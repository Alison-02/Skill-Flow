#!/usr/bin/env python3
"""Skill Flow: servidor local do editor de fluxos (só biblioteca padrão do Python).

- Escuta apenas em 127.0.0.1.
- Lê skills (SKILL.md + references/*.md) e CLAUDE.md e os quebra em seções.
- Não lê nenhum arquivo fora dos que ele mesmo descobriu; nunca conecta a banco de dados.
- Escreve apenas dentro da pasta de dados: <dados>/flows, <dados>/runs, <dados>/out e <dados>/config.json
  (mais as cópias de segurança config.json.bak e config.antes-*.json).

Uso: python server.py [--port 8765] [--data <pasta>] [--check]
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
HOME = Path(os.environ.get("USERPROFILE") or Path.home())
APPDATA = Path(os.environ.get("APPDATA") or HOME / "AppData" / "Roaming")
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA") or HOME / "AppData" / "Local")

DEFAULT_CONFIG = {
    "_comentario": "Edite à vontade. skillRoots: pastas que contêm pastas de skills. "
    "claudeMdFiles: arquivos CLAUDE.md extras. projectRoots: pastas varridas (2 níveis) atrás de CLAUDE.md. "
    "Caminhos relativos valem a partir da pasta deste arquivo; ~ é a sua pasta pessoal. "
    "skillCategory: nome da skill -> 'Categoria/Subcategoria'. databases: bancos declarados no editor (tabelas, colunas e como o Claude "
    "acessa); o editor nunca conecta e chaves NUNCA ficam aqui (só o nome da variável de ambiente).",
    "skillRoots": [],
    "claudeMdFiles": [],
    "projectRoots": [],
    "skillCategory": {},
    "databases": [],
}

BUILTIN_TOOLS = [
    ("Read", "Ler arquivo (pode usar offset/limit para trechos)"),
    ("Write", "Criar/sobrescrever arquivo"),
    ("Edit", "Editar trecho de arquivo"),
    ("Bash", "Executar comando de shell"),
    ("Glob", "Buscar arquivos por padrão"),
    ("Grep", "Buscar texto em arquivos"),
    ("WebSearch", "Pesquisar na web"),
    ("WebFetch", "Ler uma página web"),
    ("Skill", "Carregar uma skill"),
    ("Agent", "Delegar a um subagente"),
    ("AskUserQuestion", "Perguntar ao usuário"),
]

def chash(text):
    """Impressão digital do conteúdo, imune a CRLF x LF, espaço no fim da linha e linhas em branco nas pontas."""
    norm = "\n".join(l.rstrip() for l in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")).strip()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]


HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")


class Catalog:
    """Varredura dos arquivos; guarda os caminhos conhecidos (lista de permissão)."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.config_path = data_dir / "config.json"
        self.lock = threading.Lock()
        self.known_paths = set()
        self.config = self._load_config()

    def _load_config(self, strict=False):
        """Lê o config.json. Com erro: para ler, usa o modelo e guarda o erro (o editor avisa);
        para gravar (strict), recusa, para não trocar o arquivo do usuário pelo modelo."""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            if not self.config_path.exists():
                self.config_path.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass   # pasta sem permissão de escrita: segue com o modelo na memória (main() e --check avisam)
        try:
            cfg = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
            if not isinstance(cfg, dict):
                raise ValueError("o conteúdo não é um objeto { ... }")
            self.config_error = ""
            return cfg
        except Exception as e:
            msg = f"linha {e.lineno}, coluna {e.colno}: {e.msg}" if isinstance(e, json.JSONDecodeError) else str(e)
            msg = f"{self.config_path.as_posix()}, {msg}"
            self.config_error = msg
            if strict:
                raise ConfigError(msg)
            return dict(DEFAULT_CONFIG)

    def config_for_write(self, first_copy=None):
        """Config lido com rigor + cópia de segurança (config.json.bak) antes de cada gravação;
        first_copy: guarda também, uma única vez, o config como estava antes da primeira gravação desse tipo."""
        cfg = self._load_config(strict=True)
        text = self.config_path.read_text(encoding="utf-8-sig")
        if first_copy and not (self.data_dir / first_copy).exists():
            write_atomic(self.data_dir / first_copy, text)
        write_atomic(self.data_dir / "config.json.bak", text)
        return cfg

    @staticmethod
    def read_lines(path: Path):
        return path.read_text(encoding="utf-8", errors="replace").splitlines()

    @staticmethod
    def parse_sections(lines):
        """Títulos (fora de blocos de código) com intervalo de linhas 1-based [start, end]."""
        heads, in_fence = [], False
        for i, line in enumerate(lines, 1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            m = HEADING.match(line)
            if m:
                heads.append({"level": len(m.group(1)), "title": m.group(2).strip(), "start": i})
        seen = {}
        for idx, h in enumerate(heads):
            end = len(lines)
            for nxt in heads[idx + 1:]:
                if nxt["level"] <= h["level"]:
                    end = nxt["start"] - 1
                    break
            h["end"] = end
            h["hash"] = chash("\n".join(lines[h["start"] - 1:end]))
            h["occ"] = seen.get(h["title"], 0)  # n-ésimo título igual no mesmo arquivo
            seen[h["title"]] = h["occ"] + 1
        if len(heads) > 1 and heads[0]["level"] == 1:  # o H1 do arquivo equivale ao arquivo inteiro
            heads = heads[1:]
        return heads

    @staticmethod
    def frontmatter(lines):
        meta = {}
        if lines and lines[0].strip() == "---":
            for line in lines[1:]:
                if line.strip() == "---":
                    break
                m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
                if m:
                    meta[m.group(1)] = m.group(2).strip().strip('"').strip("'")
        return meta

    def file_entry(self, path: Path):
        p = str(path)
        self.known_paths.add(os.path.normcase(os.path.abspath(p)))
        lines = self.read_lines(path)
        return {"path": p.replace("\\", "/"), "lines": len(lines), "hash": chash("\n".join(lines)),
                "sections": self.parse_sections(lines)}, lines

    def cfg_path(self, value):
        """Caminho escrito no config.json: ~ vira a pasta pessoal; relativo vale a partir da pasta do config."""
        p = Path(os.path.expanduser(str(value)))
        return p if p.is_absolute() else (self.data_dir / p).resolve()

    def skill_roots(self):
        # O app Claude é MSIX: o Roaming dele é redirecionado para Packages\Claude_*\LocalCache\Roaming.
        bases = [APPDATA, *Path(LOCALAPPDATA / "Packages").glob("Claude_*/LocalCache/Roaming")]
        roots = []
        for base in bases:
            roots += glob.glob(str(base / "Claude" / "local-agent-mode-sessions" / "skills-plugin" / "*" / "*" / "skills"))
        roots.append(str(HOME / ".claude" / "skills"))
        roots += [self.cfg_path(r) for r in self.config.get("skillRoots", []) if isinstance(r, str)]
        return [Path(r) for r in roots if Path(r).is_dir()]

    def scan_skills(self):
        out, seen = [], set()
        cats = self.config.get("skillCategory", {})
        for root in self.skill_roots():
            account_skill = "skills-plugin" in str(root)
            for d in sorted(root.iterdir()):
                md = d / "SKILL.md"
                if not md.is_file() or d.name in seen:
                    continue
                seen.add(d.name)
                try:
                    entry, lines = self.file_entry(md)
                except Exception:
                    continue
                meta = self.frontmatter(lines)
                cat = cats.get(d.name) or self.guess_category(d.name)
                cat, _, sub = cat.partition("/")
                refs = []
                refdir = d / "references"
                if refdir.is_dir():
                    for f in sorted(refdir.rglob("*.md")):
                        try:
                            rentry, _ = self.file_entry(f)
                        except Exception:
                            continue
                        rentry["name"] = f.relative_to(refdir).as_posix()
                        refs.append(rentry)
                out.append({
                    "id": "sk:" + d.name,
                    "name": d.name,
                    "invoke": ("anthropic-skills:" + d.name) if account_skill else d.name,
                    "description": meta.get("description", ""),
                    "category": cat,
                    "sub": sub or "Geral",
                    "catSet": bool(cats.get(d.name)),
                    "file": entry,
                    "references": refs,
                })
        return out

    @staticmethod
    def guess_category(name):
        return "Outras/Geral"

    def scan_claude_md(self):
        files = [HOME / ".claude" / "CLAUDE.md"] + [self.cfg_path(f) for f in self.config.get("claudeMdFiles", []) if isinstance(f, str)]
        for root in self.config.get("projectRoots", []):
            if not isinstance(root, str):
                continue
            r = self.cfg_path(root)
            if not r.is_dir():
                continue
            for pattern in ("CLAUDE.md", "*/CLAUDE.md", ".claude/CLAUDE.md"):
                files += list(r.glob(pattern))
        out, seen = [], set()
        for f in files:
            try:
                key = os.path.normcase(str(f.resolve()))
                if key in seen or not f.is_file():
                    continue
                seen.add(key)
                entry, _ = self.file_entry(f)
            except Exception:
                continue
            is_global = f.resolve() == (HOME / ".claude" / "CLAUDE.md").resolve()
            entry["id"] = "md:" + str(len(out))
            entry["label"] = "CLAUDE.md global (usuário)" if is_global else f"{f.parent.name}/CLAUDE.md"
            out.append(entry)
        return out

    def scan_tools(self):
        groups = {"Nativas": [{"name": n, "description": d} for n, d in BUILTIN_TOOLS]}
        tools_json = self.data_dir / "tools.json"
        if tools_json.is_file():
            try:
                for t in json.loads(tools_json.read_text(encoding="utf-8")):
                    name = t.get("name", "")
                    if name.startswith("mcp__"):
                        parts = name.split("__")
                        server = parts[1] if len(parts) > 2 else "mcp"
                        if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-.*", server):  # id de conector: agrupa junto
                            server = "Conectores"
                        groups.setdefault("MCP: " + server, []).append({"name": name, "description": (t.get("description") or "")[:160]})
                    elif name not in {n for n, _ in BUILTIN_TOOLS}:
                        groups["Nativas"].append({"name": name, "description": (t.get("description") or "")[:160]})
            except Exception:
                pass
        return groups

    def full(self):
        with self.lock:
            self.config = self._load_config()
            self.known_paths = set()
            return {
                "skills": self.scan_skills(),
                "claudeMd": self.scan_claude_md(),
                "databases": self.config.get("databases", []),
                "configError": getattr(self, "config_error", ""),
                "databasesRetired": [x for x in self.config.get("databasesRetired", []) if isinstance(x, str)] if isinstance(self.config.get("databasesRetired"), list) else [],
                "tools": self.scan_tools(),
                "dataDir": str(self.data_dir).replace("\\", "/"),
            }

    def section_text(self, path, heading, occ=0):
        norm = os.path.normcase(os.path.abspath(path))
        if norm not in self.known_paths:
            raise PermissionError("arquivo fora do catálogo")
        lines = self.read_lines(Path(path))
        if not heading:
            return "\n".join(lines)
        for h in self.parse_sections(lines):
            if h["title"] == heading and h["occ"] == occ:
                return "\n".join(lines[h["start"] - 1:h["end"]])
        raise KeyError("seção não encontrada")


STARTED_MS = int(Path(__file__).stat().st_mtime * 1000)


_WRITE_LOCK = threading.Lock()


def write_atomic(path, text):
    """Grava num temporário único da mesma pasta e só então troca pelo definitivo.
    Caractere inválido vira '?' (não derruba a gravação); no Windows, tenta de novo se o arquivo estiver preso."""
    import tempfile
    import time
    with _WRITE_LOCK:
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", errors="replace") as f:
                f.write(text)
            for i in range(6):
                try:
                    os.replace(tmp, path)
                    return
                except PermissionError:
                    if i == 5:
                        raise
                    time.sleep(0.15)
        finally:
            if os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass


SECRET_KEY = re.compile(r"^(senha|password|passwd|pass|pwd|secret|segredo|token|api_?key|apikey|chave|key|private_?key|service_?role|"
                        r"client_?secret|access_?token|connection_?string|conn_?str|dsn|db_?password)$", re.I)
NOT_REF = r"(?![$%{<~./\\*]|[A-Za-z]:[\\/])"          # $VAR, %VAR%, ${VAR}, <...>, caminhos e *** não são chaves
SECRET_STRONG = [re.compile(x) for x in (                 # formatos inconfundíveis: recusa sempre
    r"\beyJ[\w-]{10,4000}\.[\w-]{10,}",                   # JWT
    r"\bsk-(?=[\w-]{0,200}\d)[\w-]{16,}", r"\bsk_(live|test)_\w{10,}",
    r"\bsb_secret_\w{8,}", r"\bsbp_[0-9a-f]{20,}",
    r"\bghp_\w{20,}", r"\bgithub_pat_\w{20,}", r"\bglpat-[\w-]{16,}",
    r"\bxox[abprs]-[\w-]{10,}", r"\bAIza[\w-]{30,}", r"\bAKIA[0-9A-Z]{16}\b",
)]
SOFT_RX = [re.compile(x) for x in (                       # prováveis: o usuário confirma
    r"(?i)\bBearer\s+" + NOT_REF + r"(?=[^\s]{0,200}\d)[^\s]{16,}",
    r"(?i)\bAuthorization\s*:\s*(Token|Basic)\s+" + NOT_REF + r"(?=[^\s]{0,200}\d)[^\s]{8,}",
)]
STRONG_NAME = re.compile(r"(?i)(password|passwd|pwd|secret(?!ari)|(?<!re)senha|segredo|(^|[_.-])pass$|_pw$|^pw$)")
WEAK_NAME = re.compile(r"(?i)(token|api[-_]?key|apikey|access[-_]?key|private[-_]?key|signature|^sig$|chave|key$)")
REF_NAME = re.compile(r"(?i)(env|file|path|name|var|prompt|id|url|uri|endpoint|policy|politica|padrao|type|tipo|"
                      r"(primary|sort|partition|foreign|row|range|hash|cache)[-_]?key)$")   # apontam para outro lugar ou descrevem
REF_PREFIX = re.compile(r"(?i)^(politica|policy|mostrar|show|exibir|tipo|type|min|max)[-_]")   # politica_senha, mostrar_senha: descrevem
KV = re.compile(r"([\w.-]{1,64})[\"']?\s{0,8}=\s{0,8}[\"']?([^\s'\"&;,=]{1,512})")                 # NOME=valor
COLON = re.compile(r"([\"']?)([\w.-]{1,64})\1\s{0,8}:\s{0,8}[\"']?([^\s'\",;()]{1,512})")             # nome: valor (JSON, YAML, anotação)
PHRASE = re.compile(r"(?i)(?:^|(?<=[\s|(\[]))(senha|password|pass|pwd|token|chave|segredo)\b([^:=\n;|@/]{0,40}?)\s*[:=]\s*[\"']?([^\s'\",;()|]{1,512})")   # "Senha Admin: X", "senha da API: X"
IS_PHRASE = re.compile(r"(?i)\b(senha|password)\s+(?:é|e|eh|is|=)\s+[\"']?([^\s'\",;()|]{4,512})")   # "A senha é X"
URLKV = re.compile(r"(?i)[?&;]([\w.-]{1,64})=([^&\s#]{1,512})")
CONN = re.compile(r"://([^/\s:@]{0,256}):([^@\s/]{1,256})@")             # usuario:senha@ (ou :senha@) numa URL de conexão
CLI_PW_CMD = [re.compile(x) for x in (                     # no comando e nos argumentos
    r"(?:^|\s)-p(?=[^\s-])['\"]?(?=[^\s'\"]{0,200}[A-Za-z])([^\s'\"]{3,})",   # mysql -pSenha (com letra: -p5432 é porta)
)]
CLI_PW = [re.compile(x) for x in (                         # em qualquer campo
    r"(?i:\b(?:mysql|mariadb|mysqldump|mysqlsh)(?:\.exe)?\b)[^\n]{0,400}?\s-p(?=[^\s-])['\"]?([^\s'\"]{3,})",   # -p minúsculo: no mysql, -P é a porta
    r"(?i:\b(?:sqlcmd|bcp|osql|isql)(?:\.exe)?\b)[^\n]{0,400}?\s-P\s*['\"]?([^\s'\"]{3,})",   # sqlcmd -P Senha
    r"(?:^|\s)--password\s+['\"]?(?!-)([^\s'\"]{3,})",
    r"(?i)(?:^|\s)-Password\s+['\"]?(?!-)([^\s'\"]{3,})",
    r"(?:^|\s)(?:-u|--user)\s+[^\s:]{1,64}:([^\s'\"]{3,})",        # curl -u usuario:senha
)]
CLI_KEY = re.compile(r"(?i)(?:^|\s)--(api[-_]?key|token|secret|access[-_]?token|client[-_]?secret)\s+['\"]?(?!-)([^\s'\"]{3,})")
SETX = re.compile(r"(?i)\bsetx?\s+(\w{1,64})\s+['\"]?([^\s'\"]{3,})")    # setx PGPASSWORD Senha
ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]{0,63}$")
PLACEHOLDER = {"passwd", "pwd", "para", "com", "sem", "apenas", "somente", "only", "with", "for", "the", "via", "use", "usar", "ao", "no", "na",
               "do", "da", "de", "variavel", "variável", "variable", "prompt", "ask", "none", "null", "empty", "env", "false", "true", "changeme", "senha", "password", "secret", "token",
               "chave", "segredo", "perguntar", "pedir", "nenhuma", "nenhum", "vazio", "vazia", "usuario", "user", "pass", "xxx", "***"}
