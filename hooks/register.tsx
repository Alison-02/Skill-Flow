import type { EngineInterface, Register } from 'claude-code'

// Atalho do editor de fluxos: o canvas roda num servidor local (app/server.py,
// só em 127.0.0.1) e abre no navegador. Este módulo só liga as pontas:
//   1. grava a lista de ferramentas do Claude para o editor oferecer como nós;
//   2. sobe o servidor, se ainda não estiver de pé, SEM amarrá-lo ao mod: ele
//      continua de pé quando o mod recarrega (antes caía a cada edição);
//   3. se o servidor de pé for de uma versão anterior do server.py, reinicia;
//   4. abre a página.
// Funciona no Windows, no macOS e no Linux; precisa de Python 3 instalado.
const PORT = 8765
const BASE = `http://127.0.0.1:${PORT}`
const HEADERS = { 'X-Skill-Flow': '1' }

type Ping = { app?: string; serverMtimeMs?: number } | null

async function ping($: EngineInterface): Promise<Ping> {
  try {
    const r = await $.http.fetch(`${BASE}/api/ping`, { headers: HEADERS })
    if (!r.ok) return null
    const j = JSON.parse(r.text)
    return j && j.app === 'skill-flow' ? j : null
  } catch {
    return null
  }
}

// Um servidor de uma versão antiga (sem /api/ping) responde em /api/flows.
async function oldServerUp($: EngineInterface): Promise<boolean> {
  try {
    return (await $.http.fetch(`${BASE}/api/flows`, { headers: HEADERS })).ok
  } catch {
    return false
  }
}

async function isWindows($: EngineInterface): Promise<boolean> {
  return !!(await $.env.get('USERPROFILE'))
}

async function findPython($: EngineInterface, win: boolean): Promise<string[] | null> {
  const candidates = win ? [['python'], ['py', '-3'], ['python3']] : [['python3'], ['python']]
  for (const c of candidates) {
    try {
      const r = await $.process.run([...c, '-c', 'import sys;print(sys.version_info[0])'], { timeoutMs: 8000 })
      if (r.exitCode === 0 && r.stdout.trim() === '3') return c
    } catch {
      // próximo candidato
    }
  }
  return null
}

async function writeTools($: EngineInterface): Promise<number> {
  const home = (await $.env.get('USERPROFILE')) || (await $.env.get('HOME'))
  const tools = await $.tool.list()
  const slim = tools.map(t => ({ name: t.name, description: (t.description || '').slice(0, 200), mcp: t.mcp }))
  await $.fs.write(`${home}/.claude/skill-flows/tools.json`, JSON.stringify(slim))
  return slim.length
}

// O servidor é iniciado por um processo que termina logo, então não morre com o mod.
async function startDetached($: EngineInterface, py: string[], win: boolean): Promise<void> {
  const server = `${$.plugin.root}/app/server.py`
  const args = [...py.slice(1), server, '--port', String(PORT)]
  if (win) {
    const q = (t: string) => `'${t.replace(/'/g, "''")}'`
    const list = args.map(a => (/\s/.test(a) ? q(`"${a}"`) : q(a))).join(',')
    await $.process.run(
      ['powershell', '-NoProfile', '-NonInteractive', '-Command', `Start-Process -FilePath ${q(py[0])} -ArgumentList ${list} -WindowStyle Hidden`],
      { timeoutMs: 20000 },
    )
  } else {
    await $.process.run(['sh', '-c', 'nohup "$@" >/dev/null 2>&1 &', 'sh', py[0], ...args], { timeoutMs: 10000 })
  }
}

// Plano B, se o desvinculado não subir: o servidor passa a viver (e morrer) com o mod, como na versão anterior.
function startBound($: EngineInterface, py: string[]) {
  void (async () => {
    const server = $.process.spawn({ argv: [...py, `${$.plugin.root}/app/server.py`, '--port', String(PORT)] })
    for await (const piece of server) {
      if (piece.stream === 'stderr') $.ui.log(`skill-flow: ${piece.text}`, { to: 'debug' })
    }
  })()
}

async function waitUp($: EngineInterface, tries: number): Promise<Ping> {
  for (let i = 0; i < tries; i++) {
    const p = await ping($)
    if (p) return p
    await $.clock.sleep(500)
  }
  return null
}

async function openBrowser($: EngineInterface, win: boolean): Promise<void> {
  const url = `${BASE}/`
  if (win) {
    await $.process.run(['cmd', '/c', 'start', '', url])
    return
  }
  try {
    await $.process.run(['open', url])
  } catch {
    await $.process.run(['xdg-open', url])
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'skill-flow',
      description: 'Abre o editor visual de fluxos de skills no navegador',
    })
    return next(e)
  })

  on('command.run', { command: 'skill-flow' }, async $ => {
    const win = await isWindows($)
    const count = await writeTools($)
    let up = await ping($)

    // servidor de pé, mas com um server.py mais antigo que o do disco: reinicia
    if (up) {
      let disk = 0
      try {
        disk = (await $.fs.stat(`${$.plugin.root}/app/server.py`)).mtimeMs
      } catch {
        disk = 0
      }
      if (disk && Math.abs((up.serverMtimeMs || 0) - disk) > 1500) {
        try {
          await $.http.fetch(`${BASE}/api/shutdown`, { method: 'POST', headers: HEADERS, body: '{}' })
        } catch {
          // já caiu
        }
        for (let i = 0; i < 10 && (await ping($)); i++) await $.clock.sleep(300)
        up = await ping($)
      }
    } else if (await oldServerUp($)) {
      return {
        text: `Há um servidor de uma versão anterior do Skill Flow na porta ${PORT}, que não sei reiniciar sozinho. Feche o processo do Python que escuta nessa porta (ou reinicie o Claude) e rode /skill-flow de novo.`,
      }
    }

    if (!up) {
      const py = await findPython($, win)
      if (!py) {
        return {
          text: win
            ? 'Não achei o Python 3. Instale em python.org (marque "Add python to PATH") ou pela Microsoft Store e rode /skill-flow de novo.'
            : 'Não achei o Python 3 (python3). Instale-o e rode /skill-flow de novo.',
        }
      }
      try {
        await startDetached($, py, win)
      } catch {
        // cai no plano B abaixo
      }
      up = await waitUp($, 12)
      if (!up) {
        startBound($, py)
        up = await waitUp($, 12)
      }
      if (!up) {
        return { text: `Não consegui iniciar o servidor do Skill Flow. Teste à mão: ${py.join(' ')} "${$.plugin.root}/app/server.py"` }
      }
    }

    await openBrowser($, win)
    return { text: `Skill Flow aberto em ${BASE}/ (${count} ferramentas disponíveis como nós).` }
  })
}
