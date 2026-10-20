"""Utilidades comuns dos testes: servidor isolado, Chrome sem janela e a pasta de exemplos copiada para um lugar temporário.

Os testes nunca tocam na sua pasta pessoal: o servidor roda com HOME, USERPROFILE, APPDATA e LOCALAPPDATA
apontando para uma pasta temporária, então só enxerga as skills de `examples/`.
"""
import html
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
EXAMPLES = ROOT / "examples"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def find_chrome():
    """Chrome, Chromium ou Edge: variável CHROME, caminhos comuns ou o PATH. None se não achar."""
    env = os.environ.get("CHROME")
    if env and Path(env).exists():
        return env
    common = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    for c in common:
        if Path(c).exists():
            return c
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    return None


class Sandbox:
    """Pasta temporária com uma cópia de `examples/` e um servidor do Skill Flow rodando sobre ela."""

    def __init__(self, data="examples/data", extra_config=None):
        self.tmp = Path(tempfile.mkdtemp(prefix="skillflow-test-"))
        shutil.copytree(EXAMPLES, self.tmp / "examples")
        self.data = self.tmp / data
        if extra_config is not None:
            cfg_path = self.data / "config.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg.update(extra_config)
            cfg_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        home = self.tmp / "home"
        self.env = dict(os.environ, USERPROFILE=str(home), HOME=str(home), APPDATA=str(self.tmp / "appdata"),
                        LOCALAPPDATA=str(self.tmp / "localappdata"), XDG_CONFIG_HOME=str(self.tmp / "xdg"))
        self.proc = None

    def start(self):
        self.proc = subprocess.Popen([sys.executable, str(APP / "server.py"), "--port", str(self.port), "--data", str(self.data)],
                                     env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                urllib.request.urlopen(f"{self.base}/api/ping", timeout=2).read()
                return self
            except Exception:
                time.sleep(0.25)
        raise RuntimeError("o servidor não subiu")

    def api(self, method, path, body=None):
        req = urllib.request.Request(self.base + path, method=method, headers={"X-Skill-Flow": "1", "Content-Type": "application/json"},
                                     data=json.dumps(body).encode("utf-8") if body is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def chrome_dom(self, chrome, query, budget_ms=90000, size="1700,1000", timeout=300):
        prof = self.tmp / f"chrome-profile-{int(time.time() * 1000)}"
        out = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={prof}",
                              f"--window-size={size}", f"--virtual-time-budget={budget_ms}", "--dump-dom", f"{self.base}/?{query}"],
                             capture_output=True, timeout=timeout).stdout.decode("utf-8", "replace")
        return out

    def stop(self):
        try:
            if self.proc and self.proc.poll() is None:
                try:
                    self.api("POST", "/api/shutdown", {})
                except Exception:
                    pass
                self.proc.terminate()
                self.proc.wait(timeout=10)
        finally:
            shutil.rmtree(self.tmp, ignore_errors=True)

    def __enter__(self):
        return self.start()

    def __exit__(self, *a):
        self.stop()


def selftest_result(dom, element="selftest"):
    """Texto do <pre id="selftest"> que a página escreve quando termina."""
    m = re.search(rf'<pre id="{element}"[^>]*>(.*?)</pre>', dom, re.S)
    return html.unescape(m.group(1)) if m else None