NUMERIC_ID = re.compile(r"^[A-Za-z]{0,6}\d{30,}$")          # identificador numérico longo (ex.: ID de transação): não é segredo


def is_placeholder(v):
    v = v.strip().strip("\"'")
    return (not v or not re.match(NOT_REF, v) or v.lower() in PLACEHOLDER or len(set(v.lower())) == 1
            or bool(re.fullmatch(r"[A-Z]+(_[A-Z]+)+", v))            # SUA_SENHA, MEU_TOKEN: nome, não valor (com dígito, VENDAS_2024, é valor)
            or bool(re.fullmatch(r"[\[(<{]\s*[^\])>}]{1,40}\s*[\])>}]", v))      # [SUA-SENHA], <senha>, (senha)
            or bool(re.fullmatch(r"(sua|seu|minha|meu|your|my|the)?[-_ ]?(senha|password|pass|passwd|pwd|secret|token|chave)"
                                 r"([-_ ]?(do|da|de|of)[-_ ]?(banco|usuario|usuário|projeto|acesso|sistema|db|database|user))?", v, re.I)))   # sua_senha, senha_do_banco


def secret_value(v, kind, sep):
    """kind: 'strong' (senha) ou 'weak' (token/chave); sep: '=' (posição de valor) ou ':' (texto livre)."""
    v = v.strip().strip("\"'")
    if is_placeholder(v) or NUMERIC_ID.match(v):
        return False
    if kind == "strong":
        if sep == "=":
            return len(v) >= 3                                  # PGPASSWORD=vendas: nessa posição é a senha
        return len(v) >= 4 and bool(re.search(r"[\d\W_]", v))   # "senha: solicitar ao TI" é texto; "senha: Abc123" não
    if "/" in v or (sep == ":" and re.fullmatch(r"[a-z]+|[a-z][a-z0-9]*(_[a-z0-9]+)+", v)):   # caminho; em texto livre, palavra ou identificador_com_sublinhado
        return False
    return len(v) >= 8 and bool(re.search(r"\d", v)) and bool(re.search(r"[A-Za-z]", v))


