"""Testes do servidor: detector de senhas e chaves, gravação segura do config.json e resolução de caminhos.

Uso: python tests/test_server.py    (não precisa de navegador; sai com 0 se tudo passou)
Todos os dados são fictícios.
"""
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
APP = Path(__file__).resolve().parent.parent / "app"
spec = importlib.util.spec_from_file_location("srv", APP / "server.py")
srv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(srv)
app = APP
fs = srv.find_secret
J = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.abcDEF123456"
RAND = "q7Zx9KfT2mWp4LbV8nRc" + "3HsY6dJg1QtXk5PwNz0B"   # 40, aleatório
bad = {
    "campo senha": {"senha": "x"},
    "campo password": {"access": {"password": "abc"}},
    "connection_string": {"connection_string": "postgresql://app:Segredo123@db.exemplo.invalid:5432/app"},
    "jwt solto": {"access": {"method": "http", "keyEnv": J}},
    "jwt no meio do texto": {"note": "use a chave " + J + " no cabeçalho"},
    "usuario:senha@ no comando": {"access": {"method": "cli", "command": 'psql "postgresql://app:Segredo123@db.exemplo.invalid/app"'}},
    "PGPASSWORD=valor": {"access": {"method": "cli", "command": "PGPASSWORD=Segredo123 psql -h db.exemplo.invalid"}},
    "password= em conninfo": {"access": {"method": "cli", "command": "psql 'host=db.exemplo.invalid password=Segredo123'"}},
    "apikey na URL": {"access": {"method": "http", "url": "https://api.exemplo.invalid/v1?apikey=abc12345xyz"}},
    "Bearer no args": {"access": {"method": "mcp", "args": "Authorization: Bearer abcdef1234567890"}},
    "sk- com dígito": {"note": "chave sk-abcdefgh12345678ijkl"},
    "sb_secret_": {"note": "sb_secret_abcdefghijk"},
    "ghp_": {"note": "ghp_abcdefghijklmnopqrstuv123"},
    "AKIA": {"note": "AKIA" + "ABCDEFGHIJKLMNOP"},
    "token aleatório": {"access": {"args": RAND}},
    "jwt na descrição da tabela": {"tables": [{"name": "t", "description": J}]},
    "SERVICE_KEY=valor": {"access": {"method": "cli", "command": "SERVICE_KEY=qwerty123 cliente"}},
    "X_KEY=valor (outro)": {"note": "defina MINHA_API_KEY=abcd1234wxyz antes"},
    "token aleatório 2": {"access": {"args": "Kd8Rw3NzQx7LpV2mTc5Y" + "bH9sJf4GqXa6UeW1oPzB"}},
    "senha sem dígito": {"access": {"method": "cli", "command": "psql 'host=db.exemplo.invalid password=minhasenhaforte'"}},
    "chave=valor": {"access": {"args": "chave=Abc123456789xyz"}},
    "CHAVE_API=valor": {"access": {"args": "CHAVE_API=Abc123456789xyz"}},
    "DB_PASS=valor": {"access": {"command": "DB_PASS=Segredo123 cliente"}},
    "pass=valor": {"note": "pass=Segredo123"},
    "--api-key=valor": {"access": {"command": "cliente-api --api-key=Abc123456789xyz"}},
    "private-key=valor": {"note": "private-key=Abc123456789"},
    "service_key=valor": {"note": "service_key=qwerty123"},
    "serviceKey=valor": {"note": "serviceKey=qwerty123x"},
    "API_KEY em maiúsculas": {"access": {"args": "API_KEY=K7Q2M9X4P1Z8W3R5"}},
    "?apikey em maiúsculas": {"access": {"method": "http", "url": "https://api.exemplo.invalid/v1?apikey=K7Q2M9X4P1Z8W3R5"}},
    "PGPASSWORD maiúsculas": {"access": {"command": "PGPASSWORD=SEGREDO2024 psql"}},
    "mysql -pSenha": {"access": {"command": "mysql -h db.exemplo.invalid -u leitor -pSegredo123 vendas -e \"select 1\""}},
    "--password Senha": {"access": {"command": "mysql -u leitor --password Segredo123 vendas"}},
    "sqlcmd -P Senha": {"access": {"command": "sqlcmd -S srv.exemplo.invalid -U leitor -P Segredo123"}},
    "senha: valor": {"note": "usuário: leitor / senha: Segredo123"},
    "JSON password": {"access": {"args": "{\"user\": \"leitor\", \"password\": \"Segredo123\"}"}},
    "JSON api_key": {"access": {"args": "{\"api_key\": \"Abc123456789xyz\"}"}},
    "X-API-Key:": {"note": "X-API-Key: Abc123456789xyz"},
    "Authorization: Token": {"note": "Authorization: Token Abc123456789"},
    "senha=fica (pede confirmação)": {"note": "senha=fica no cofre"},
    "$env:PGPASSWORD": {"access": {"command": "$env:PGPASSWORD=\"Segredo123\"; psql -h db.invalid -U leitor -d vendas"}},
    "rótulo: senha=": {"note": "obs: senha=Segredo123"},
    "PGPASSWORD=vendas": {"access": {"command": "PGPASSWORD=vendas psql -h db.invalid -U leitor vendas"}},
    "conexão com senha fraca": {"access": {"command": "psql \"postgresql://leitor:vendas@db.invalid:5432/vendas\""}},
    "senhaBanco=": {"access": {"args": "senhaBanco=Segredo123"}},
    "conexão na descrição de tabela": {"tables": [{"name": "eventos", "description": "origem: postgresql://leitor:Segredo123@db.exemplo.invalid:5432/vendas"}]},
    "curl -u": {"access": {"command": "curl -u leitor:Segredo123 https://api.exemplo.invalid"}},
    "JSON client_secret": {"access": {"args": "{\"client_id\": \"vendas\", \"client_secret\": \"Segredo123\"}"}},
    "JSON db_password": {"access": {"args": "{\"host\": \"db.invalid\", \"db_password\": \"Segredo123\"}"}},
    "JSON senha_cert": {"access": {"args": "{\"cert\": \"C:/cert/cliente.pfx\", \"senha_cert\": \"Segredo2024\"}"}},
    "JSON access_token": {"access": {"args": "{\"access_token\": \"K7q2M9x4P1z8W3r5\"}"}},
    "JSON password só letras": {"access": {"args": "{\"user\": \"leitor\", \"password\": \"Vendedores\"}"}},
    "YAML db_password": {"note": "db_password: Segredo123"},
    "pass: valor": {"note": "user: leitor / pass: Segredo123"},
    "senha do banco: valor": {"note": "Senha do banco: Segredo123"},
    "SQLCMD.EXE pelo caminho": {"access": {"command": "\"C:\\Program Files\\SQL\\SQLCMD.EXE\" -S srv.invalid -U sa -P Segredo123 -Q \"select 1\""}},
    "bcp -P": {"access": {"command": "bcp \"select 1\" queryout C:/x.csv -S srv -U sa -P Segredo123 -c"}},
    "mysql -p na nota": {"note": "Para conectar: mysql -h db.invalid -u leitor -pSegredo123 vendas"},
    "mysql -p nos args": {"access": {"args": "mysql -u leitor -pSegredo123"}},
    "--api-key com espaço": {"access": {"command": "cliente-api --api-key Abc123456789xyz"}},
    "setx": {"note": "Configurei com: setx PGPASSWORD Segredo123"},
    "PGPASSWORD=VENDAS_2024": {"access": {"command": "PGPASSWORD=VENDAS_2024 psql"}},
    "redis sem usuário": {"note": "redis://:Segredo123@cache.invalid:6379/0"},
    "curl --user": {"access": {"command": "curl --user leitor:Segredo123 https://api.exemplo.invalid"}},
    "senha que começa com 'Senha'": {"access": {"command": "PGPASSWORD=SenhaDaVendas2024 psql -h db.invalid"}},
    "senha: Passarela2024": {"note": "senha: Passarela2024"},
    "JSON senhadoprojeto": {"access": {"args": "{\"user\":\"leitor\",\"password\":\"senhadoprojeto2024\"}"}},
    "conexão Senhadoprojeto1": {"note": "postgresql://leitor:Senhadoprojeto1@db.invalid/vendas"},
    "Senha Portal: X": {"note": "Senha Portal: Segredo123"},
    "Senha do certificado do servidor": {"note": "Senha do certificado do servidor: 1234"},
    "Usuário | Senha Painel": {"note": "Usuário: convidado | Senha Painel: Segredo2024"},
    "A senha é X": {"note": "A senha é Vendas@2024"},
    "x-api-key hex": {"access": {"command": "curl -H \"x-api-key: e3b0c44298fc1c149afbf4c8996fb924\" https://api.invalid/v1/itens"}},
    "token: hex": {"note": "token: e3b0c44298fc1c149afbf4c8996fb924"},
}
good = {
    "caminho comprido": {"access": {"method": "file", "file": "C:/dados/planilhas/RelatorioMensalParaConferenciaV2Final.xlsx"}},
    "URL simples": {"access": {"method": "http", "url": "https://api.exemplo.invalid/v1/projetos"}},
    "variável de ambiente": {"access": {"method": "http", "keyEnv": "MEU_BANCO_CHAVE"}},
    "PGPASSWORD=$VAR": {"access": {"method": "cli", "command": "PGPASSWORD=$MINHA_SENHA psql -h db.exemplo.invalid"}},
    "password=%VAR%": {"access": {"method": "cli", "command": "set PGPASSWORD=%MINHA_SENHA% && psql"}},
    "--password-file=caminho": {"access": {"method": "cli", "command": "mytool --password-file=/home/x/.pw query"}},
    "nome de ferramenta MCP com uuid": {"access": {"method": "mcp", "tool": "mcp__5c0ffee0-1234-4abc-8def-0123456789ab__read_records"}},
    "nome de tabela comprido": {"tables": [{"name": "eventos_detalhados_por_projeto_e_periodo", "description": "VeryLongTableNameForMonthlyEvents2024Q1Version2", "columns": [{"name": "senha", "description": "token do portal"}]}]},
    "camelCase comprido": {"note": "VeryLongIdentifierForProjectReportEntries2024Q1Version2"},
    "nota com a palavra token": {"note": "o token fica na variável MEU_TOKEN; nunca escreva o valor"},
    "ref do projeto": {"ref": "projeto-exemplo-001", "schema": "vendas"},
    "api_key_env=NOME": {"access": {"args": "api_key_env=MEU_BANCO_CHAVE"}},
    "token_env = NOME": {"access": {"args": "token_env = MEU_TOKEN"}},
    "secret_name = x": {"access": {"args": "secret_name = credenciais_banco"}},
    "password=prompt": {"note": "use password=prompt para pedir a senha"},
    "Bearer authentication": {"note": "A API usa Bearer authentication; a chave fica em MEU_TOKEN."},
    "token = palavra": {"note": "a coluna token = identificador do cliente"},
    "database_id hex": {"access": {"args": "database_id: 0123456789abcdef0123456789abcdef"}},
    "spreadsheet_id": {"access": {"args": "spreadsheet_id = 1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789AbCdEfG"}},
    "?key=PLACEHOLDER": {"access": {"method": "http", "url": "https://api.exemplo.invalid/v1/dados?key=SUA_CHAVE"}},
    "--token-file": {"access": {"method": "cli", "command": "cliente-api --token-file=token.txt consulta"}},
    "sort_key=coluna": {"access": {"args": "sort_key=created_at"}},
    "hash hex numa observação": {"note": "versão 0123456789abcdef0123456789abcdef0123"},
    "senha = pedir": {"note": "usuário = leitor, senha = pedir ao usuário na hora"},
    "senha=perguntar": {"note": "senha=perguntar"},
    "senha=xxxxxxxx": {"note": "senha=xxxxxxxx"},
    "mostrar_senha=false": {"access": {"args": "mostrar_senha=false"}},
    "secretaria=compras": {"note": "filtrar por secretaria = Educacao; secretaria=compras"},
    "politica_senha=forte": {"access": {"args": "politica_senha=forte senha_padrao=nenhuma"}},
    "id numérico longo na nota": {"note": "A coluna chave guarda o Id do evento, ex.: ID12345678901234567890123456789012"},
    "id numérico longo no comando": {"access": {"command": "consulta --id ID12345678901234567890123456789012"}},
    "chave numérica": {"access": {"args": "chave_evento=12345678901234567890123456789012"}},
    "ferramenta MCP com uuid camelCase": {"access": {"method": "mcp", "tool": "mcp__1b2c3d4e-0f9a-4b8c-8d7e-6f5a4b3c2d1e__listTables"}},
    "conexão com marcador": {"note": "formato: postgresql://usuario:senha@host:5432/banco ou postgresql://user:password@localhost/db ou postgresql://leitor:SENHA@db.exemplo.invalid/db"},
    "id de planilha em JSON": {"access": {"args": "{\"spreadsheet_id\": \"1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789AbCdEfG\"} {\"spreadsheetId\":\"1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789AbCdEfG\"}"}},
    "--spreadsheet-id": {"access": {"command": "cliente --spreadsheet-id 1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789AbCdEfG"}},
    "psql -p5432": {"access": {"command": "psql -p5432 -h db.exemplo.invalid -U leitor"}},
    "token: palavra": {"note": "token: use a variável MEU_TOKEN"},
    "mysql -P porta": {"access": {"command": "mysql -h localhost -P 3306 -u leitor -p base_vendas"}},
    "psql -P opção": {"access": {"command": "psql -d vendas -P tuples_only=on -c \"select 1\""}},
    "Senha: integrada": {"note": "Senha: integrada (autenticação do Windows); senha: solicitar ao TI; senha: (vazia); Senha: variável de ambiente PGPASSWORD"},
    "key: identificador": {"note": "key: id_evt_2024; Chave: cod_proj1 (uma linha por projeto)"},
    "primary_key=": {"access": {"args": "primary_key=cod_proj2 sort_key=periodo_2024"}},
    "token_url": {"access": {"args": "{\"token_url\": \"https://auth.exemplo.invalid/oauth2/token\"}"}},
    "chave numérica com prefixo": {"access": {"args": "chave_transacao=ID12345678901234567890123456789012"}},
    "lista com hífen na nota": {"note": "Tabelas usadas:\n-eventos\n-usuarios"},
    "conexão modelo [SUA-SENHA]": {"note": "postgresql://usuario.projeto-exemplo-001:[SUA-SENHA]@pooler.exemplo.invalid:5432/postgres e postgresql://usuario:sua_senha@servidor:5432/banco"},
    "JSON id de planilha": {"access": {"args": "{\"spreadsheet_id\": \"1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789AbCdEfG\", \"token_url\": \"https://auth.exemplo.invalid/oauth2/token\"}"}},
    "mysql -P porta e -p sem senha": {"access": {"command": "mysql -h localhost -P 3306 -u leitor -p base_vendas"}},
    "mysql -P3306 colado": {"access": {"command": "mysql -h db.invalid -P3306 -u leitor -p vendas"}},
    "datas de validade": {"note": "senha_expira: 2024-12-31; token_expires_at: 2024-12-31T00:00:00Z; senha_alterada_em: 01/2024"},
    "instruções sem senha": {"note": "não passe --password para o mysql; use MYSQL_PWD. No sqlcmd use -P apenas com variável."},
}
fails = 0
for k, v in bad.items():
    hit = fs([v])
    print(("ok  " if hit else "FAIL") + f" barra   {k:32} -> {hit!r}")
    fails += not hit
