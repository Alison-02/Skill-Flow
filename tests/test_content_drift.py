"""Teste de ponta a ponta da detecção de mudança de conteúdo.

Cria uma skill de mentira numa pasta temporária, monta um fluxo apontando para ela, abre no Chrome
(fase 1: tudo confere), edita o arquivo da skill e abre de novo (fase 2: o editor tem de detectar).
Não toca nas suas skills nem na sua pasta de dados.

Uso: python tests/test_content_drift.py   (sai com 2 se não achar um navegador)
"""
import json
import sys
import time
import urllib.parse

from _helpers import Sandbox, find_chrome, selftest_result

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

V1 = """---
name: zz-teste
description: skill de teste
---
# Titulo

## Regras
linha A
linha B

## Passos
1. um
2. dois

## Outro
texto do outro

## Exemplo
primeiro exemplo

## Exemplo
segundo exemplo
"""


def main():
    chrome = find_chrome()
    if not chrome:
        print("Não achei Chrome, Chromium ou Edge. Instale um ou aponte a variável CHROME para o executável.")
        return 2
    with Sandbox() as sb:
        skill_dir = sb.tmp / "skills-zz" / "zz-teste"
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        skill.write_text(V1, encoding="utf-8")
        cfg_path = sb.data / "config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["skillRoots"] = [str(skill_dir.parent)]
        cfg["claudeMdFiles"] = []
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
            # reinicia o servidor para ler a configuração nova
        sb.api("POST", "/api/shutdown", {})
        sb.proc.wait(timeout=10)
        sb.start()

        _, cat = sb.api("GET", "/api/catalog")
        sk = next(s for s in cat["skills"] if s["name"] == "zz-teste")
        secs = {(x["title"], x["occ"]): x for x in sk["file"]["sections"]}

        def node(nid, kind, title, ref, x):
            n = {"id": nid, "kind": kind, "title": title, "sub": "teste", "x": x, "y": 100, "note": "", "ref": ref}
            q = "/api/section?path=%s&heading=%s&occ=%d" % (urllib.parse.quote(ref["path"], safe=""), urllib.parse.quote(ref.get("heading", ""), safe=""), ref.get("occ", 0))
            _, r = sb.api("GET", q)
            ref["hash"], ref["snap"], ref["baseAt"] = r["hash"], r["text"], "2026-10-01"
            return n

        def sec_ref(title, occ):
            c = secs[(title, occ)]
            return {"skill": "zz-teste", "invoke": "zz-teste", "path": sk["file"]["path"], "heading": title, "occ": occ,
                    "start": c["start"], "end": c["end"], "level": c["level"]}

        flow = {"name": "zz-teste", "description": "teste", "edges": [], "view": {"x": 40, "y": 40, "k": 1}, "nodes": [
            node("n_regras", "section", "Regras", sec_ref("Regras", 0), 0),
            node("n_passos", "section", "Passos", sec_ref("Passos", 0), 300),
            node("n_outro", "section", "Outro", sec_ref("Outro", 0), 600),
            node("n_ex2", "section", "Exemplo (2a)", sec_ref("Exemplo", 1), 900),
            node("n_skill", "skill", "zz-teste", {"skill": "zz-teste", "invoke": "zz-teste", "path": sk["file"]["path"]}, 1200),
        ]}
        sb.api("PUT", "/api/flow", flow)
        print("--- FASE 1 (arquivo igual ao da referência) ---")
        r1 = selftest_result(sb.chrome_dom(chrome, "selftest=2&phase=1", budget_ms=20000, timeout=120)) or "(sem resultado)"
        print(r1)

        v2 = (V1.replace("# Titulo\n", "Aviso novo antes de tudo.\n\n# Titulo\n").replace("linha B\n", "linha B alterada\n")
              .replace("## Passos\n", "## Passos novos\n").replace("## Exemplo\nprimeiro exemplo\n", "## Exemplo\nprimeiro exemplo editado\n"))
        skill.write_text(v2, encoding="utf-8", newline="\r\n")   # CRLF de propósito: não pode contar como mudança
        time.sleep(0.5)
        print("--- FASE 2 (arquivo editado; CRLF) ---")
        r2 = selftest_result(sb.chrome_dom(chrome, "selftest=2&phase=2", budget_ms=20000, timeout=120)) or "(sem resultado)"
        print(r2)

    lines = (r1 + "\n" + r2).splitlines()
    problems = [l for l in lines if l.startswith(("FAIL", "ERRO", "(sem"))]
    print(f"\nRESULTADO: {sum(1 for l in lines if l.startswith('PASS'))} PASS, {len(problems)} problema(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