def name_kind(name):
    n = name.strip("-_.\"'")
    if not n or REF_NAME.search(n) or REF_PREFIX.search(n) or re.search(r"(?i)(expir|alterad|validade|venc|_at$|_em$|date|data$)", n):
        return ""
    if STRONG_NAME.search(n):
        return "strong"
    if WEAK_NAME.search(n):
        return "weak"
    return ""


def conn_secret(t):
    return any(not is_placeholder(m.group(2)) and len(m.group(2)) >= 3 for m in CONN.finditer(t))


def text_secret(t, field=""):
    if any(r.search(t) for r in SOFT_RX) or conn_secret(t):
        return True
    for m in KV.finditer(t):
        k = name_kind(m.group(1))
        if k and secret_value(m.group(2), k, "="):
            return True
    for m in URLKV.finditer(t):
        k = name_kind(m.group(1))
        if k and secret_value(m.group(2), k, "="):
            return True
    for m in COLON.finditer(t):
        k = name_kind(m.group(2))
        if k and secret_value(m.group(3), k, "=" if m.group(1) else ":"):     # "nome": valor (JSON) é posição de valor
            return True
    for m in PHRASE.finditer(t):
        k = name_kind(m.group(1)) or "weak"
        if not re.search(r"(?i)(expir|alterad|validade|venc|data)", m.group(2)) and secret_value(m.group(3), k, ":"):
            return True
    for m in IS_PHRASE.finditer(t):
        if secret_value(m.group(2), "strong", ":"):
            return True
    for m in SETX.finditer(t):
        k = name_kind(m.group(1))
        if k and secret_value(m.group(2), k, "="):
            return True
    for m in CLI_KEY.finditer(t):
        if secret_value(m.group(2), "weak", "=") or (not is_placeholder(m.group(2)) and len(m.group(2)) >= 12):
            return True
    rxs = CLI_PW + (CLI_PW_CMD if field in ("command", "args") else [])
    return any(not is_placeholder(m.group(m.lastindex)) and not is_placeholder(m.group(m.lastindex).rstrip(".,;:")) for rx in rxs for m in rx.finditer(t))


