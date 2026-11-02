import { useEffect, useState } from 'react'
import { download, localFetch, post, request, type DiagnosticKind, type Prepared, type Result, type Task } from './api'

type Page = 'home' | 'storage' | 'process' | 'network' | 'labs' | 'history' | 'tech'
type ResultView = 'client' | 'technical'
type CatalogEntry = { id: string; module: string; type: string; source: string; read_only?: boolean }
type Item = { kind: DiagnosticKind; title: string; description: string; icon: string }
type FileEvidence = { path?: string; name?: string; bytes?: number; modified?: string; captured?: string; date_used?: string; pid?: number; created?: number; status?: string; rss_bytes?: number }

const modules: Record<'storage' | 'process' | 'network', { title: string; subtitle: string; icon: string; items: Item[] }> = {
  storage: {
    title: 'Almacenamiento', subtitle: 'Espacio, fotos y archivos perdidos', icon: '▧', items: [
      { kind: 'storage-space', title: 'Me estoy quedando sin espacio', description: 'Mide capacidad, inodos, papelera y archivos grandes.', icon: '01' },
      { kind: 'storage-photo', title: 'No encuentro una foto o video', description: 'Busca por nombre, formato, tamaño y fecha aproximada.', icon: '02' },
      { kind: 'storage-file', title: 'No encuentro un archivo', description: 'Busca por ruta, tipo, fecha o texto en documentos pequeños.', icon: '03' },
    ],
  },
  process: {
    title: 'Procesos', subtitle: 'Rendimiento, aplicaciones y temperatura', icon: '◈', items: [
      { kind: 'process-slow', title: 'Mi computadora está lenta', description: 'Muestreo de CPU, memoria, intercambio y disco durante 10 segundos.', icon: '01' },
      { kind: 'process-frozen', title: 'Una aplicación se quedó congelada', description: 'Identifica procesos asociados; tú decides si cerrar.', icon: '02' },
      { kind: 'process-heat', title: 'El equipo se calienta o hace ruido', description: 'Mide carga sostenida y sensores disponibles.', icon: '03' },
    ],
  },
  network: {
    title: 'Redes', subtitle: 'Conectividad, velocidad y páginas', icon: '⌁', items: [
      { kind: 'network-offline', title: 'No tengo conexión', description: 'Revisa interfaz, IP, ruta, DNS y salida exterior.', icon: '01' },
      { kind: 'network-slow', title: 'Internet está lento', description: 'Mide tráfico y latencia de prueba durante 10 segundos.', icon: '02' },
      { kind: 'network-page', title: 'Una página no abre', description: 'Comprueba DNS, conexión y respuesta HTTP o HTTPS.', icon: '03' },
    ],
  },
}

const nav: { id: Page; label: string; icon: string }[] = [
  { id: 'home', label: 'Inicio', icon: '⌂' },
  { id: 'storage', label: 'Almacenamiento', icon: '▧' },
  { id: 'process', label: 'Procesos', icon: '◈' },
  { id: 'network', label: 'Redes', icon: '⌁' },
  { id: 'labs', label: 'Pruebas', icon: '◇' },
  { id: 'history', label: 'Historial', icon: '◷' },
  { id: 'tech', label: 'Herramientas del técnico', icon: '⌘' },
]

const formatBytes = (n: number) => `${(n / 1024 / 1024).toFixed(1)} MiB`
const labelKind = (kind: string) => kind === 'full-scan' ? 'FULL SCAN' : Object.values(modules).flatMap(m => m.items).find(i => i.kind === kind)?.title || kind
const terminal = (status: string) => ['complete', 'cancelled', 'failed'].includes(status)

