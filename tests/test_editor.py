"""Autoteste do editor: abre a página com ?selftest=1 num Chrome sem janela e confere o resultado.

A página simula mouse e teclado sobre um fluxo de exemplo e confere centenas de comportamentos
(conexões, ramos, laços, subfluxos, parâmetros, consulta a banco, geração do SKILL.md, desfazer...).

Uso:
    python tests/test_editor.py          # precisa de Chrome, Chromium ou Edge (ou a variável CHROME)

Sai com 0 se tudo passou, 1 se algo falhou e 2 se não achou um navegador.
"""
import sys

from _helpers import Sandbox, find_chrome, selftest_result

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    chrome = find_chrome()
    if not chrome:
        print("Não achei Chrome, Chromium ou Edge. Instale um ou aponte a variável CHROME para o executável.")
        return 2
    with Sandbox() as sb:
        dom = sb.chrome_dom(chrome, "selftest=1")
    res = selftest_result(dom)
    if res is None:
        print("A página não devolveu resultado (timeout ou erro de carregamento).")
        return 1
    lines = res.splitlines()
    for line in lines:
        if line.startswith(("FAIL", "ERRO", "SKIP", "INFO")):
            print(line)
    passed = sum(1 for l in lines if l.startswith("PASS"))
    problems = [l for l in lines if l.startswith(("FAIL", "ERRO"))]
    print(f"\nRESULTADO: {passed} PASS, {len(problems)} problema(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