def looks_like_token(t, free_text):
    """Palavra longa, sem cara de caminho, com maiúscula, minúscula e dígito e 16+ letras: provável chave.
    Em texto livre (nota, descrição) exige também poucas vogais. Não vale para nome de ferramenta MCP,
    identificador numérico longo nem valor de identificador (planilha_id = ..., "spreadsheetId": "...", --sheet-id ...)."""
    for m in re.finditer(r"[^\s'\"]{40,}", t):
        w = m.group(0)
        if (w.startswith("mcp__") or re.search(r"[\\/]", w) or NUMERIC_ID.match(re.sub(r"^\w+[=:]", "", w))
                or re.search(r"(?i)id[\"']?\s*[=:]?\s*[\"']?\s*$", t[max(0, m.start() - 48):m.start()])):
            continue
        letters = re.sub(r"[^A-Za-z]", "", w)
        if len(letters) >= 16 and re.search(r"[A-Z]", w) and re.search(r"[a-z]", w) and re.search(r"\d", w):
            if not free_text or len(re.findall(r"[aeiouAEIOU]", letters)) / len(letters) < 0.35:
                return True
    return False


FREE_TEXT = {"note", "description", "name"}


def masked(t):
    """Trecho do campo para a pergunta, com as palavras que podem ser segredo mascaradas (Se•••23)."""
    t = re.sub(r"\s+", " ", t)[:90]
    return re.sub(r"[^\s'\",;:=@/()]{6,}", lambda m: m.group(0) if not re.search(r"\d", m.group(0)) and len(m.group(0)) < 14 else m.group(0)[:2] + "•••" + m.group(0)[-2:], t)