function PhotoThumb({ taskId, path, token }: { taskId: string; path: string; token: string }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    let local = ''
    let active = true
    localFetch(`/tasks/${taskId}/thumbnail?path=${encodeURIComponent(path)}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.blob() : Promise.reject()).then(blob => {
        if (active && blob.type.startsWith('image/')) { local = URL.createObjectURL(blob); setUrl(local) }
      }).catch(() => {})
    return () => { active = false; if (local) URL.revokeObjectURL(local) }
  }, [taskId, path, token])
  return url ? <img className="thumb" src={url} alt="Vista previa del archivo" /> : <div className="thumb thumb-placeholder">▧</div>
}

function Evidence({ task, token, onError }: { task: Task; token: string; onError: (message: string) => void }) {
  const items = task.result?.evidence || []
  const [page, setPage] = useState(0)
  const [sort, setSort] = useState<'name' | 'size' | 'date'>('name')
  if (!items.length) return null
  if (task.kind === 'full-scan') return <div className="subresults">{items.map((item, index) => {
    const part = item as { kind: string; result: Result }
    return <article className="subresult" key={index}><p className="eyebrow">{labelKind(part.kind)}</p><h3>{part.result.summary}</h3>
      <DataList title="Mediciones" data={part.result.measurements} /><DataList title="Hallazgos" data={part.result.findings} />
      <DataList title="Limitaciones" data={part.result.limitations} /></article>
  })}</div>
  if (task.kind === 'storage-photo' || task.kind === 'storage-file') {
    const ordered = [...items] as FileEvidence[]
    ordered.sort((a, b) => sort === 'size' ? (b.bytes || 0) - (a.bytes || 0) : sort === 'date' ? String(b.captured || b.modified || '').localeCompare(String(a.captured || a.modified || '')) : String(a.name || '').localeCompare(String(b.name || ''), 'es'))
    const pages = Math.max(1, Math.ceil(ordered.length / 24))
    return <><div className="file-controls"><label>Ordenar <select value={sort} onChange={e => { setSort(e.target.value as typeof sort); setPage(0) }}><option value="name">Nombre</option><option value="size">Tamaño</option><option value="date">Fecha de modificación</option></select></label><span>Página {Math.min(page + 1, pages)} de {pages}</span></div><div className={task.kind === 'storage-photo' ? 'gallery' : 'file-list'}>
    {ordered.slice(page * 24, page * 24 + 24).map((entry, index) => {
      const file = entry as FileEvidence
      if (!file.path) return null
      return <article className="file-card" key={index}>
        {task.kind === 'storage-photo' && index < 12 && /\.(png|jpe?g|gif|webp)$/i.test(file.path) && <PhotoThumb taskId={task.id} path={file.path} token={token} />}
        <div className="file-info"><strong>{file.name}</strong><small>{file.path}</small><span>{file.bytes !== undefined ? formatBytes(file.bytes) : ''} · {file.captured ? `Captura ${file.captured}` : file.modified ? `Modificado ${new Date(file.modified).toLocaleDateString('es')}` : ''}</span></div>
        <button className="text-button" onClick={() => download(`/tasks/${task.id}/file?path=${encodeURIComponent(file.path!)}`, token, file.name || 'archivo').catch(e => onError(e.message))}>Descargar ↗</button>
      </article>
    })}
  </div><div className="pagination"><button className="secondary" disabled={page <= 0} onClick={() => setPage(page - 1)}>← Anterior</button><button className="secondary" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>Siguiente →</button></div></>
  }
  return <DataList title="Evidencia" data={items} />
}

function DataList({ title, data }: { title: string; data?: unknown[] }) {
  if (!data?.length) return null
  return <div className="data-section"><h4>{title}</h4><div className="data-list">{data.map((entry, index) => <div className="data-row" key={index}>
    {typeof entry === 'string' ? entry : <code>{JSON.stringify(entry, null, 2)}</code>}
  </div>)}</div></div>
}

function ClientResult({ task }: { task: Task }) {
  const result = task.result
  if (!result) return null
  const findings = result.findings || []
  const evidence = (result.evidence || []).filter((item): item is FileEvidence => typeof item === 'object' && item !== null && ('path' in item || 'name' in item))
  const facts = (result.measurements || []).flatMap(item => {
    if (!item || typeof item !== 'object') return []
    return Object.entries(item as Record<string, unknown>)
      .filter(([key]) => !key.endsWith('_bytes') && !['interfaces', 'default_route', 'dns_servers', 'temperatures_celsius'].includes(key))
      .map(([key, value]) => `${key.replaceAll('_', ' ')}: ${typeof value === 'number' ? value.toFixed(2) : String(value)}`)
  })
  return <div className="client-result">
    <div className="client-summary"><span className="client-icon">✓</span><div><strong>{findings.length ? 'Se encontraron señales para revisar' : 'No se encontraron señales críticas'}</strong><p>{result.summary}</p></div></div>
    {findings.length > 0 && <div className="problem-alert" role="alert"><span aria-hidden="true">⚠</span><div><strong>Problema encontrado</strong><p>{findings[0]}</p></div></div>}
    <MetricCards measurements={result.measurements} />
    {facts.length > 0 && <div className="quick-facts"><h4>Lo más importante</h4>{facts.slice(0, 8).map((line, i) => <p key={i}>{line}</p>)}</div>}
    {evidence.length > 0 && <div className="quick-facts"><h4>Elementos encontrados</h4>{evidence.slice(0, 8).map((item, i) => <p key={i}><strong>{item.name || item.path || item.pid || 'Elemento'}</strong>{item.bytes !== undefined ? ` · ${formatBytes(item.bytes)}` : item.rss_bytes !== undefined ? ` · RAM ${formatBytes(item.rss_bytes)}` : ''}</p>)}</div>}
    {result.limitations?.length ? <p className="client-limitations">Límites del análisis: {result.limitations[0]}</p> : null}
  </div>
}

function MetricCards({ measurements }: { measurements?: unknown[] }) {
  const volumes = (measurements || []).filter((x): x is { volume: string; percent: number; free_bytes: number } => typeof x === 'object' && x !== null && 'volume' in x && 'percent' in x)
  const cpu = (measurements || []).find((x): x is { cpu_percent_by_core: number[]; memory_available_bytes: number } => typeof x === 'object' && x !== null && 'cpu_percent_by_core' in x)
  if (!volumes.length && !cpu) return null
  return <div className="metric-grid">{volumes.map(v => <div className="metric-card" key={v.volume}><small>VOLUMEN {v.volume}</small><strong>{v.percent.toFixed(1)}% ocupado</strong><div className="metric-track"><progress aria-label={`Ocupación de ${v.volume}`} value={v.percent} max={100} /></div><p>{formatBytes(v.free_bytes)} disponibles</p></div>)}{cpu && <><div className="metric-card"><small>CARGA MEDIA / NÚCLEO</small><strong>{(cpu.cpu_percent_by_core.reduce((a, b) => a + b, 0) / cpu.cpu_percent_by_core.length).toFixed(1)}%</strong><div className="metric-track"><progress aria-label="Uso medio de CPU" value={cpu.cpu_percent_by_core.reduce((a, b) => a + b, 0) / cpu.cpu_percent_by_core.length} max={100} /></div><p>Muestra de diez segundos</p></div><div className="metric-card"><small>MEMORIA DISPONIBLE</small><strong>{formatBytes(cpu.memory_available_bytes)}</strong><p>Medición actual del sistema</p></div></>}</div>
}

export default function App() {
  const [page, setPage] = useState<Page>('home')
  const [token, setToken] = useState('')
  const [code, setCode] = useState('')
  const [health, setHealth] = useState<'checking' | 'ready' | 'offline' | 'incompatible'>('checking')
  const [capabilities, setCapabilities] = useState<{ distribution: string; distribution_version: string; initially_supported: boolean; network_manager_available: boolean } | null>(null)
  const [permission, setPermission] = useState<'checking' | 'granted' | 'prompt' | 'denied'>('checking')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [selected, setSelected] = useState<DiagnosticKind | null>(null)
  const [params, setParams] = useState<Record<string, string | boolean>>({})
  const [task, setTask] = useState<Task | null>(null)
  const [prepared, setPrepared] = useState<Prepared | null>(null)
  const [actionTarget, setActionTarget] = useState('')
  const [history, setHistory] = useState<{ id: string; kind: string; status: string; created: string; summary: string }[]>([])
  const [labs, setLabs] = useState<Record<string, unknown>>({})
  const [techConfigured, setTechConfigured] = useState(false)
  const [techPassword, setTechPassword] = useState('')
  const [techUnlocked, setTechUnlocked] = useState(false)
  const [scriptName, setScriptName] = useState('')
  const [scriptSource, setScriptSource] = useState('print("Hola desde X-Scanner")')
  const [scriptOutput, setScriptOutput] = useState('')
  const [resultView, setResultView] = useState<ResultView>('client')
  const [actionState, setActionState] = useState<'idle' | 'working' | 'success'>('idle')
  const [scripts, setScripts] = useState<string[]>([])
  const [catalog, setCatalog] = useState<CatalogEntry[]>([])
  const [catalogItem, setCatalogItem] = useState<CatalogEntry | null>(null)
  const [catalogSource, setCatalogSource] = useState('')
  const [catalogModule, setCatalogModule] = useState('storage')
  const [catalogName, setCatalogName] = useState('')

  async function checkHealth() {
    request<{ service: string; api_version: number }>('/health').then(r => {
      setHealth(r.service === 'xscanner-local-agent' && r.api_version === 1 ? 'ready' : 'incompatible')
    }).catch(() => setHealth('offline'))
  }

  useEffect(() => {
    if (!navigator.permissions?.query) { setPermission('prompt'); return }
    navigator.permissions.query({ name: 'loopback-network' as PermissionName }).then(status => {
      setPermission(status.state)
      if (status.state === 'granted') checkHealth()
      status.addEventListener('change', () => {
        setPermission(status.state)
        if (status.state === 'granted') checkHealth()
      })
    }).catch(() => setPermission('prompt'))
  }, [])

  useEffect(() => {
    if (!token || !task || terminal(task.status)) return
    const timer = window.setInterval(() => request<Task>(`/tasks/${task.id}`, token).then(setTask).catch(e => setError(e.message)), 700)
    return () => window.clearInterval(timer)
  }, [token, task?.id, task?.status])

  useEffect(() => {
    if (!token || page !== 'history') return
    request<typeof history>('/tasks', token).then(setHistory).catch(e => setError(e.message))
  }, [page, token, task?.status])

  useEffect(() => {
    if (!token || page !== 'labs') return
    request<Record<string, unknown>>('/labs', token).then(setLabs).catch(e => setError(e.message))
  }, [page, token])

  useEffect(() => {
    if (!token || page !== 'tech') return
    request<{ configured: boolean }>('/technician/status', token).then(r => setTechConfigured(r.configured)).catch(e => setError(e.message))
  }, [page, token])

  function select(item: DiagnosticKind) {
    setSelected(item)
    setParams(item === 'network-page' ? { url: 'http://127.0.0.1:8766/' } : {})
    setTask(null)
    setPrepared(null)
    setError('')
    setMessage('')
    setResultView('client')
  }

  async function run(kind = selected, values = params) {
    if (!kind || !token) return
    setError(''); setMessage(''); setPrepared(null)
    try {
      const submitted: Record<string, unknown> = { ...values }
      if (values.min_mib) submitted.min_bytes = Number(values.min_mib) * 1024 * 1024
      if (values.max_mib) submitted.max_bytes = Number(values.max_mib) * 1024 * 1024
      delete submitted.min_mib
      delete submitted.max_mib
      const response = await post<Task>('/tasks', token, { kind, params: submitted })
      setTask(response)
      setSelected(kind)
      setResultView('client')
    } catch (e) { setError((e as Error).message) }
  }

  async function pair() {
    setError('')
    try {
      const response = await post<{ token: string }>('/pair', undefined, { code })
      setToken(response.token)
      request<typeof capabilities>('/capabilities', response.token).then(setCapabilities).catch(() => {})
      setCode('')
      setMessage('Complemento vinculado. Los diagnósticos se ejecutan en esta computadora.')
    } catch (e) { setError((e as Error).message) }
  }

  async function prepareAction(kind: string, target?: string) {
    if (!task || !token) return
    try {
      setError('')
      const response = await post<Prepared>('/actions/prepare', token, { task_id: task.id, kind, target: target || undefined })
      setPrepared(response)
    } catch (e) { setError((e as Error).message) }
  }

  async function executeAction() {
    if (!prepared || !token) return
    setActionState('working')
    try {
      const response = await post<{ message: string }>('/actions/execute', token, { token: prepared.token })
      await new Promise(resolve => window.setTimeout(resolve, 2000))
      setPrepared(null)
      setActionState('success')
      setMessage(`${response.message}. Ejecuta de nuevo el diagnóstico para comparar.`)
    } catch (e) { setError((e as Error).message); setPrepared(null); setActionState('idle') }
  }

  async function lab(kind: string, operation: 'start' | 'restore') {
    try {
      setError('')
      await post(`/labs/${kind}/${operation}`, token)
      setLabs(await request<Record<string, unknown>>('/labs', token))
      setMessage(operation === 'start' ? 'Prueba creada. Ejecuta el diagnóstico correspondiente.' : 'Recursos de la prueba restaurados.')
    } catch (e) { setError((e as Error).message) }
  }

  async function loadScripts() {
    if (!token || !techUnlocked) return
    try { setScripts(await request<string[]>('/technician/scripts', token)) } catch (e) { setError((e as Error).message) }
  }

  useEffect(() => {
    if (!token || !techUnlocked || page !== 'tech') return
    request<CatalogEntry[]>('/technician/catalog', token).then(setCatalog).catch(e => setError(e.message))
    request<string[]>('/technician/scripts', token).then(setScripts).catch(e => setError(e.message))
  }, [page, token, techUnlocked])

  const currentModule = page === 'storage' || page === 'process' || page === 'network' ? modules[page] : null
  const actionItems = task?.result?.actions || []
  const targetFiles = (task?.result?.evidence || []).filter((v): v is FileEvidence => typeof v === 'object' && v !== null && 'path' in v)
  const targetProcesses = (task?.result?.evidence || []).filter((v): v is FileEvidence => typeof v === 'object' && v !== null && 'pid' in v)

  return <div className="shell">
    <aside className="sidebar">
      <button className="brand" onClick={() => { setPage('home'); setSelected(null); setTask(null) }} aria-label="Ir al inicio"><span className="brand-mark">X<span>+</span></span><span><strong>X-SCANNER</strong><small>LINUX DIAGNOSTIC</small></span></button>
      <div className="side-label">ESPACIO DE TRABAJO</div>
      <nav aria-label="Navegación principal">{nav.map(link => <button key={link.id} className={`nav-item ${page === link.id ? 'active' : ''}`} onClick={() => { setPage(link.id); setSelected(null); setTask(null); setPrepared(null); setError(''); setMessage('') }}><span className="nav-icon" aria-hidden="true">{link.icon}</span>{link.label}</button>)}</nav>
      <div className="sidebar-bottom"><div className={`status-dot ${token ? 'online' : ''}`}></div><div><strong>{token ? 'Complemento vinculado' : health === 'ready' ? 'Listo para vincular' : health === 'incompatible' ? 'Versión incompatible' : permission === 'prompt' ? 'Acceso local pendiente' : 'Complemento desconectado'}</strong><small>{token ? 'Datos en esta computadora' : '127.0.0.1:8765'}</small></div></div>
    </aside>

    <main className="main">
      <header className="topbar"><div className="breadcrumb">SISTEMA / <span>{nav.find(n => n.id === page)?.label.toUpperCase()}</span></div><div className="topright"><span className="live-indicator">● SISTEMA LOCAL</span><span className="version">v0.1</span></div></header>
      <div className="content">
        {error && <div className="notice error" role="alert"><span>!</span>{error}<button onClick={() => setError('')} aria-label="Cerrar aviso">×</button></div>}
        {message && <div className="notice success" role="status"><span>✓</span>{message}<button onClick={() => setMessage('')} aria-label="Cerrar aviso">×</button></div>}
        {capabilities && !capabilities.initially_supported && <div className="notice error" role="status"><span>!</span>Distribución {capabilities.distribution} {capabilities.distribution_version}: se muestran las funciones disponibles, pero esta versión aún no se ha verificado aquí.</div>}

        {!token && <section className="pair-panel" aria-labelledby="pair-title"><div><p className="eyebrow">PASO 01 / CONEXIÓN LOCAL</p><h2 id="pair-title">Conecta el complemento</h2><p>Instala y abre X-Scanner en este equipo. Copia el código temporal que aparece en su ventana o terminal. La página nunca recibe tu contraseña de Linux.</p><p className="muted">{permission === 'denied' ? 'El acceso al dispositivo local está bloqueado. Permite “Red de bucle local” en los permisos de este sitio en Brave.' : health === 'offline' ? 'El servicio no responde. Inícialo y comprueba el permiso de red local en Brave.' : health === 'incompatible' ? 'El puerto responde, pero no es una versión compatible de X-Scanner. No introduzcas el código.' : health === 'ready' ? 'Servicio local detectado.' : 'Pulsa el botón para solicitar acceso a este complemento local.'}</p>{health !== 'ready' && <button className="secondary" disabled={permission === 'denied' || permission === 'checking'} onClick={checkHealth}>Comprobar servicio local</button>}</div><form onSubmit={e => { e.preventDefault(); pair() }}><label htmlFor="pair-code">Código de seis dígitos</label><input id="pair-code" inputMode="numeric" maxLength={6} pattern="[0-9]{6}" value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ''))} placeholder="000000" /><button className="primary" disabled={health !== 'ready' || code.length !== 6}>Vincular ahora <span>→</span></button></form></section>}

        {page === 'home' && <>
          <section className="hero"><div className="hero-copy"><p className="eyebrow">DIAGNÓSTICO INTELIGENTE / LINUX</p><h1>Entiende lo que pasa.<br /><em>Recupera el control.</em></h1><p>Herramientas claras para encontrar problemas en almacenamiento, procesos y redes. Todo ocurre en esta computadora.</p><div className="hero-actions"><button className="primary" disabled={!token} onClick={() => { select('full-scan'); run('full-scan', {}) }}>Iniciar FULL SCAN <span>↗</span></button><span>Sin reparaciones automáticas</span></div></div><div className="hero-visual" aria-hidden="true"><div className="orbit orbit-one"></div><div className="orbit orbit-two"></div><div className="radar-core">X</div><div className="radar-label label-one">STORAGE · OK</div><div className="radar-label label-two">NETWORK · LIVE</div><div className="radar-label label-three">PROCESS · 03</div></div></section>
          <div className="section-heading"><div><p className="eyebrow">EXPLORA POR ÁREA</p><h2>¿Qué necesitas revisar?</h2></div><span>03 módulos disponibles</span></div>
          <div className="module-grid">{(['storage', 'process', 'network'] as const).map((id, index) => <button className="module-card" key={id} onClick={() => setPage(id)}><div className="module-top"><span className="module-icon">{modules[id].icon}</span><span className="module-number">0{index + 1} / 03</span></div><h3>{modules[id].title}</h3><p>{modules[id].subtitle}</p><div className="module-footer"><span>3 diagnósticos</span><span className="arrow">↗</span></div></button>)}</div>
          <button className="scan-card" disabled={!token} onClick={() => { select('full-scan'); run('full-scan', {}) }}><div><p className="eyebrow">NO SABES POR DÓNDE EMPEZAR</p><h3>Algo anda mal, pero no sé por dónde comenzar</h3><p>Full Scan revisa el estado general de las tres áreas y te orienta sobre el siguiente paso.</p></div><span>INICIAR FULL SCAN ↗</span></button>
          <section className="tech-card quick-start"><p className="eyebrow">GUÍA DE CONEXIÓN</p><h3>Instalar y volver a vincular</h3><p>Desde la carpeta donde descargaste el paquete: <code>sudo apt install ./xscanner-agent_0.1.0_amd64.deb</code></p><p>Configura el sitio publicado: <code>xscanner-cli origin https://xscanner.netlify.app</code>. Luego inicia <strong>X-Scanner</strong> desde el menú y escribe el código temporal.</p><p>Si ya estaba iniciado, cierra esa instancia y vuelve a ejecutar <code>xscanner-launch</code>. Si aparece “puerto 8765 ocupado”, comprueba el proceso con <code>sudo fuser -v 8765/tcp</code>; detén solo una instancia identificada de X-Scanner y vuelve a lanzarlo.</p></section>
        </>}

        {currentModule && <><section className="page-intro"><p className="eyebrow">MÓDULO / {currentModule.title.toUpperCase()}</p><h1>{currentModule.title}<span className="intro-icon">{currentModule.icon}</span></h1><p>{currentModule.subtitle}. Elige el problema que se parece al tuyo.</p></section><div className="problem-list">{currentModule.items.map(item => <button key={item.kind} className={`problem-card ${selected === item.kind ? 'chosen' : ''}`} onClick={() => select(item.kind)}><span>{item.icon}</span><div><h3>{item.title}</h3><p>{item.description}</p></div><b>↗</b></button>)}</div></>}

        {page === 'labs' && <><section className="page-intro"><p className="eyebrow">LABORATORIO CONTROLADO</p><h1>Pruebas</h1><p>Cada prueba altera solo recursos creados por X-Scanner. Puedes restaurarlos desde aquí aunque cierres el navegador.</p></section><div className="lab-grid">{[
          { id: 'storage', title: 'Almacenamiento', body: 'Crea 128 MiB en cuatro archivos identificados. Diagnostica espacio y recupera el laboratorio.', kind: 'storage-space' as DiagnosticKind },
          { id: 'process', title: 'Procesos', body: 'Inicia un proceso de carga de un núcleo durante un máximo de 90 segundos.', kind: 'process-slow' as DiagnosticKind },
          { id: 'network', title: 'Redes', body: 'Deja detenido el servidor HTTP local de prueba en el puerto 8766.', kind: 'network-page' as DiagnosticKind },
          { id: 'strange', title: 'Caso extraño', body: 'Mantiene abierto un archivo eliminado de 32 MiB durante un máximo de 90 segundos.', kind: 'strange-case' as DiagnosticKind },
        ].map(item => <article className="lab-card" key={item.id}><p className="eyebrow">PRUEBA / {item.id.toUpperCase()}</p><h3>{item.title}</h3><p>{item.body}</p><div className="lab-actions"><button disabled={!token} onClick={() => lab(item.id, 'start')}>Crear alteración</button><button disabled={!token} onClick={() => { select(item.kind); run(item.kind, item.kind === 'network-page' ? { url: 'http://127.0.0.1:8766/' } : {}) }}>Diagnosticar</button><button disabled={!token || !(item.id in labs)} onClick={() => lab(item.id, 'restore')}>Restaurar</button></div><small>{item.id in labs ? 'Prueba activa' : 'Prueba inactiva'}</small></article>)}</div></>}

        {page === 'history' && <><section className="page-intro"><p className="eyebrow">REGISTRO LOCAL</p><h1>Historial</h1><p>Los resultados y reportes permanecen en este equipo.</p></section><div className="history-list">{history.length ? history.map(entry => <button key={entry.id} onClick={() => request<Task>(`/tasks/${entry.id}`, token).then(t => { setTask(t); setSelected(t.kind) }).catch(e => setError(e.message))}><span>{new Date(entry.created).toLocaleString('es')}</span><strong>{labelKind(entry.kind)}</strong><small>{entry.status}</small><b>Ver →</b></button>) : <div className="empty">Todavía no hay diagnósticos guardados.</div>}</div></>}

        {page === 'tech' && <><section className="page-intro"><p className="eyebrow">ACCESO AVANZADO</p><h1>Herramientas del técnico</h1><p>La contraseña es local. El acceso vence tras 15 minutos de inactividad. Los scripts se ejecutan con tu usuario, nunca con privilegios administrativos.</p></section><div className="tech-card"><h3>{techConfigured ? 'Desbloquear modo técnico' : 'Crear contraseña técnica'}</h3><div className="inline-form"><label htmlFor="tech-password">Contraseña (mínimo 10 caracteres)</label><input id="tech-password" type="password" minLength={10} value={techPassword} onChange={e => setTechPassword(e.target.value)} /><button className="primary" disabled={!token || techPassword.length < 10} onClick={async () => { try { await post(`/technician/${techConfigured ? 'unlock' : 'password'}`, token, { password: techPassword }); setTechUnlocked(true); setTechConfigured(true); setTechPassword(''); setMessage('Modo técnico desbloqueado.'); setTimeout(loadScripts, 0) } catch (e) { setError((e as Error).message) } }}>Desbloquear</button></div></div>{techUnlocked && <><div className="tech-card"><h3>Arsenal</h3><p>Los diagnósticos integrados se consultan como referencia. Los scripts personales se guardan por versiones y se ejecutan como el usuario actual.</p><div className="arsenal-list">{scripts.map(name => <button key={name} className="secondary" onClick={async () => { setScriptName(name); try { const r = await request<{ source: string }>(`/technician/scripts/${encodeURIComponent(name)}`, token); setScriptSource(r.source) } catch (e) { setError((e as Error).message) } }}>{name}</button>)}{!scripts.length && <span className="muted">Aún no hay scripts personales guardados.</span>}</div><div className="arsenal-reference"><strong>Diagnósticos integrados</strong><span>Almacenamiento · Procesos · Redes</span></div></div><div className="tech-card"><h3>Editor de script personal</h3><p>Guarda una versión y ejecútala con límite de 30 segundos y memoria acotada. Revisa el código antes de ejecutarlo.</p><label htmlFor="script-name">Nombre</label><input id="script-name" pattern="[a-zA-Z0-9_-]+" value={scriptName} onChange={e => setScriptName(e.target.value)} placeholder="mi_diagnostico" /><label htmlFor="script-source">Código Python</label><textarea id="script-source" rows={9} value={scriptSource} onChange={e => setScriptSource(e.target.value)} /><div className="lab-actions"><button onClick={async () => { try { await post('/technician/scripts', token, { name: scriptName, source: scriptSource }); await loadScripts(); setMessage('Versión guardada.') } catch (e) { setError((e as Error).message) } }}>Guardar versión</button><button onClick={async () => { try { const r = await post<{ stdout: string; stderr: string; exit_code: number }>(`/technician/scripts/${encodeURIComponent(scriptName)}/run`, token); setScriptOutput(`Salida ${r.exit_code}\n${r.stdout}\n${r.stderr}`) } catch (e) { setError((e as Error).message) } }}>Ejecutar</button></div>{scriptOutput && <pre className="script-output">{scriptOutput}</pre>}</div></>}</>}

        {page === 'tech' && techUnlocked && <section className="tech-card" aria-labelledby="catalog-title"><h3 id="catalog-title">Arsenal por módulo</h3><p>Selecciona el código real de un diagnóstico o solución. Puedes editar y guardar una copia personal para pruebas. Los diagnósticos y acciones integrados siguen usando el código instalado.</p><div className="view-switch">{(['storage','process','network'] as const).map(module => <button key={module} className={catalogModule === module ? 'active' : ''} onClick={() => setCatalogModule(module)}>{module === 'storage' ? 'Almacenamiento' : module === 'process' ? 'Procesos' : 'Redes'}</button>)}</div><div className="arsenal-list">{catalog.filter(item => item.module === catalogModule).map(item => <button className="secondary" key={item.type + item.id} onClick={() => { setCatalogItem(item); setCatalogSource(item.source); setCatalogName(`copia_${item.id.replaceAll('-', '_')}`) }}>{item.type === 'diagnostic' ? 'Diagnóstico' : 'Solución'} · {item.id}</button>)}</div>{catalogItem && <div><h4>{catalogItem.id}</h4><label>Nombre de tu versión<input value={catalogName} onChange={e => setCatalogName(e.target.value)} /></label><textarea className="catalog-source" aria-label="Código del módulo seleccionado" rows={14} value={catalogSource} onChange={e => setCatalogSource(e.target.value)} /><button className="secondary" disabled={!/^[a-zA-Z0-9_-]{1,40}$/.test(catalogName)} onClick={async () => { try { await post('/technician/scripts', token, { name: catalogName, source: catalogSource, module: catalogItem.module }); await loadScripts(); setMessage('Versión personal guardada en Arsenal.') } catch (e) { setError((e as Error).message) } }}>Guardar versión personal</button></div>}</section>}

        {selected && token && page !== 'tech' && <section className="diagnostic-panel" id="diagnostic"><div className="diagnostic-heading"><div><p className="eyebrow">DIAGNÓSTICO SELECCIONADO</p><h2>{labelKind(selected)}</h2></div><span className="step-badge">{task ? '02 / RESULTADO' : '01 / CONFIGURAR'}</span></div>
          {!task && <><div className="parameter-grid">{(selected === 'storage-photo' || selected === 'storage-file') && <>
            <label>Carpeta inicial<input value={String(params.root || '')} onChange={e => setParams({ ...params, root: e.target.value })} placeholder="Tu carpeta personal" /></label>
            <label>Nombre parcial<input value={String(params.name || '')} onChange={e => setParams({ ...params, name: e.target.value })} placeholder="Opcional" /></label>
            <label>Extensión<input value={String(params.extension || '')} onChange={e => setParams({ ...params, extension: e.target.value })} placeholder="jpg, pdf..." /></label>
            <label>Mes aproximado<input type="month" value={String(params.month || '')} onChange={e => setParams({ ...params, month: e.target.value })} /></label>
            <label className="check-label"><input type="checkbox" checked={Boolean(params.expand_month)} onChange={e => setParams({ ...params, expand_month: e.target.checked })} /> Ampliar al mes anterior y siguiente</label>
            {selected === 'storage-file' && <label>Texto interno (txt, md, csv, log)<input value={String(params.content || '')} onChange={e => setParams({ ...params, content: e.target.value })} placeholder="Opcional" /></label>}
          </>}
          {selected === 'storage-space' && <label className="check-label"><input type="checkbox" checked={Boolean(params.duplicates)} onChange={e => setParams({ ...params, duplicates: e.target.checked })} /> Buscar posibles duplicados (puede tardar)</label>}
          {(selected === 'storage-photo' || selected === 'storage-file') && <><label>Tamaño mínimo (MiB)<input type="number" min="0" value={String(params.min_mib || '')} onChange={e => setParams({ ...params, min_mib: e.target.value })} placeholder="Opcional" /></label><label>Tamaño máximo (MiB)<input type="number" min="0" value={String(params.max_mib || '')} onChange={e => setParams({ ...params, max_mib: e.target.value })} placeholder="Opcional" /></label></>}
          {selected === 'network-slow' && <label className="check-label"><input type="checkbox" checked={Boolean(params.per_process)} onChange={e => setParams({ ...params, per_process: e.target.checked })} /> Medir tráfico por aplicación con NetHogs (requiere autorización de Linux)</label>}
          {selected === 'process-frozen' && <label>Nombre de la aplicación<input value={String(params.name || '')} onChange={e => setParams({ ...params, name: e.target.value })} placeholder="Ej.: editor" /></label>}
          {selected === 'network-page' && <label>Dirección HTTP o HTTPS<input type="url" value={String(params.url || '')} onChange={e => setParams({ ...params, url: e.target.value })} /></label>}
          </div><button className="primary" onClick={() => run()}>{selected === 'full-scan' ? 'Iniciar FULL SCAN' : 'Iniciar diagnóstico'} <span>→</span></button></>}
          {task && <><div className="task-meta"><span className={`task-status ${task.status}`}>{task.status === 'complete' ? 'COMPLETADO' : task.status === 'running' ? 'ANALIZANDO' : task.status === 'queued' ? 'EN COLA' : task.status === 'cancelled' ? 'CANCELADO' : 'INCOMPLETO'}</span><span>ID {task.id.slice(0, 8)}</span><span>{new Date(task.created).toLocaleString('es')}</span></div>
            {!terminal(task.status) && <div className="progress-block"><div className="progress-track"><progress aria-label="Progreso del diagnóstico" value={task.progress} max={100} /></div><p>El tiempo depende del equipo y de las carpetas examinadas.</p><button className="secondary" onClick={() => post(`/tasks/${task.id}/cancel`, token).catch(e => setError(e.message))}>Cancelar diagnóstico</button></div>}
            {task.result && <><div className="view-switch" role="tablist" aria-label="Vista del resultado"><button className={resultView === 'client' ? 'active' : ''} onClick={() => setResultView('client')}>Cliente</button><button className={resultView === 'technical' ? 'active' : ''} onClick={() => setResultView('technical')}>Técnico · JSON</button></div>{resultView === 'client' ? <ClientResult task={task} /> : <><h3 className="result-summary">{task.result.summary}</h3><MetricCards measurements={task.result.measurements} /><DataList title="Mediciones" data={task.result.measurements} /><DataList title="Hallazgos" data={task.result.findings} /><Evidence task={task} token={token} onError={setError} /><DataList title="Limitaciones" data={task.result.limitations} /><DataList title="Recomendaciones" data={task.result.recommendations} /><DataList title="Resultados de reparación" data={task.result.actions_taken} /></>}</>}
            {task.error && <p className="error-text">{task.error}</p>}
            {terminal(task.status) && <div className="result-actions"><button className="primary" onClick={() => download(`/tasks/${task.id}/report`, token, `xscanner-${task.id}.txt`).catch(e => setError(e.message))}>Descargar reporte .txt ↓</button><button className="secondary" onClick={() => { setTask(null); setPrepared(null) }}>Nuevo diagnóstico</button></div>}
            {task.status === 'complete' && actionItems.length > 0 && <div className="action-section"><p className="eyebrow">ACCIONES DISPONIBLES</p><h3>Revisa antes de cambiar algo</h3>{actionItems.map(action => <div className="action-row" key={action.kind}><div><strong>{action.description}</strong>{action.kind === 'trash-file' && <select aria-label="Archivo para mover" value={actionTarget} onChange={e => setActionTarget(e.target.value)}><option value="">Selecciona un archivo</option>{targetFiles.map(f => f.path && <option key={f.path} value={f.path}>{f.path}</option>)}</select>}{action.kind === 'terminate-process' && <select aria-label="Proceso para cerrar" value={actionTarget} onChange={e => setActionTarget(e.target.value)}><option value="">Selecciona un proceso</option>{targetProcesses.map(p => p.pid && <option key={p.pid} value={String(p.pid)}>{p.name || 'Proceso'} · PID {p.pid}</option>)}</select>}</div><button className="secondary" onClick={() => prepareAction(action.kind, actionTarget)}>Revisar acción →</button></div>)}{actionItems.some(a => a.kind === 'terminate-process') && <button className="text-button" onClick={() => prepareAction('force-process', actionTarget)}>Preparar cierre forzado (segunda acción explícita)</button>}</div>}
          </>}
        </section>}
      </div>
    </main>

    {prepared && <div className="modal-backdrop" role="presentation"><div className="modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title"><p className="eyebrow">CONFIRMACIÓN REQUERIDA</p><h2 id="confirm-title">Revisa el cambio</h2><p>{prepared.description}</p><div className="modal-note"><strong>Consecuencias</strong><span>{prepared.consequences}</span></div><div className="modal-note"><strong>Recuperación</strong><span>{prepared.recovery}</span></div><div className="modal-actions"><button className="secondary" disabled={actionState === 'working'} onClick={() => setPrepared(null)}>Cancelar</button><button className="primary" disabled={actionState === 'working'} onClick={executeAction}>Confirmar y ejecutar</button></div></div></div>}
    {actionState === 'working' && <div className="modal-backdrop" role="status"><div className="modal working-modal"><div className="spinner"></div><h2>Trabajando en ello...</h2><p>Estamos aplicando la acción y verificando la respuesta del sistema.</p></div></div>}
    {actionState === 'success' && <div className="modal-backdrop"><div className="modal success-modal" role="dialog" aria-modal="true"><div className="success-check">✓</div><h2>Acción confirmada</h2><p>La operación terminó correctamente.</p><button className="primary" onClick={() => setActionState('idle')}>Aceptar</button></div></div>}
  </div>
}
