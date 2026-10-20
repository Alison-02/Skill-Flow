"""Gera as capturas de tela do README (docs/images/*.png) a partir dos exemplos, num Chrome sem janela.

Uso: python docs/make_screenshots.py     (precisa de Chrome, Chromium ou Edge; ou a variável CHROME)
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tests"))
from _helpers import Sandbox, find_chrome  # noqa: E402

SHOTS = [
    ("editor.png", "demo=1", "2300,800"),
    ("editor-inspector.png", "demo=sel", "2300,900"),
    ("db-queries.png", "demo=consultas&sel=1", "2300,900"),
]


def main():
    chrome = find_chrome()
    if not chrome:
        print("Não achei Chrome, Chromium ou Edge.")
        return 2
    out = HERE / "images"
    out.mkdir(exist_ok=True)
    with Sandbox() as sb:
        for name, query, size in SHOTS:
            target = (out / name).resolve()
            subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", f"--user-data-dir={sb.tmp / ('p-' + name)}",
                            f"--window-size={size}", "--force-device-scale-factor=1", "--virtual-time-budget=20000",
                            f"--screenshot={target}", f"{sb.base}/?{query}"], capture_output=True, timeout=180)
            print(("ok  " if target.exists() else "FALHOU ") + str(target.relative_to(HERE.parent)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