def soft_findings(obj, path="bancos", loose=False, key="", out=None):
    """Todos os achados prováveis: [(caminho, chave, trecho)]. A chave identifica o texto exato do campo (muda se o texto mudar)."""
    out = [] if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            soft_findings(v, f"{path}.{k}", loose or k in ("tables", "columns"), out=out, key=k if isinstance(k, str) else "")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            soft_findings(v, f"{path}[{i}]", loose, key, out)
    elif isinstance(obj, str):
        t = obj.strip()
        if conn_secret(t) or (not loose and (text_secret(t, key) or looks_like_token(t, key in FREE_TEXT))):
            out.append((path, hashlib.sha256((key + "\0" + t).encode("utf-8")).hexdigest()[:24], masked(t)))
    return out


def find_secret(obj, path="bancos", loose=False, hard_only=False, key=""):
    """Onde há senha ou chave ('' se nada). hard_only: só formatos inconfundíveis e usuario:senha@.
    Em nomes e descrições de tabelas (loose) valem só esses formatos, para não barrar nome comprido."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and not loose and SECRET_KEY.match(k.strip()) and v not in ("", None, False):
                return f"{path}.{k}"
            hit = find_secret(v, f"{path}.{k}", loose or k in ("tables", "columns"), hard_only, k if isinstance(k, str) else "")
            if hit:
                return hit
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hit = find_secret(v, f"{path}[{i}]", loose, hard_only, key)
            if hit:
                return hit
    elif isinstance(obj, str):
        t = obj.strip()
        if any(r.search(t) for r in SECRET_STRONG) or conn_secret(t):
            return path
        if not hard_only and not loose and (text_secret(t, key) or looks_like_token(t, key in FREE_TEXT)):
            return path
    return ""


def bad_env_names(dbs):
    """Campos keyEnv que não são um NOME de variável de ambiente (ex.: a própria chave colada)."""
    out = []
    for i, d in enumerate(dbs):
        a = d.get("access") if isinstance(d, dict) else None
        if not isinstance(a, dict) or a.get("method") != "http":
            continue                                   # o campo só existe (e só é usado) no acesso http
        v = a.get("keyEnv")
        if v not in (None, "") and not (isinstance(v, str) and ENV_NAME.match(v.strip())):
            out.append(f"bancos[{i}].access.keyEnv")
    return out


class ConfigError(Exception):
    pass


def friendly(e, data_dir):
    """Mensagem para o editor: erro de disco vira orientação em português."""
    if isinstance(e, OSError):
        return (f"Não consegui gravar na pasta de dados «{Path(data_dir).as_posix()}»: {e.strerror or e}. "
                "Inicie o servidor com --data apontando para uma pasta onde você possa gravar.")
    return str(e)


def slugify(s):
    import unicodedata
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "fluxo"


class Server(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"   # no Windows isso deixaria dois servidores na mesma porta, e o segundo diria que subiu


class Handler(BaseHTTPRequestHandler):
    catalog: Catalog = None
    port = 8765
    server_version = "SkillFlow/0.5.0"

    def log_message(self, fmt, *args):
        pass

    def _host_ok(self):
        return self.headers.get("Host", "") in {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 5_000_000:
            raise ValueError("corpo grande demais")
        return json.loads(self.rfile.read(n) or b"{}")

    def _guard(self, mutating):
        if not self._host_ok():
            self._send(403, {"error": "host não permitido"})
            return False
        if mutating and self.headers.get("X-Skill-Flow") != "1":
            self._send(403, {"error": "cabeçalho ausente"})
            return False
        return True

    def do_GET(self):
        if not self._guard(False):
            return
        u = urlparse(self.path)
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
            if u.path == "/api/catalog":
                return self._send(200, self.catalog.full())
            if u.path == "/api/flows":
                d = self.catalog.data_dir / "flows"
                names = sorted(p.stem for p in d.glob("*.json")) if d.is_dir() else []
                return self._send(200, names)
            if u.path == "/api/flow":
                name = slugify(parse_qs(u.query).get("name", [""])[0])
                p = self.catalog.data_dir / "flows" / f"{name}.json"
                if not p.is_file():
                    return self._send(404, {"error": "fluxo não existe"})
                return self._send(200, p.read_bytes())
            if u.path == "/api/ping":
                return self._send(200, {"app": "skill-flow", "pid": os.getpid(), "serverMtimeMs": STARTED_MS, "port": self.port})
            if u.path == "/api/runs":
                name = slugify(parse_qs(u.query).get("name", [""])[0])
                p = self.catalog.data_dir / "runs" / f"{name}.json"
                return self._send(200, p.read_bytes() if p.is_file() else b"[]")
            if u.path == "/api/section":
                q = parse_qs(u.query)
                occ = int((q.get("occ", ["0"])[0] or "0"))
                text = self.catalog.section_text(q.get("path", [""])[0], q.get("heading", [""])[0], occ)
                return self._send(200, {"text": text[:20000], "hash": chash(text), "full": len(text)})
        except PermissionError as e:
            return self._send(403, {"error": str(e)})
        except KeyError as e:
            return self._send(404, {"error": str(e)})
        except Exception as e:
            return self._send(500, {"error": str(e)})
        self._send(404, {"error": "não encontrado"})

    def do_PUT(self):
        if not self._guard(True):
            return
        u = urlparse(self.path)
        try:
            if u.path == "/api/flow":
                flow = self._body()
                slug = slugify(flow.get("name", "fluxo"))
                d = self.catalog.data_dir / "flows"
                d.mkdir(parents=True, exist_ok=True)
                write_atomic(d / f"{slug}.json", json.dumps(flow, ensure_ascii=False, indent=1))
                return self._send(200, {"slug": slug})
            if u.path == "/api/databases":
                self._body_cache = self._body()
                dbs = self._body_cache.get("databases")
                retired = self._body_cache.get("retired") or []
                if not isinstance(retired, list) or not all(isinstance(x, str) and len(x) <= 200 for x in retired):
                    return self._send(400, {"error": "lista de ids removidos inválida"})
                if not isinstance(dbs, list) or len(dbs) > 200 or not all(isinstance(x, dict) for x in dbs):
                    return self._send(400, {"error": "lista de bancos inválida"})
                if len(json.dumps(dbs, ensure_ascii=False)) > 1_000_000:
                    return self._send(400, {"error": "descrição dos bancos grande demais"})
                body = self._body_cache
                bad = find_secret(dbs, hard_only=True)
                if bad:
                    return self._send(400, {"error": f"Isto é uma senha ou chave ({bad}). Guarde-a numa variável de ambiente e informe só o NOME da variável."})
                conf = body.get("confirm") if isinstance(body.get("confirm"), list) else []
                acc0 = self.catalog._load_config().get("databasesAccepted")
                accepted = {x for x in (acc0 if isinstance(acc0, list) else []) if isinstance(x, str)} | {x for x in conf if isinstance(x, str)}
                found = soft_findings(dbs)
                pending = [(w, k, tr) for w, k, tr in found if k not in accepted]
                if pending:
                    def where_info(w):
                        m = re.match(r"bancos\[(\d+)\](.*)", w)
                        i = int(m.group(1)) if m else -1
                        nome = dbs[i].get("name") if 0 <= i < len(dbs) and isinstance(dbs[i], dict) else ""
                        return {"banco": nome if isinstance(nome, str) else "", "n": i + 1, "campo": (m.group(2) if m else w).lstrip(".")}
                    lst = ", ".join(w for w, _, _ in pending[:6]) + ("…" if len(pending) > 6 else "")
                    return self._send(422, {"soft": True, "findings": [dict(where=w, key=k, trecho=tr, **where_info(w)) for w, k, tr in pending],
                                            "error": f"Isto parece uma senha ou chave em: {lst}. Se for, guarde numa variável de ambiente e informe só o NOME da variável."})
                bad = bad_env_names(dbs)
                if bad:
                    return self._send(400, {"error": f"Em {bad[0]} informe só o NOME da variável de ambiente (ex.: MEU_BANCO_CHAVE), nunca a chave."})
                if len(json.dumps(dbs, ensure_ascii=False)) > 1_000_000:
                    return self._send(400, {"error": "descrição dos bancos grande demais"})
                with self.catalog.lock:
                    try:
                        cfg = self.catalog.config_for_write("config.antes-dos-bancos.json")
                    except ConfigError as e:
                        return self._send(409, {"error": f"O config.json tem um erro ({e}). Corrija o arquivo antes; nada foi gravado."})
                    cfg["databases"] = dbs
                    old = cfg.get("databasesRetired")
                    old = [x for x in old if isinstance(x, str)] if isinstance(old, list) else []
                    acc = cfg.get("databasesAccepted")
                    acc = [x for x in acc if isinstance(x, str)] if isinstance(acc, list) else []
                    cfg["databasesAccepted"] = list(dict.fromkeys(acc + [k for _, k, _ in found]))[-500:]   # textos liberados com "Salvar assim mesmo"
                    live = {d.get("id") for d in dbs}
                    cfg["databasesRetired"] = [x for x in dict.fromkeys(old + retired) if x not in live][-1000:]   # ids de bancos removidos: não voltam a ser usados
                    write_atomic(self.catalog.config_path, json.dumps(cfg, ensure_ascii=False, indent=2))
                return self._send(200, {"ok": True, "n": len(dbs)})
            if u.path == "/api/categories":
                m = self._body().get("map")
                if not isinstance(m, dict) or len(m) > 2000:
                    return self._send(400, {"error": "mapa de categorias inválido"})
                clean = {}
                for k, v in m.items():
                    if not (isinstance(k, str) and isinstance(v, str) and 0 < len(k) <= 200 and len(v) <= 120):
                        return self._send(400, {"error": "nome de skill ou categoria inválido"})
                    clean[k] = v.strip()
                with self.catalog.lock:
                    try:
                        cfg = self.catalog.config_for_write("config.antes-das-categorias.json")
                    except ConfigError as e:
                        return self._send(409, {"error": f"O config.json tem um erro ({e}). Corrija o arquivo antes; nada foi gravado."})
                    cats = dict(cfg.get("skillCategory", {}))
                    for k, v in clean.items():
                        if v:
                            cats[k] = v
                        else:
                            cats.pop(k, None)
                    cfg["skillCategory"] = cats
                    write_atomic(self.catalog.config_path, json.dumps(cfg, ensure_ascii=False, indent=2))
                return self._send(200, {"ok": True, "n": len(clean)})
            if u.path == "/api/runs":
                name = slugify(parse_qs(u.query).get("name", [""])[0])
                runs = self._body().get("runs")
                if not isinstance(runs, list) or len(runs) > 2000 or not all(isinstance(r, dict) for r in runs):
                    return self._send(400, {"error": "lista de execuções inválida"})
                d = self.catalog.data_dir / "runs"
                d.mkdir(parents=True, exist_ok=True)
                write_atomic(d / f"{name}.json", json.dumps(runs, ensure_ascii=False, indent=1))
                return self._send(200, {"slug": name, "n": len(runs)})
        except Exception as e:
            return self._send(500, {"error": friendly(e, self.catalog.data_dir)})
        self._send(404, {"error": "não encontrado"})

    def do_POST(self):
        if not self._guard(True):
            return
        u = urlparse(self.path)
        try:
            if u.path == "/api/shutdown":
                self._send(200, {"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if u.path == "/api/export":
                body = self._body()
                slug = slugify(body.get("name", "fluxo"))
                d = self.catalog.data_dir / "out" / f"fluxo-{slug}"
                d.mkdir(parents=True, exist_ok=True)
                write_atomic(d / "SKILL.md", body.get("markdown", ""))
                written = ["SKILL.md"]
                # arquivos extras na mesma pasta (ex.: registro-da-execucao.md): só nomes simples terminados em .md
                for fname, text in (body.get("files") or {}).items():
                    if (isinstance(fname, str) and isinstance(text, str) and fname != "SKILL.md" and not fname.startswith(".")
                            and re.fullmatch(r"[A-Za-z0-9._-]{1,80}\.md", fname)):
                        write_atomic(d / fname, text)
                        written.append(fname)
                return self._send(200, {"path": str(d / "SKILL.md").replace("\\", "/"), "dir": str(d).replace("\\", "/"), "files": written})
        except Exception as e:
            return self._send(500, {"error": friendly(e, self.catalog.data_dir)})
        self._send(404, {"error": "não encontrado"})

    def do_DELETE(self):
        if not self._guard(True):
            return
        u = urlparse(self.path)
        if u.path == "/api/flow":
            name = slugify(parse_qs(u.query).get("name", [""])[0])
            p = self.catalog.data_dir / "flows" / f"{name}.json"
            if p.is_file():
                p.unlink()
            return self._send(200, {"ok": True})
        self._send(404, {"error": "não encontrado"})


def check(data_dir):
    """Diagnóstico de instalação: Python, pasta de dados, onde estão as skills e os CLAUDE.md."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(f"Python {sys.version.split()[0]} ({sys.executable})")
    if sys.version_info < (3, 8):
        print("  ⚠ precisa de Python 3.8 ou mais novo")
    err = prepare_data_dir(data_dir)
    print(f"Pasta de dados: {data_dir} " + (f"⚠ {err}" if err else "(pode gravar)"))
    cat = Catalog(data_dir)
    roots = cat.skill_roots()
    print(f"Pastas de skills encontradas: {len(roots)}")
    for r in roots:
        print(f"  - {r}")
    full = cat.full()
    print(f"Skills: {len(full['skills'])} · CLAUDE.md: {len(full['claudeMd'])} · bancos descritos: {len(full['databases'])}")
    if not roots:
        print("  ⚠ nenhuma pasta de skills: ponha o caminho em skillRoots no config.json da pasta de dados")
    return 0


