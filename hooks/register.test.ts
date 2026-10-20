import { test, expect } from 'claude-code/testing'

// Um "mundo" de mentira: o servidor está de pé ou não, com o server.py de uma certa data;
// o disco tem o server.py de outra; o Python existe ou não; o sistema é Windows ou não.
type Opts = { up?: boolean; serverMtime?: number; diskMtime?: number; python?: boolean; win?: boolean; oldServer?: boolean }

function setup(on: any, o: Opts) {
  const w = { up: !!o.up, mtime: o.serverMtime ?? 1000, ran: [] as string[][], fetched: [] as string[], written: [] as { path: string; text: string }[] }
  const win = o.win ?? true
  on('env.get', async (_$: unknown, e: { name: string }) => ({ value: e.name === 'USERPROFILE' ? (win ? 'D:/dados/x' : undefined) : e.name === 'HOME' ? '/home/x' : undefined }))
  on('tool.list', async () => ({ value: [{ name: 'Read', description: 'Lê arquivo', mcp: false }] }))
  on('fs.write', async (_$: unknown, e: { path: string; text: string }) => {
    w.written.push({ path: e.path, text: e.text })
    return { value: undefined }
  })
  on('fs.stat', async () => ({ value: { kind: 'file', size: 1, mtimeMs: o.diskMtime ?? 1000, isLink: false } }))
  on('clock.sleep', async () => ({ value: undefined }))
  on('http.fetch', async (_$: unknown, e: { url: string }) => {
    w.fetched.push(e.url)
    if (e.url.endsWith('/api/shutdown')) {
      w.up = false
      return { value: { status: 200, ok: true, headers: {}, text: '{"ok":true}' } }
    }
    if (e.url.endsWith('/api/ping')) {
      if (!w.up) throw new Error('recusado')
      return { value: { status: 200, ok: true, headers: {}, text: JSON.stringify({ app: 'skill-flow', serverMtimeMs: w.mtime }) } }
    }
    if (e.url.endsWith('/api/flows')) {
      if (!(w.up || o.oldServer)) throw new Error('recusado')
      return { value: { status: 200, ok: true, headers: {}, text: '[]' } }
    }
    throw new Error('url inesperada ' + e.url)
  })
  on('process.run', async (_$: unknown, e: { argv: readonly string[] }) => {
    const a = [...e.argv]
    w.ran.push(a)
    if (a.includes('-c') && /sys\.version_info/.test(a.join(' '))) {
      return { value: o.python === false ? { exitCode: 9009, stdout: '', stderr: 'sem python' } : { exitCode: 0, stdout: '3\n', stderr: '' } }
    }
    if (a[0] === 'powershell' || a[0] === 'sh') {
      w.up = true   // iniciar o servidor desvinculado o põe de pé
      w.mtime = o.diskMtime ?? 1000
    }
    return { value: { exitCode: 0, stdout: '', stderr: '' } }
  })
  return w
}

const run = ($: any) => $.command.run({ command: 'skill-flow', args: '', origin: { kind: 'user' }, presentation: {} } as never)

test('servidor já de pé e atual: só grava as ferramentas e abre o navegador (nada é iniciado)', async ($, on) => {
  const w = setup(on, { up: true })
  const out = await run($)
  expect(JSON.stringify(out)).toContain('http://127.0.0.1:8765/')
  expect(w.written[0]?.path).toContain('tools.json')
  expect(w.written[0]?.text).toContain('"name":"Read"')
  expect(w.ran.some(a => a[0] === 'powershell')).toBe(false)
  expect(w.ran.some(a => a[0] === 'cmd' && a.includes('http://127.0.0.1:8765/'))).toBe(true)
})

test('servidor parado no Windows: acha o Python, inicia desvinculado (Start-Process) e abre', async ($, on) => {
  const w = setup(on, { up: false })
  const out = await run($)
  const ps = w.ran.find(a => a[0] === 'powershell')
  expect(ps?.join(' ')).toContain('Start-Process')
  expect(ps?.join(' ')).toContain('server.py')
  expect(ps?.join(' ')).toContain('-WindowStyle Hidden')
  expect(JSON.stringify(out)).toContain('Skill Flow aberto')
  expect(w.ran.some(a => a[0] === 'cmd')).toBe(true)
})

test('fora do Windows: usa python3, nohup e xdg-open/open', async ($, on) => {
  const w = setup(on, { up: false, win: false })
  const out = await run($)
  expect(w.ran.some(a => a[0] === 'python3')).toBe(true)
  expect(w.ran.some(a => a[0] === 'sh' && a.join(' ').includes('nohup'))).toBe(true)
  expect(w.ran.some(a => a[0] === 'open')).toBe(true)
  expect(w.ran.some(a => a[0] === 'cmd' || a[0] === 'powershell')).toBe(false)
  expect((w.written[0]?.path || '').replace(/\\/g, '/')).toContain('/home/x/.claude/skill-flows/')
  expect(JSON.stringify(out)).toContain('Skill Flow aberto')
})

test('sem Python: explica como instalar e não abre nada', async ($, on) => {
  const w = setup(on, { up: false, python: false })
  const out = await run($)
  expect(JSON.stringify(out)).toContain('Python 3')
  expect(w.ran.some(a => a[0] === 'powershell' || a[0] === 'cmd')).toBe(false)
})

test('servidor de pé mas com server.py antigo: desliga e inicia o novo', async ($, on) => {
  const w = setup(on, { up: true, serverMtime: 1000, diskMtime: 9000 })
  const out = await run($)
  expect(w.fetched.some(u => u.endsWith('/api/shutdown'))).toBe(true)
  expect(w.ran.some(a => a[0] === 'powershell')).toBe(true)
  expect(JSON.stringify(out)).toContain('Skill Flow aberto')
})

test('servidor de uma versão sem /api/ping: avisa em vez de brigar pela porta', async ($, on) => {
  const w = setup(on, { up: false, oldServer: true })
  const out = await run($)
  expect(JSON.stringify(out)).toContain('versão anterior')
  expect(w.ran.some(a => a[0] === 'powershell')).toBe(false)
})
