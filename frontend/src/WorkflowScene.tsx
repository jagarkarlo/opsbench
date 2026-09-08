import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'
import { Plus, Minus, RotateCcw, Orbit, Hand, Pause, Play, Scan, Focus, Camera, Maximize2, Minimize2, SlidersHorizontal } from 'lucide-react'
import { stages } from './workflow'
import { createFactory } from './factory'
import { cycleDuration } from './factoryMotion'

export function WorkflowScene({ selected, onSelect }: { selected: number; onSelect: (index: number) => void }) {
  const mount = useRef<HTMLDivElement>(null)
  const selection = useRef(selected)
  const callback = useRef(onSelect)
  const controlsRef = useRef<OrbitControls | null>(null)
  const actions = useRef({ focus: () => {}, overview: () => {}, top: () => {} })
  const playback = useRef({ paused: false, speed: 1, progress: 0 })
  const [paused, setPaused] = useState(() => matchMedia('(prefers-reduced-motion: reduce)').matches)
  const [speed, setSpeed] = useState(1)
  const [mode, setMode] = useState<'orbit' | 'pan'>('orbit')
  const [cameraView, setCameraView] = useState('OVERVIEW')
  const [expanded, setExpanded] = useState(false)
  const [inspectCycle, setInspectCycle] = useState(false)
  const [unavailable, setUnavailable] = useState(false)
  const [cycle, setCycle] = useState({ seconds: 0, phase: 'Conveying' })
  useEffect(() => { selection.current = selected; callback.current = onSelect }, [selected, onSelect])
  useEffect(() => { playback.current.paused = paused; playback.current.speed = speed }, [paused, speed])
  useEffect(() => {
    const controls = controlsRef.current
    if (!controls) return
    controls.mouseButtons.LEFT = mode === 'orbit' ? THREE.MOUSE.ROTATE : THREE.MOUSE.PAN
    controls.touches.ONE = mode === 'orbit' ? THREE.TOUCH.ROTATE : THREE.TOUCH.PAN
  }, [mode])

  useEffect(() => {
    const element = mount.current!
    let renderer: THREE.WebGLRenderer
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true }) }
    catch { queueMicrotask(() => setUnavailable(true)); return }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.75))
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFShadowMap
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.25
    element.appendChild(renderer.domElement)
    renderer.domElement.setAttribute('aria-label', 'Interactive benchmark workflow')
    const scene = new THREE.Scene()
    const environment = new RoomEnvironment()
    const generator = new THREE.PMREMGenerator(renderer)
    const environmentMap = generator.fromScene(environment, .04)
    scene.environment = environmentMap.texture
    scene.environmentIntensity = .35
    environment.dispose()
    generator.dispose()
    scene.background = new THREE.Color('#263b43')
    scene.fog = new THREE.Fog('#263b43', 35, 85)
    const camera = new THREE.OrthographicCamera(-8, 8, 5, -5, .1, 100)
    camera.position.set(9, 14, 21)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.minZoom = .65
    controls.maxZoom = 3
    controls.maxPolarAngle = Math.PI / 2.12
    controls.minPolarAngle = .08
    controls.target.set(-.5, .8, -.2)
    controls.update()
    controls.saveState()
    controlsRef.current = controls
    scene.add(new THREE.HemisphereLight(0xdceeff, 0x53656b, 2.2))
    const light = new THREE.DirectionalLight(0xfff0df, 4.2)
    light.position.set(-6, 13, 9)
    light.castShadow = true
    light.shadow.mapSize.set(2048, 2048)
    Object.assign(light.shadow.camera, { left: -13, right: 13, top: 12, bottom: -12, near: .5, far: 40 })
    light.shadow.normalBias = .035
    light.shadow.bias = -.00015
    scene.add(light)
    const rim = new THREE.DirectionalLight(0xa6dfff, 2.4)
    rim.position.set(5, 7, -9)
    scene.add(rim)
    const factory = createFactory()
    scene.add(factory.root)
    const pose = (target: THREE.Vector3, offset: THREE.Vector3, zoom: number) => {
      controls.target.copy(target)
      camera.position.copy(target).add(offset)
      camera.zoom = zoom
      camera.updateProjectionMatrix()
      controls.update()
    }
    actions.current = {
      overview: () => { controls.reset(); setCameraView('OVERVIEW') },
      top: () => { pose(new THREE.Vector3(0, 0, .5), new THREE.Vector3(0, 22, .01), 1); setCameraView('PLAN') },
      focus: () => { pose(factory.anchors[selection.current], new THREE.Vector3(5, 4, 8), 2.1); setCameraView(`STATION 0${selection.current + 1}`) },
    }
    const raycaster = new THREE.Raycaster()
    let start = { x: 0, y: 0 }
    const pick = (event: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect()
      raycaster.setFromCamera(new THREE.Vector2((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1), camera)
      return raycaster.intersectObjects([...factory.stations, factory.parcel], true)[0]?.object.userData.stage as number | undefined
    }
    const pointerDown = (event: PointerEvent) => { start = { x: event.clientX, y: event.clientY } }
    const pointerUp = (event: PointerEvent) => {
      if (Math.hypot(event.clientX - start.x, event.clientY - start.y) > 6) return
      const hit = pick(event)
      if (hit !== undefined) callback.current(hit)
    }
    const pointerMove = (event: PointerEvent) => {
      if (event.buttons) return
      renderer.domElement.style.cursor = pick(event) === undefined ? 'grab' : 'pointer'
    }
    renderer.domElement.addEventListener('pointerdown', pointerDown)
    renderer.domElement.addEventListener('pointerup', pointerUp)
    renderer.domElement.addEventListener('pointermove', pointerMove)
    const resize = new ResizeObserver(() => {
      const width = Math.max(1, element.clientWidth)
      const height = Math.max(1, element.clientHeight)
      const halfWidth = Math.max(14.4, 8.1 * width / height)
      camera.left = -halfWidth
      camera.right = halfWidth
      camera.top = halfWidth * height / width
      camera.bottom = -camera.top
      camera.updateProjectionMatrix()
      renderer.setSize(width, height)
    })
    resize.observe(element)
    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)')
    const motionChange = () => { setPaused(reducedMotion.matches) }
    reducedMotion.addEventListener('change', motionChange)
    let frame = 0
    let last = 0
    let lastCycleTick = -1
    const animate = (time: number) => {
      frame = requestAnimationFrame(animate)
      const delta = Math.min((time - last) / 1000, .05)
      last = time
      if (!playback.current.paused) playback.current.progress += delta * playback.current.speed
      const state = factory.update(playback.current.progress, selection.current)
      const tick = Math.floor(state.seconds * 5)
      if (tick !== lastCycleTick) { setCycle({ seconds: state.seconds, phase: state.phase }); lastCycleTick = tick }
      controls.update()
      renderer.render(scene, camera)
    }
    frame = requestAnimationFrame(animate)
    return () => {
      cancelAnimationFrame(frame)
      resize.disconnect()
      controls.dispose()
      reducedMotion.removeEventListener('change', motionChange)
      controlsRef.current = null
      renderer.domElement.removeEventListener('pointerdown', pointerDown)
      renderer.domElement.removeEventListener('pointerup', pointerUp)
      renderer.domElement.removeEventListener('pointermove', pointerMove)
      factory.dispose()
      environmentMap.dispose()
      light.shadow.dispose()
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [])

  const zoom = (factor: number) => {
    const controls = controlsRef.current
    if (!controls) return
    const camera = controls.object as THREE.OrthographicCamera
    camera.zoom = Math.min(3, Math.max(.65, camera.zoom * factor))
    camera.updateProjectionMatrix()
  }
  return <div className={`scene-wrap${expanded ? ' scene-expanded' : ''}${inspectCycle ? ' inspecting-cycle' : ''}`}>
    <div ref={mount} className="workflow-canvas" />
    {unavailable && <p className="scene-fallback">3D view unavailable. Stage selection remains available below.</p>}
    <div className="scene-caption"><span className="signal-dot" /> DEVOPS FACTORY <span>ILLUSTRATIVE</span></div>
    <div className="scene-view-label">CAMERA / {cameraView}</div>
    <div className="scene-tools">
      <button title="Orbit camera" aria-label="Orbit camera" aria-pressed={mode === 'orbit'} onClick={() => setMode('orbit')}><Orbit size={16} /></button>
      <button title="Pan camera" aria-label="Pan camera" aria-pressed={mode === 'pan'} onClick={() => setMode('pan')}><Hand size={16} /></button>
      <button title="Zoom in" aria-label="Zoom in" onClick={() => zoom(1.2)}><Plus size={16} /></button>
      <button title="Zoom out" aria-label="Zoom out" onClick={() => zoom(1 / 1.2)}><Minus size={16} /></button>
      <button title="Focus selected station" aria-label="Focus selected station" onClick={() => actions.current.focus()}><Focus size={16} /></button>
      <button title="Top view" aria-label="Top view" onClick={() => actions.current.top()}><Scan size={16} /></button>
      <button title="Reset view" aria-label="Reset view" onClick={() => actions.current.overview()}><RotateCcw size={16} /></button>
      <button title={expanded ? 'Collapse scene' : 'Expand scene'} aria-label={expanded ? 'Collapse scene' : 'Expand scene'} aria-pressed={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}</button>
      <button title="Inspect animation cycle" aria-label="Inspect animation cycle" aria-pressed={inspectCycle} onClick={() => setInspectCycle(!inspectCycle)}><SlidersHorizontal size={16} /></button>
    </div>
    <div className="scene-transport"><Camera size={14} /><span>FACTORY / 01</span><button title={paused ? 'Play animation' : 'Pause animation'} aria-label={paused ? 'Play animation' : 'Pause animation'} onClick={() => setPaused(!paused)}>{paused ? <Play size={15} /> : <Pause size={15} />}</button><label>Speed <select aria-label="Animation speed" value={speed} onChange={event => setSpeed(Number(event.target.value))}><option value={.5}>0.5x</option><option value={1}>1x</option><option value={2}>2x</option></select></label></div>
    {inspectCycle && <div className="cycle-timeline"><span>ILLUSTRATED CYCLE</span><output>{cycle.phase}</output><input aria-label="Factory cycle position" type="range" min="0" max={cycleDuration - .01} step=".01" value={cycle.seconds} onChange={event => { playback.current.progress = Number(event.target.value); playback.current.paused = true; setPaused(true) }} /><span>{cycle.seconds.toFixed(1)}s</span></div>}
    <div className="stage-tabs" role="tablist" aria-label="Workflow stages">{stages.map((stage, index) => <button role="tab" aria-selected={selected === index} tabIndex={selected === index ? 0 : -1} key={stage.title} onClick={() => onSelect(index)} onKeyDown={event => { const shortcut = Number(event.key) - 1; const next = event.key === 'ArrowRight' ? (index + 1) % stages.length : event.key === 'ArrowLeft' ? (index + stages.length - 1) % stages.length : event.key === 'Home' ? 0 : event.key === 'End' ? stages.length - 1 : shortcut >= 0 && shortcut < stages.length ? shortcut : null; if (next !== null) { event.preventDefault(); onSelect(next); (event.currentTarget.parentElement?.children[next] as HTMLButtonElement).focus() } }} style={{ '--stage-color': stage.color } as React.CSSProperties}><span>0{index + 1}</span>{stage.title}</button>)}</div>
  </div>
}