def prepare_data_dir(p):
    """Cria a pasta de dados, se preciso, e confirma que dá para gravar nela. Devolve '' ou a mensagem de erro."""
    try:
        p.mkdir(parents=True, exist_ok=True)
        probe = p / ".escrita-ok"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as e:
        return f"a pasta de dados «{p}» não aceita escrita ({e.strerror or e}). Use --data com outra pasta."
    return ""


def main():
    ap = argparse.ArgumentParser(description="Skill Flow: editor visual de fluxos de skills. Servidor local, só em 127.0.0.1.")
    ap.add_argument("--port", type=int, default=8765, help="porta local (padrão 8765)")
    ap.add_argument("--data", default=str(HOME / ".claude" / "skill-flows"),
                    help="pasta de dados: fluxos, execuções, saídas e config.json (padrão ~/.claude/skill-flows)")
    ap.add_argument("--check", action="store_true", help="mostra o que o servidor enxerga nesta máquina e sai")
    args = ap.parse_args()
    if not 1 <= args.port <= 65535:
        ap.error("--port deve estar entre 1 e 65535")
    data_dir = Path(args.data)
    if args.check:
        return check(data_dir)
    novo = not data_dir.exists()
    err = prepare_data_dir(data_dir)
    if err:
        print(f"Não consigo usar {err}", file=sys.stderr)
        return 1
    Handler.catalog = Catalog(data_dir)
    Handler.port = args.port
    try:
        srv = Server(("127.0.0.1", args.port), Handler)
    except (OSError, OverflowError) as e:
        print(f"Não consegui abrir a porta {args.port}: {getattr(e, 'strerror', None) or e}. "
              f"Outro Skill Flow (ou outro programa) pode estar usando essa porta: feche-o ou use --port {min(args.port + 1, 65535)}.", file=sys.stderr)
        return 1
    print(f"Skill Flow em http://127.0.0.1:{args.port}  (dados: {args.data})", flush=True)
    if novo:
        print(f"  Pasta de dados nova criada em {data_dir}.", flush=True)
    full = Handler.catalog.full()
    print(f"  {len(full['skills'])} skill(s) e {len(full['claudeMd'])} CLAUDE.md encontrados.", flush=True)
    if not full["skills"]:
        print("  Nenhuma skill encontrada: ponha pastas em skillRoots no config.json da pasta de dados ou rode com --check. "
              "Para ver o exemplo, rode a partir da raiz do repositório: python app/server.py --data examples/data", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())
