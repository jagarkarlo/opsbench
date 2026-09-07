import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { Plus, Minus, RotateCcw } from 'lucide-react'
import { stages } from './workflow'

export function WorkflowScene({ selected, onSelect }: { selected: number; onSelect: (index: number) => void }) {
  const mount = useRef<HTMLDivElement>(null)
  const selection = useRef(selected)
  const callback = useRef(onSelect)
  const controlsRef = useRef<OrbitControls | null>(null)
  const [unavailable, setUnavailable] = useState(false)
  useEffect(() => { selection.current = selected; callback.current = onSelect }, [selected, onSelect])

  useEffect(() => {
    const element = mount.current!
    let renderer: THREE.WebGLRenderer
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true }) }
    catch { queueMicrotask(() => setUnavailable(true)); return }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
    element.appendChild(renderer.domElement)
    renderer.domElement.setAttribute('aria-label', 'Interactive benchmark workflow')
    const scene = new THREE.Scene()
    const camera = new THREE.OrthographicCamera(-8, 8, 5, -5, .1, 100)
    camera.position.set(7, 10, 14)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableRotate = false
    controls.enableDamping = true
    controls.minZoom = .6
    controls.maxZoom = 2
    controls.mouseButtons.LEFT = THREE.MOUSE.PAN
    controls.touches.ONE = THREE.TOUCH.PAN
    controls.target.set(0, 0, 0)
    controls.update()
    controls.saveState()
    controlsRef.current = controls
    scene.add(new THREE.HemisphereLight(0xd5f8ff, 0x25252d, 3))
    const light = new THREE.DirectionalLight(0xffffff, 4)
    light.position.set(-3, 8, 5)
    scene.add(light)
    const grid = new THREE.GridHelper(40, 40, 0x39434b, 0x222930)
    grid.position.y = -.6
    scene.add(grid)
    const nodes = stages.map((stage, index) => {
      const node = new THREE.Mesh(new THREE.BoxGeometry(1.5, .55, 1.5), new THREE.MeshStandardMaterial({ color: stage.color, roughness: .35, metalness: .35 }))
      node.position.set((index - 1.5) * 3.1, 0, index % 2 ? .6 : -.6)
      scene.add(node)
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(node.geometry), new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: .4 }))
      node.add(edges)
      return node
    })
    const paths = nodes.slice(0, -1).map((node, index) => new THREE.LineCurve3(node.position.clone(), nodes[index + 1].position.clone()))
    paths.forEach(path => scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(path.getPoints(2)), new THREE.LineBasicMaterial({ color: 0x748b9b }))))
    const pulses = paths.map(() => {
      const pulse = new THREE.Mesh(new THREE.SphereGeometry(.09, 12, 12), new THREE.MeshBasicMaterial({ color: 0xffffff }))
      scene.add(pulse)
      return pulse
    })
    const raycaster = new THREE.Raycaster()
    let start = { x: 0, y: 0 }
    const pointerDown = (event: PointerEvent) => { start = { x: event.clientX, y: event.clientY } }
    const pointerUp = (event: PointerEvent) => {
      if (Math.hypot(event.clientX - start.x, event.clientY - start.y) > 6) return
      const rect = renderer.domElement.getBoundingClientRect()
      raycaster.setFromCamera(new THREE.Vector2((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1), camera)
      const hit = raycaster.intersectObjects(nodes, false)[0]
      if (hit) callback.current(nodes.indexOf(hit.object as typeof nodes[number]))
    }
    renderer.domElement.addEventListener('pointerdown', pointerDown)
    renderer.domElement.addEventListener('pointerup', pointerUp)
    const resize = new ResizeObserver(() => {
      const width = element.clientWidth
      const height = element.clientHeight
      const halfWidth = Math.max(7.8, 4.6 * width / height)
      camera.left = -halfWidth
      camera.right = halfWidth
      camera.top = halfWidth * height / width
      camera.bottom = -camera.top
      camera.updateProjectionMatrix()
      renderer.setSize(width, height)
    })
    resize.observe(element)
    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)')
    let frame = 0
    const animate = (time: number) => {
      frame = requestAnimationFrame(animate)
      nodes.forEach((node, index) => {
        node.scale.y = index === selection.current ? 1.8 : 1
        node.material.emissive.set(index === selection.current ? stages[index].color : '#000000')
        node.material.emissiveIntensity = .18
      })
      pulses.forEach((pulse, index) => pulse.position.copy(paths[index].getPoint(reducedMotion.matches ? .5 : (time / 3000 + index * .2) % 1)))
      controls.update()
      renderer.render(scene, camera)
    }
    frame = requestAnimationFrame(animate)
    return () => {
      cancelAnimationFrame(frame)
      resize.disconnect()
      controls.dispose()
      controlsRef.current = null
      renderer.domElement.removeEventListener('pointerdown', pointerDown)
      renderer.domElement.removeEventListener('pointerup', pointerUp)
      scene.traverse(object => {
        if (object instanceof THREE.Mesh || object instanceof THREE.Line) {
          object.geometry.dispose()
          const materials = Array.isArray(object.material) ? object.material : [object.material]
          materials.forEach(material => material.dispose())
        }
      })
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [])

  const zoom = (factor: number) => {
    const controls = controlsRef.current
    if (!controls) return
    const camera = controls.object as THREE.OrthographicCamera
    camera.zoom = Math.min(2, Math.max(.6, camera.zoom * factor))
    camera.updateProjectionMatrix()
  }
  return <div className="scene-wrap">
    <div ref={mount} className="workflow-canvas" />
    {unavailable && <p className="scene-fallback">3D view unavailable. Stage selection remains available below.</p>}
    <div className="scene-caption"><span className="signal-dot" /> BENCHMARK MODEL <span>ILLUSTRATIVE</span></div>
    <div className="scene-tools">
      <button title="Zoom in" aria-label="Zoom in" onClick={() => zoom(1.2)}><Plus size={16} /></button>
      <button title="Zoom out" aria-label="Zoom out" onClick={() => zoom(1 / 1.2)}><Minus size={16} /></button>
      <button title="Reset view" aria-label="Reset view" onClick={() => controlsRef.current?.reset()}><RotateCcw size={16} /></button>
    </div>
    <div className="stage-tabs" role="tablist" aria-label="Workflow stages">{stages.map((stage, index) => <button role="tab" aria-selected={selected === index} tabIndex={selected === index ? 0 : -1} key={stage.title} onClick={() => onSelect(index)} onKeyDown={event => { const next = event.key === 'ArrowRight' ? (index + 1) % stages.length : event.key === 'ArrowLeft' ? (index + stages.length - 1) % stages.length : event.key === 'Home' ? 0 : event.key === 'End' ? stages.length - 1 : null; if (next !== null) { event.preventDefault(); onSelect(next); (event.currentTarget.parentElement?.children[next] as HTMLButtonElement).focus() } }} style={{ '--stage-color': stage.color } as React.CSSProperties}><span>0{index + 1}</span>{stage.title}</button>)}</div>
  </div>
}