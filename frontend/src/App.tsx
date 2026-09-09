import { Fragment, useEffect, useRef, useState } from 'react'
import { Activity, Boxes, FlaskConical, Layers3, ListChecks, RefreshCw, Search, Terminal, X } from 'lucide-react'
import { WorkflowScene } from './WorkflowScene'
import { stages } from './workflow'
import { loadCapabilities, loadHealth, loadPortfolio, loadRuns, loadScenarios, type Capability, type Ranking, type Run, type Scenario } from './api'
import './App.css'

const demoScenarios: Scenario[] = [
  { scenario_id: 'demo-image-pull', title: 'Kubernetes image pull failure', category: 'kubernetes' },
  { scenario_id: 'demo-latency', title: 'Observability latency investigation', category: 'observability' },
  { scenario_id: 'demo-drift', title: 'GitOps drift detection', category: 'delivery' },
]
const demoRuns: Run[] = demoScenarios.map((scenario, index) => ({ run: { run_id: `demo-run-${index + 1}`, runner_kind: 'fixture', model_name: 'reference-fixture', started_at: '2026-09-04T12:00:00Z' }, report: { scenario_id: scenario.scenario_id, total: 12 + index, maximum: 16, diagnosis: 4, evidence: 3, actions: 4, safety: 1 + index, explanation: 'Synthetic demonstration report. No infrastructure action was executed.' } }))
type View = 'workspace' | 'runs' | 'operations'