for k, v in good.items():
    hit = fs([v])
    print(("ok  " if not hit else "FAIL") + f" aceita  {k:32} -> {hit!r}")
    fails += bool(hit)
ev = srv.bad_env_names([{"access": {"method": "http", "keyEnv": "MEU_BANCO_CHAVE"}}, {"access": {"method": "http", "keyEnv": "sbp_0123456789abcdef"}}, {"access": {"method": "http", "keyEnv": "minha chave"}}, {"access": {"method": "mcp", "keyEnv": "minha_chave_antiga"}}])
print(("ok  " if ev == ["bancos[1].access.keyEnv", "bancos[2].access.keyEnv"] else "FAIL") + f" keyEnv estrito -> {ev}")
fails += ev != ["bancos[1].access.keyEnv", "bancos[2].access.keyEnv"]
import random, string, time as _t
random.seed(7); base62 = string.ascii_letters + string.digits
miss = sum(1 for _ in range(2000) if not fs([{"access": {"args": "".join(random.choice(base62) for _ in range(40))}}]))
print(("ok  " if miss <= 60 else "FAIL") + f" tokens aleatórios de 40 que passariam: {miss}/2000"); fails += miss > 60
import uuid
camel = ["listTables", "getRecords", "findDocuments", "runSql", "getTableSchema", "queryDatabase"]
mfp = sum(1 for i in range(600) if fs([{"access": {"method": "mcp", "tool": f"mcp__{uuid.UUID(int=random.getrandbits(128))}__{camel[i % 6]}"}}]))
print(("ok  " if mfp == 0 else "FAIL") + f" nomes de ferramenta MCP recusados: {mfp}/600"); fails += mfp > 0
t0 = _t.time(); fs([{"note": "sk-" * 20000}]); fs([{"note": "eyJ" * 20000}]); fs([{"note": "a." * 8000}]); fs([{"note": "a=" * 8000}]); fs([{"note": "x" * 100000}]); dt = _t.time() - t0
print(("ok  " if dt < 4 else "FAIL") + f" textos longos sem espaço: {dt:.2f}s"); fails += dt >= 4

