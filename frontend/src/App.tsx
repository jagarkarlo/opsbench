import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import './App.css'

type Scenario = { scenario_id: string; title: string; category: string }
type Ranking = { runner_name: string; scenario_count: number; trial_count: number; average_score: number; conservative_score: number }

const demoScenarios: Scenario[] = [
  { scenario_id: 'k8s-image-pull', title: 'Kubernetes image pull failure', category: 'kubernetes' },
  { scenario_id: 'observability-latency', title: 'Observability latency investigation', category: 'observability' },
  { scenario_id: 'gitops-drift', title: 'GitOps drift detection', category: 'delivery' },
]

const demoRankings: Ranking[] = [
  { runner_name: 'reference-fixture', scenario_count: 5, trial_count: 18, average_score: 0.86, conservative_score: 0.78 },
  { runner_name: 'human-review', scenario_count: 4, trial_count: 11, average_score: 0.74, conservative_score: 0.62 },
  { runner_name: 'openai-compatible', scenario_count: 3, trial_count: 8, average_score: 0.68, conservative_score: 0.51 },
]

function NetworkCanvas({ active }: { active: string }) {
  const mount = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!mount.current) return
    const scene = new THREE.Scene()
    const camera = new THREE.OrthographicCamera(-6, 6, 3.5, -3.5, 0.1, 100)
    camera.position.set(0, 0, 10)
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(mount.current.clientWidth, mount.current.clientHeight)
    mount.current.appendChild(renderer.domElement)

    const points = [-4.4, -1.5, 1.5, 4.4]
    const nodes = points.map((x, index) => {
      const geometry = new THREE.CircleGeometry(index === 2 ? 0.34 : 0.25, 32)
      const material = new THREE.MeshBasicMaterial({ color: index === 2 ? 0xffc857 : 0x5de2c2 })
      const node = new THREE.Mesh(geometry, material)
      node.position.set(x, index % 2 ? -0.4 : 0.55, 0)
      scene.add(node)
      return node
    })
    const lineMaterial = new THREE.LineBasicMaterial({ color: 0x376b75, transparent: true, opacity: 0.8 })
    for (let index = 0; index < nodes.length - 1; index += 1) {
      const geometry = new THREE.BufferGeometry().setFromPoints([nodes[index].position, nodes[index + 1].position])
      scene.add(new THREE.Line(geometry, lineMaterial))
    }
    const pulse = new THREE.Mesh(new THREE.CircleGeometry(0.1, 20), new THREE.MeshBasicMaterial({ color: 0xfff3c4 }))
    scene.add(pulse)
    let frame = 0
    const animate = () => {
      frame = requestAnimationFrame(animate)
      const progress = (Date.now() % 2600) / 2600
      pulse.position.x = -4.4 + progress * 8.8
      pulse.position.y = Math.sin(progress * Math.PI * 3) * 0.48
      pulse.scale.setScalar(1 + Math.sin(Date.now() / 180) * 0.18)
      renderer.render(scene, camera)
    }
    animate()
    const resize = () => renderer.setSize(mount.current?.clientWidth ?? 600, mount.current?.clientHeight ?? 240)
    window.addEventListener('resize', resize)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', resize)
      renderer.dispose()
      mount.current?.removeChild(renderer.domElement)
    }
  }, [active])

  return <div className="network-canvas" ref={mount} aria-label="Animated incident service topology" />
}

function App() {
  const [scenarios, setScenarios] = useState<Scenario[]>(demoScenarios)
  const [rankings, setRankings] = useState<Ranking[]>(demoRankings)
  const [selected, setSelected] = useState(demoScenarios[0].scenario_id)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    Promise.all([
      fetch('/api/v1/scenarios').then((response) => response.json()),
      fetch('/api/v1/leaderboard/portfolio').then((response) => response.json()),
    ]).then(([scenarioData, leaderboardData]) => {
      if (scenarioData.scenarios?.length) setScenarios(scenarioData.scenarios)
      if (leaderboardData.leaderboard?.length) setRankings(leaderboardData.leaderboard)
      setConnected(true)
    }).catch(() => setConnected(false))
  }, [])

  return (
    <main className="shell">
      <header className="topbar"><div className="brand"><span className="brand-mark">O</span><span>OPSBENCH <small>/ CONTROL ROOM</small></span></div><span className={connected ? 'status live' : 'status'}><i />{connected ? 'API CONNECTED' : 'DEMO DATA'}</span></header>
      <section className="hero-row"><div><p className="eyebrow">PHASE 05 / ECOSYSTEM TELEMETRY</p><h1>Benchmark intelligence,<br /><em>with a pulse.</em></h1><p className="lede">Read the reliability of your incident reasoning at a glance. Explore scenario topology, compare agents, and follow the signal.</p></div><div className="hero-meta"><span>LAST SYNC</span><strong>JUST NOW</strong><span>STORE</span><strong>SQLITE / LOCAL</strong></div></section>
      <section className="workspace">
        <aside className="rail"><div className="rail-label">SCENARIO GALLERY <span>{String(scenarios.length).padStart(2, '0')}</span></div>{scenarios.map((scenario, index) => <button className={selected === scenario.scenario_id ? 'scenario selected' : 'scenario'} key={scenario.scenario_id} onClick={() => setSelected(scenario.scenario_id)}><span className="scenario-index">0{index + 1}</span><span><strong>{scenario.title}</strong><small>{scenario.category.toUpperCase()} / READY</small></span><span className="arrow">↗</span></button>)}</aside>
        <section className="stage"><div className="stage-head"><div><p className="eyebrow">LIVE TOPOLOGY</p><h2>{scenarios.find((scenario) => scenario.scenario_id === selected)?.title ?? 'Incident topology'}</h2></div><span className="chip">● RUNNING</span></div><NetworkCanvas active={selected} /><div className="node-labels"><span>INGRESS</span><span>ORCHESTRATOR</span><span className="alert">FAULT DOMAIN</span><span>RECOVERY</span></div><div className="stage-foot"><span>FLOW LATENCY <b>124 ms</b></span><span>ACTIVE NODES <b>04</b></span><span>CONFIDENCE <b>92.4%</b></span></div></section>
      </section>
      <section className="lower"><div className="section-heading"><div><p className="eyebrow">CROSS-SCENARIO SIGNAL</p><h2>Portfolio leaderboard</h2></div><span className="muted">NORMALIZED SCORE / LOWER BOUND RANKING</span></div><div className="table-wrap"><table><thead><tr><th>#</th><th>RUNNER / MODEL</th><th>SCENARIOS</th><th>TRIALS</th><th>AVERAGE</th><th>CONSERVATIVE</th><th /></tr></thead><tbody>{rankings.map((ranking, index) => <tr className={index === 0 ? 'top-rank' : ''} key={ranking.runner_name}><td className="rank">0{index + 1}</td><td><strong>{ranking.runner_name}</strong>{index === 0 && <span className="winner">LEADING</span>}</td><td>{ranking.scenario_count}</td><td>{ranking.trial_count}</td><td>{ranking.average_score.toFixed(3)}</td><td className="score">{ranking.conservative_score.toFixed(3)}</td><td><div className="bar"><span style={{ width: `${ranking.average_score * 100}%` }} /></div></td></tr>)}</tbody></table></div></section>
      <footer><span>OPSBENCH / OPEN BENCHMARK PLATFORM</span><span>V0.6.4 <i /> LOCAL OBSERVABILITY MODE</span></footer>
    </main>
  )
}

export default App