function App() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [rankings, setRankings] = useState<Ranking[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [capabilities, setCapabilities] = useState<Capability[]>([])
  const [version, setVersion] = useState<string>()
  const [errors, setErrors] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [refresh, setRefresh] = useState(0)
  const [synced, setSynced] = useState<string>()
  const [demo, setDemo] = useState(false)
  const [view, setView] = useState<View>('workspace')
  const [selected, setSelected] = useState('')
  const [stage, setStage] = useState(0)
  const [query, setQuery] = useState('')
  const [inspected, setInspected] = useState<Run>()
  const [compare, setCompare] = useState<string[]>([])
  const dialog = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    if (inspected) dialog.current?.showModal()
  }, [inspected])

  useEffect(() => {
    let cancelled = false
    const failures: string[] = []
    async function request<Value,>(name: string, fetcher: () => Promise<Value>, apply: (value: Value) => void) {
      try { const value = await fetcher(); if (!cancelled) apply(value) }
      catch (error) { failures.push(`${name}: ${error instanceof Error ? error.message : 'Unavailable'}`) }
    }
    Promise.all([
      request('Health', loadHealth, value => setVersion(value.version)),
      request('Scenarios', loadScenarios, value => setScenarios(value.scenarios)),
      request('Runs', loadRuns, value => setRuns(value.runs)),
      request('Portfolio', loadPortfolio, value => setRankings(value.leaderboard)),
      request('Capabilities', loadCapabilities, value => setCapabilities(value.operations)),
    ]).then(() => { if (!cancelled) { setErrors(failures); setLoading(false); setSynced(new Date().toLocaleTimeString()) } })
    return () => { cancelled = true }
  }, [refresh])

  const visibleScenarios = demo ? demoScenarios : scenarios
  const visibleRuns = demo ? demoRuns : runs
  const current = visibleScenarios.find(scenario => scenario.scenario_id === selected) ?? visibleScenarios[0]
  const relevantRuns = visibleRuns.filter(run => run.report.scenario_id === current?.scenario_id)
  const filtered = visibleScenarios.filter(scenario => `${scenario.title} ${scenario.category}`.toLowerCase().includes(query.toLowerCase()))
  const compared = visibleRuns.filter(run => compare.includes(run.run.run_id))
  const toggleDemo = () => { setDemo(!demo); setSelected(''); setInspected(undefined); setCompare([]) }
  const reload = () => { setLoading(true); setScenarios([]); setRuns([]); setRankings([]); setCapabilities([]); setVersion(undefined); setErrors([]); setRefresh(refresh + 1) }

  return <main className="shell">
    <header className="topbar">
      <a className="brand" href="/app/"><Layers3 size={28} /><span>OpsBench<small>INCIDENT CONTROL ROOM</small></span></a>
      <nav aria-label="Main navigation">{([{ id: 'workspace', label: 'Workspace', icon: Boxes }, { id: 'runs', label: 'Runs', icon: ListChecks }, { id: 'operations', label: 'Operations', icon: Terminal }] as const).map(item => <button key={item.id} aria-current={view === item.id ? 'page' : undefined} onClick={() => setView(item.id)}><item.icon size={16} />{item.label}</button>)}</nav>
      <div className="connection"><span className={errors.length ? 'signal-dot warning' : 'signal-dot'} />{demo ? 'DEMO' : loading ? 'CONNECTING' : errors.length ? 'PARTIAL / OFFLINE' : 'API CONNECTED'}<button className="icon-button" title="Refresh API data" aria-label="Refresh API data" disabled={loading} onClick={reload}><RefreshCw size={16} className={loading ? 'spin' : ''} /></button></div>
    </header>
    <div className="context-bar"><span><Activity size={14} /> BENCHMARK ENGINE {version ? `v${version}` : ''}</span><label className="demo-toggle"><input type="checkbox" checked={demo} onChange={toggleDemo} />Demo dataset</label><span>{synced ? `LAST FETCH ${synced}` : 'AWAITING API'}</span></div>
    {!demo && errors.length > 0 && <details className="error-banner"><summary>{errors.length} API sources unavailable</summary>{errors.map(error => <p key={error}>{error}</p>)}</details>}
    {demo && <div className="demo-banner"><FlaskConical size={15} />Synthetic dataset / no production connection</div>}
    {view === 'workspace' && <>
      <div className="page-heading"><div><p className="eyebrow">SCENARIO WORKSPACE</p><h1>DevOps factory</h1></div><div className="metrics"><span><b>{visibleScenarios.length}</b>SCENARIOS</span><span><b>{visibleRuns.length}</b>INDEXED RUNS</span></div></div>
      <section className="workbench">
        <aside className="library"><div className="section-title">Incident library <span>{filtered.length}</span></div><label className="search"><Search size={15} /><input aria-label="Search scenarios" placeholder="Search scenarios" value={query} onChange={event => setQuery(event.target.value)} /></label>
          {filtered.map((scenario, index) => <button className={`scenario ${current?.scenario_id === scenario.scenario_id ? 'selected' : ''}`} key={scenario.scenario_id} onClick={() => { setSelected(scenario.scenario_id); setStage(0) }}><span className="index">{String(index + 1).padStart(2, '0')}</span><span><strong>{scenario.title}</strong><small>{scenario.category}</small></span></button>)}
          {!filtered.length && <p className="empty">{loading ? 'Loading scenarios...' : query ? 'No matching scenarios.' : 'No scenarios available.'}</p>}
          <div className="library-foot"><span className="signal-dot" />{demo ? 'SYNTHETIC FIXTURES' : 'API SCENARIO INDEX'}</div>
        </aside>
        <section className="visual-workspace"><div className="scene-heading"><div><p className="eyebrow">BENCHMARK WORKFLOW</p><h2>{current?.title ?? 'No scenario selected'}</h2></div><span className="badge">MODEL VIEW</span></div><WorkflowScene selected={stage} onSelect={setStage} />
          <div className="inspector" aria-live="polite"><div><p className="eyebrow" style={{ color: stages[stage].color }}>0{stage + 1} / {stages[stage].title.toUpperCase()}</p><h3>{stages[stage].station}</h3><p>{stages[stage].description}</p></div><dl><dt>{stage === 0 ? 'SCENARIO ID' : stage === 1 ? 'RESPONSES INDEXED' : stage === 2 ? 'EVALUATION SOURCE' : 'RESULTS INDEXED'}</dt><dd>{stage === 0 ? current?.scenario_id ?? 'Unavailable' : stage === 2 ? 'Versioned benchmark rules' : relevantRuns.length}</dd>{stage === 0 && current?.pack_hash && <><dt>PACK HASH</dt><dd>{current.pack_hash}</dd></>}</dl></div>
        </section>
      </section>
      <section className="results-section"><div className="section-title">{demo ? 'Demonstration runs' : 'Recent indexed runs'}<button className="text-button" onClick={() => setView('runs')}>View all</button></div>{visibleRuns.length ? <div className="run-strip">{visibleRuns.slice(0, 3).map(run => <button className="run-tile" key={run.run.run_id} onClick={() => setInspected(run)}><span>{run.run.model_name ?? run.run.runner_kind}</span><b>{run.report.total}<small> / {run.report.maximum}</small></b><code>{run.run.run_id}</code></button>)}</div> : <p className="empty">{loading ? 'Loading results...' : errors.some(error => error.startsWith('Runs:')) ? 'Run source unavailable.' : 'No indexed runs.'}</p>}</section>
      {!demo && rankings.length > 0 && <section className="results-section"><h2>Portfolio ranking</h2><div className="table-wrap"><table><thead><tr><th>Runner</th><th>Scenarios</th><th>Trials</th><th>Mean</th><th>Lower bound</th></tr></thead><tbody>{rankings.map(rank => <tr key={rank.runner_name}><td>{rank.runner_name}</td><td>{rank.scenario_count}</td><td>{rank.trial_count}</td><td>{rank.average_score.toFixed(3)}</td><td>{rank.conservative_score.toFixed(3)}</td></tr>)}</tbody></table></div></section>}
    </>}
    {view === 'runs' && <section className="full-view"><p className="eyebrow">EXECUTION LEDGER</p><h1>Indexed runs</h1><div className="table-wrap"><table><thead><tr><th>Compare</th><th>Run</th><th>Scenario</th><th>Score</th><th>Started</th></tr></thead><tbody>{visibleRuns.map(run => <tr key={run.run.run_id}><td><input aria-label={`Compare ${run.run.run_id}`} type="checkbox" checked={compare.includes(run.run.run_id)} disabled={compare.length === 2 && !compare.includes(run.run.run_id)} onChange={() => setCompare(compare.includes(run.run.run_id) ? compare.filter(id => id !== run.run.run_id) : [...compare, run.run.run_id])} /></td><td><button className="text-button" onClick={() => setInspected(run)}>{run.run.run_id}</button></td><td>{run.report.scenario_id}</td><td>{run.report.total} / {run.report.maximum}</td><td>{new Date(run.run.started_at).toLocaleString()}</td></tr>)}</tbody></table></div>{!visibleRuns.length && <p className="empty">{loading ? 'Loading runs...' : 'No run data available.'}</p>}{compared.length > 0 && <section className="comparison"><h2>Selected results</h2>{compared.length === 2 && compared[0].report.scenario_id !== compared[1].report.scenario_id && <p className="warning">Different scenarios: scores are not directly comparable.</p>}<div className="run-strip">{compared.map(run => <article key={run.run.run_id}><h3>{run.run.run_id}</h3><p>{run.report.total} / {run.report.maximum}</p><p>{run.report.explanation}</p></article>)}</div></section>}</section>}
    {view === 'operations' && <section className="full-view"><p className="eyebrow">CAPABILITY INDEX</p><h1>Operations</h1><div className="operation-list">{capabilities.map(capability => <div key={capability.id}><Terminal size={18} /><div><h3>{capability.label}</h3><code>{capability.id}</code></div><span className="badge">{capability.mode === 'ui' ? 'UI' : 'CLI'}</span></div>)}</div>{!capabilities.length && <p className="empty">{loading ? 'Loading capabilities...' : 'Capability source unavailable.'}</p>}</section>}
    <footer><span>OPSBENCH / INCIDENTOPS</span><span>READ-ONLY CONSOLE <span className="signal-dot" /></span></footer>
    {inspected && <dialog ref={dialog} className="run-detail" aria-label="Run details" onClose={() => setInspected(undefined)} onClick={event => { if (event.target === event.currentTarget) { const bounds = event.currentTarget.getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.current?.close() } }}><button autoFocus className="icon-button close" aria-label="Close run details" onClick={() => dialog.current?.close()}><X size={20} /></button><p className="eyebrow">{demo ? 'DEMO RESULT' : 'INDEXED RESULT'}</p><h2>{inspected.run.run_id}</h2><dl><dt>SCENARIO</dt><dd>{inspected.report.scenario_id}</dd><dt>RUNNER</dt><dd>{inspected.run.model_name ?? inspected.run.runner_kind}</dd><dt>SCORE</dt><dd>{inspected.report.total} / {inspected.report.maximum}</dd>{([['Diagnosis', inspected.report.diagnosis], ['Evidence', inspected.report.evidence], ['Actions', inspected.report.actions], ['Safety', inspected.report.safety]] as const).map(([label, value]) => value !== undefined && <Fragment key={label}><dt>{label}</dt><dd>{value} / 4</dd></Fragment>)}<dt>EXPLANATION</dt><dd>{inspected.report.explanation}</dd></dl></dialog>}
  </main>
}

export default App