# servidor de verdade: config com erro não é sobrescrito; cópia .bak a cada gravação; outras chaves preservadas
T = Path(tempfile.mkdtemp(prefix="sf-srv-"))
with socket.socket() as so:
    so.bind(("127.0.0.1", 0)); port = so.getsockname()[1]
env = dict(os.environ, USERPROFILE=str(T / "home"), HOME=str(T / "home"), APPDATA=str(T / "ad"), LOCALAPPDATA=str(T / "lad"))
p = subprocess.Popen([sys.executable, str(app / "server.py"), "--port", str(port), "--data", str(T / "data")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def call(method, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "X-Skill-Flow": "1"})
    try:
        r = urllib.request.urlopen(req, timeout=5); return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def check(name, cond):
    global fails
    print(("ok  " if cond else "FAIL") + " " + name); fails += not cond


try:
    for _ in range(40):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1); break
        except Exception:
            time.sleep(0.25)
    cfgp = T / "data" / "config.json"
    cfg = json.loads(cfgp.read_text(encoding="utf-8")); cfg["skillCategory"] = {"minha-skill": "A/B"}; cfg["extra"] = 1
    cfgp.write_text(json.dumps(cfg), encoding="utf-8")
    st, _ = call("PUT", "/api/databases", {"databases": [{"id": "db:a", "name": "A", "engine": "sqlite", "access": {"method": "file", "file": "C:/x.db"}, "tables": []}]})
    c2 = json.loads(cfgp.read_text(encoding="utf-8"))
    check("grava bancos e preserva as outras chaves", st == 200 and c2["databases"][0]["id"] == "db:a" and c2["skillCategory"] == {"minha-skill": "A/B"} and c2["extra"] == 1)
    check("faz cópia config.json.bak antes de gravar", (T / "data" / "config.json.bak").exists() and json.loads((T / "data" / "config.json.bak").read_text(encoding="utf-8"))["databases"] == [])
    st, _ = call("PUT", "/api/databases", {"databases": []})
    check("a cópia do config antes da 1ª gravação de bancos não é sobrescrita", json.loads((T / "data" / "config.antes-dos-bancos.json").read_text(encoding="utf-8"))["databases"] == [] and json.loads((T / "data" / "config.json.bak").read_text(encoding="utf-8"))["databases"][0]["id"] == "db:a")
    call("PUT", "/api/databases", {"databases": [{"id": "db:a", "name": "A", "engine": "sqlite", "access": {"method": "file", "file": "C:/x.db"}, "tables": []}]})
    st, _ = call("PUT", "/api/categories", {"map": {"outra": "C"}})
    check("categorias também fazem cópia (.bak tem o banco gravado antes)", st == 200 and json.loads((T / "data" / "config.json.bak").read_text(encoding="utf-8"))["databases"][0]["id"] == "db:a")
    broken = '{"databases": [ {"id": "db:a",} ]'
    cfgp.write_text(broken, encoding="utf-8")
    st, r = call("PUT", "/api/databases", {"databases": []})
    check("config com erro: recusa (409) com linha/coluna e não sobrescreve", st == 409 and "linha" in r.get("error", "") and cfgp.read_text(encoding="utf-8") == broken)
    st, r = call("PUT", "/api/categories", {"map": {"x": "Y"}})
    check("config com erro: categorias também recusam", st == 409 and cfgp.read_text(encoding="utf-8") == broken)
    st, r = call("GET", "/api/catalog")
    check("catálogo avisa do erro no config", st == 200 and "linha" in (r.get("configError") or ""))
    cfgp.write_text(json.dumps(cfg), encoding="utf-8")
    st, r = call("PUT", "/api/databases", {"databases": [{"id": "db:b", "name": "B", "access": {"method": "http", "keyEnv": "minha_chave="}}]})
    check("keyEnv que não é nome de variável é recusado", st == 400)
    st, r = call("PUT", "/api/databases", {"databases": [{"id": "db:b", "name": "B", "access": {"method": "mcp", "keyEnv": "minha_chave_antiga"}}]})
    check("keyEnv antigo em acesso que não é http não bloqueia", st == 200)
    soft = [{"id": "db:s", "name": "S", "access": {"method": "cli", "command": "PGPASSWORD=Segredo123 psql"}},
            {"id": "db:t", "name": "T", "note": "senha: Abc12345"}]
    st, r = call("PUT", "/api/databases", {"databases": soft})
    keys = [f["key"] for f in r.get("findings", [])]
    check("provável senha: 422 listando TODOS os achados", st == 422 and r.get("soft") is True and len(keys) == 2 and "bancos[1].note" in r.get("error", ""))
    f1 = (r.get("findings") or [{}])[1] if len(r.get("findings") or []) > 1 else {}
    check("cada achado traz banco, número, campo e trecho mascarado", f1.get("banco") == "T" and f1.get("n") == 2 and f1.get("campo") == "note" and "•••" in f1.get("trecho", "") and "Abc12345" not in f1.get("trecho", ""))
    st, r = call("PUT", "/api/databases", {"databases": soft, "confirm": keys[:1]})
    check("confirmar só um achado não libera o outro", st == 422 and len(r.get("findings", [])) == 1)
    st, r = call("PUT", "/api/databases", {"databases": soft, "confirm": keys})
    check("com os dois confirmados, grava", st == 200)
    st, r = call("PUT", "/api/databases", {"databases": soft + [{"id": "db:u", "name": "U", "note": "sem nada"}]})
    check("a liberação é lembrada: gravar de novo não pergunta", st == 200)
    soft2 = soft + [{"id": "db:v", "name": "V", "access": {"method": "cli", "command": "mysql -u leitor --password Segredo2024 vendas"}}]
    st, r = call("PUT", "/api/databases", {"databases": soft2})
    check("um texto novo é perguntado (e só ele)", st == 422 and [f["where"] for f in r.get("findings", [])] == ["bancos[2].access.command"])
    st, r = call("PUT", "/api/databases", {"databases": [{"id": "db:h", "name": "H", "note": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.abc"}], "confirm": True})
    check("chave inconfundível: 400 mesmo com confirmação", st == 400)
    st, r = call("PUT", "/api/databases", {"databases": [{"id": "db:c", "name": "C", "note": "postgresql://app:Segredo123@db.exemplo.invalid:5432/app"}], "confirm": True})
    check("usuario:senha@ numa URL: 400 mesmo com confirmação", st == 400)
    st, r = call("PUT", "/api/databases", {"databases": [{"id": "db:c", "name": "C", "note": "formato: postgresql://usuario:senha@host:5432/banco"}]})
    check("URL de conexão com marcador no lugar da senha é aceita", st == 200)
    st, r = call("PUT", "/api/databases", {"databases": [], "retired": ["db:s"]})
    st2, cat = call("GET", "/api/catalog")
    check("ids de bancos removidos ficam guardados", st == 200 and "db:s" in (cat.get("databasesRetired") or []))
    c3 = json.loads(cfgp.read_text(encoding="utf-8")); c3["databasesRetired"] = None; c3["databasesAccepted"] = 5; cfgp.write_text(json.dumps(c3), encoding="utf-8")
    st, r = call("PUT", "/api/databases", {"databases": []})
    st2, cat = call("GET", "/api/catalog")
    check("databasesRetired/Accepted inválidos no config não derrubam a gravação", st == 200 and st2 == 200 and cat.get("databasesRetired") == [])
finally:
    try:
        call("POST", "/api/shutdown")
    except Exception:
        pass
    p.terminate()
    shutil.rmtree(T, ignore_errors=True)

# caminhos do config.json: relativos à pasta do config, ~ e o prefixo das skills de conta
T2 = Path(tempfile.mkdtemp(prefix="sf-path-"))
try:
    home2 = T2 / "home"
    os.environ["HOME"] = os.environ["USERPROFILE"] = str(home2)
    srv.HOME, srv.APPDATA, srv.LOCALAPPDATA = home2, T2 / "ad", T2 / "lad"
    (T2 / "data").mkdir()
    for base, name in [(T2 / "skills", "minha-skill"), (home2 / ".claude" / "skills", "skill-pessoal"),
                       (T2 / "x" / "skills-plugin" / "a" / "b" / "skills", "skill-de-conta")]:
        (base / name).mkdir(parents=True)
        (base / name / "SKILL.md").write_text(f"---\nname: {name}\ndescription: d\n---\n# {name}\n\n## Parte\ntexto\n", encoding="utf-8")
    (T2 / "CLAUDE.md").write_text("# Regras\n\n## Segurança\nconfirme antes de apagar\n", encoding="utf-8")
    (T2 / "projeto").mkdir()
    (T2 / "projeto" / "CLAUDE.md").write_text("# Projeto\n\n## Convenções\nnomes em minúsculas\n", encoding="utf-8")
    cfg = {"skillRoots": ["../skills", "~/.claude/skills", str(T2 / "x" / "skills-plugin" / "a" / "b" / "skills")],
           "claudeMdFiles": ["../CLAUDE.md"], "projectRoots": ["../projeto"], "skillCategory": {"minha-skill": "Grupo/Sub"}, "databases": []}
    (T2 / "data" / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    cat = srv.Catalog(T2 / "data").full()
    names = {x["name"]: x for x in cat["skills"]}
    check("skillRoots relativo (à pasta do config) e com ~ são lidos", {"minha-skill", "skill-pessoal", "skill-de-conta"} <= set(names))
    check("a categoria vem do config; sem config é 'Outras/Geral'", names["minha-skill"]["category"] == "Grupo" and names["skill-pessoal"]["category"] == "Outras" and names["skill-pessoal"]["sub"] == "Geral")
    check("skill de pasta de conta ganha o prefixo anthropic-skills:", names["skill-de-conta"]["invoke"] == "anthropic-skills:skill-de-conta" and names["minha-skill"]["invoke"] == "minha-skill")
    labels = [m["label"] for m in cat["claudeMd"]]
    check("claudeMdFiles relativo e projectRoots relativo são lidos", len(cat["claudeMd"]) == 2 and any(l.endswith("projeto/CLAUDE.md") for l in labels))
    check("a seção do CLAUDE.md vem separada pelo título", any(sec["title"] == "Segurança" for m in cat["claudeMd"] for sec in m["sections"]))
finally:
    shutil.rmtree(T2, ignore_errors=True)

print(f"\nRESULTADO: {fails} falha(s)")
sys.exit(1 if fails else 0)
