import * as THREE from 'three'
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js'
import { SVGLoader } from 'three/addons/loaders/SVGLoader.js'
import { siKubernetes, siTerraform, siAnsible, siGrafana, siPrometheus, siDocker, siGitlab, type SimpleIcon } from 'simple-icons'
import { factoryMotion, solveArm, robotBase, upperArmLength, forearmLength, toolOffset } from './factoryMotion'

type Parent = THREE.Object3D
type Position = [number, number, number]

export function createFactory() {
  const root = new THREE.Group()
  const materials: THREE.Material[] = []
  const textures: THREE.Texture[] = []
  const material = (color: string, metalness = .12, roughness = .3) => {
    const value = new THREE.MeshStandardMaterial({ color, metalness, roughness })
    materials.push(value)
    return value
  }
  const porcelain = material('#e7eef1')
  const white = material('#ffffff')
  const blue = material('#137dce', .25)
  const deepBlue = material('#185080', .3)
  const orange = material('#f27916', .18)
  const red = material('#cb3e30', .2)
  const mint = material('#65dbc0', .3)
  const dark = material('#26353d', .5)
  const steel = material('#9aadb5', .75, .23)
  const yellow = material('#f3bf38', .25)
  const terraformBlue = material('#5752cd', .25)
  const glass = material('#112f43', .4, .17)
  const light = material('#d0fbff')
  light.emissive.set('#69cce5')
  light.emissiveIntensity = .7
  const mesh = (parent: Parent, geometry: THREE.BufferGeometry, surface: THREE.Material, position: Position) => {
    const value = new THREE.Mesh(geometry, surface)
    value.position.set(...position)
    value.castShadow = true
    value.receiveShadow = true
    parent.add(value)
    return value
  }
  const box = (parent: Parent, size: Position, position: Position, surface: THREE.Material, radius = .08) => mesh(parent, new RoundedBoxGeometry(...size, 3, radius), surface, position)
  const cylinder = (parent: Parent, radius: number, height: number, position: Position, surface: THREE.Material, top = radius) => mesh(parent, new THREE.CylinderGeometry(top, radius, height, 40), surface, position)
  const tube = (parent: Parent, points: Position[], surface: THREE.Material, radius = .065) => {
    const curve = new THREE.CatmullRomCurve3(points.map(point => new THREE.Vector3(...point)), false, 'centripetal')
    mesh(parent, new THREE.TubeGeometry(curve, 64, radius, 10, false), surface, [0, 0, 0])
    return curve
  }
  const label = (parent: Parent, text: string, width: number, height: number, position: Position, background = '#123345', foreground = '#ffffff') => {
    const canvas = document.createElement('canvas')
    canvas.width = 768
    canvas.height = Math.round(768 * height / width)
    const context = canvas.getContext('2d')!
    context.fillStyle = background
    context.fillRect(0, 0, canvas.width, canvas.height)
    context.fillStyle = foreground
    context.font = `600 ${Math.floor(canvas.height * .48)}px sans-serif`
    context.textAlign = 'center'
    context.textBaseline = 'middle'
    context.fillText(text, canvas.width / 2, canvas.height / 2, canvas.width - 32)
    const texture = new THREE.CanvasTexture(canvas)
    texture.colorSpace = THREE.SRGBColorSpace
    textures.push(texture)
    const surface = new THREE.MeshBasicMaterial({ map: texture })
    materials.push(surface)
    return mesh(parent, new THREE.PlaneGeometry(width, height), surface, position)
  }
  const bolt = (parent: Parent, position: Position) => {
    const screw = cylinder(parent, .043, .025, position, steel)
    screw.rotation.x = Math.PI / 2
  }
  const logo = (parent: Parent, icon: SimpleIcon, size: number, position: Position, surface: THREE.Material) => {
    const group = new THREE.Group()
    group.name = `logo-${icon.slug}`
    group.position.set(...position)
    group.scale.set(size / 24, -size / 24, size / 24)
    const artwork = new SVGLoader().parse(icon.svg)
    for (const path of artwork.paths) for (const shape of path.toShapes()) {
      const geometry = new THREE.ExtrudeGeometry(shape, { depth: .65, bevelEnabled: false, curveSegments: 12 })
      geometry.translate(-12, -12, 0)
      mesh(group, geometry, surface, [0, 0, 0])
    }
    parent.add(group)
    return group
  }
  const stations = Array.from({ length: 4 }, (_, index) => {
    const group = new THREE.Group()
    group.userData.stage = index
    root.add(group)
    return group
  })
  const anchors = [new THREE.Vector3(-5.5, .8, .9), new THREE.Vector3(-1.9, 1.3, -4.3), new THREE.Vector3(4.1, 1.6, -.2), new THREE.Vector3(-8, 1.8, -2.1)]
  const rings = anchors.map((anchor, index) => {
    const ring = mesh(root, new THREE.TorusGeometry(index === 1 ? 2.25 : 1.5, .025, 8, 90), light, [anchor.x, .065, anchor.z])
    ring.rotation.x = Math.PI / 2
    return ring
  })

  const platform = stations[0]
  platform.position.set(-1.8, 0, -2.4)
  for (let index = 0; index < 6; index++) {
    const column = index % 3
    const row = Math.floor(index / 3)
    const position: Position = [-5.2 + column * 1.45, .23, 2.2 + row * 1.5]
    box(platform, [1.23, .34, 1.22], position, porcelain, .13)
    box(platform, [.92, .08, .9], [position[0], .44, position[2]], deepBlue)
    box(platform, [.78, .76, .78], [position[0], .86, position[2]], column === 0 ? mint : blue)
    for (let rib = 0; rib < 5; rib++) box(platform, [.035, .55, .025], [position[0] - .28 + rib * .14, .86, position[2] + .4], white, .008)
    box(platform, [.18, .045, .025], [position[0] + .2, 1.14, position[2] + .42], light)
  }
  box(platform, [3.35, .16, .65], [-3.75, .17, 5.12], steel)
  const containerSign = label(platform, 'CONTAINER REGISTRY', 3.08, .42, [-3.75, .29, 5.16])
  containerSign.rotation.x = -Math.PI / 3
  logo(platform, siDocker, .65, [-3.75, 1.8, 3.7], blue)
  tube(platform, [[-5.2, .16, 2.2], [-5.9, .16, 2.2], [-6.3, .16, 1.5], [-6.3, .16, -.8]], white, .08)

  const delivery = stations[1]
  delivery.position.set(-2, 0, -2.2)
  box(delivery, [7.3, .64, 1.54], [.2, .6, -1.8], porcelain, .27)
  box(delivery, [6.6, .27, 1.38], [.2, .98, -1.8], dark)
  box(delivery, [7.2, .14, .12], [.2, .65, -.98], red)
  box(delivery, [7.2, .14, .12], [.2, .65, -2.62], red)
  const slats = Array.from({ length: 30 }, (_, index) => box(delivery, [.215, .09, 1.42], [-3.2 + index * .235, 1.15, -1.8], red, .025))
  for (const end of [-3.25, 3.65]) {
    const roller = cylinder(delivery, .38, 1.42, [end, .82, -1.8], steel)
    roller.rotation.x = Math.PI / 2
    for (const depth of [-2.52, -1.08]) {
      const cap = cylinder(delivery, .3, .07, [end, .82, depth], red)
      cap.rotation.x = Math.PI / 2
    }
  }
  for (const offset of [-2.65, 2.95]) for (const depth of [-2.25, -1.35]) {
    cylinder(delivery, .105, .5, [offset, .28, depth], steel)
    cylinder(delivery, .23, .12, [offset, .06, depth], red)
  }
  box(delivery, [1.8, 2.05, 1.15], [-2.4, 1.7, -3], porcelain, .26)
  box(delivery, [1.48, 1.39, .08], [-2.4, 1.85, -2.38], glass, .15)
  label(delivery, 'BUILD', .95, .26, [-2.4, 2.3, -2.33], '#112f43', '#88e4fa')
  for (let row = 0; row < 4; row++) box(delivery, [.85 - row * .12, .045, .015], [-2.52, 2.05 - row * .16, -2.31], row === 3 ? mint : light)
  cylinder(delivery, .3, .13, [-2.4, 2.79, -3], red)
  tube(delivery, [[.1, .3, -.85], [.1, 2.4, -.85], [.1, 2.7, -1.1], [.1, 2.7, -2.5], [.1, 2.4, -2.75], [.1, .3, -2.75]], red, .115)
  label(delivery, 'TEST', .8, .28, [.1, 2.24, -.71], '#cb3e30')
  box(delivery, [.75, .45, .12], [.1, 1.65, -.69], steel)
  label(delivery, 'PASS', .63, .3, [.1, 1.65, -.62], '#267965')
  box(delivery, [.16, .9, 1.45], [.1, 1.6, -1.8], new THREE.MeshPhysicalMaterial({ color: '#80e6e5', transparent: true, opacity: .14, depthWrite: false, roughness: .1 }))
  for (const offset of [1.8, 2.0]) cylinder(delivery, .055, 3.3, [offset, 1.65, -3.2], steel)
  box(delivery, [2.8, .87, .18], [1.9, 3.43, -3.2], porcelain, .15)
  label(delivery, 'CI / CD', 1.75, .62, [2.19, 3.43, -3.1], '#f6d6cc', '#ab3323')
  logo(delivery, siGitlab, .55, [.94, 3.43, -3.07], orange)
  const parcel = new THREE.Group()
  parcel.name = 'active-package'
  root.add(parcel)
  box(parcel, [.56, .6, .6], [0, .3, 0], blue)
  box(parcel, [.11, .012, .6], [0, .608, 0], white)
  logo(parcel, siDocker, .32, [0, .32, .307], white)
  label(delivery, 'RELEASE', 1.05, .28, [2.8, .66, -.965], '#e7eef1', '#273f4a')

  const robotics = stations[2]
  const robot = new THREE.Group()
  robot.position.set(robotBase.x, 0, robotBase.z)
  robotics.add(robot)
  cylinder(robot, 1.13, .22, [0, .15, 0], blue)
  cylinder(robot, .94, .18, [0, .35, 0], porcelain)
  cylinder(robot, .6, .16, [0, .48, 0], steel)
  cylinder(robot, .48, 1.14, [0, 1.02, 0], porcelain, .33)
  const shoulder = new THREE.Group()
  shoulder.position.y = 1.57
  robot.add(shoulder)
  const joint = (parent: Parent, position: Position, radius = .33) => {
    const value = cylinder(parent, radius, .48, position, blue)
    value.rotation.x = Math.PI / 2
    const inset = cylinder(parent, radius * .66, .025, [position[0], position[1], position[2] + .254], steel)
    inset.rotation.x = Math.PI / 2
    bolt(parent, [position[0], position[1], position[2] + .28])
  }
  joint(shoulder, [0, 0, 0], .44)
  box(shoulder, [.43, upperArmLength, .4], [0, upperArmLength / 2, 0], porcelain, .16)
  box(shoulder, [.22, 1.4, .035], [0, 1, .22], deepBlue)
  const elbow = new THREE.Group()
  elbow.position.y = upperArmLength
  shoulder.add(elbow)
  joint(elbow, [0, 0, 0])
  box(elbow, [.35, forearmLength, .34], [0, forearmLength / 2, 0], porcelain, .13)
  const wrist = new THREE.Group()
  wrist.position.y = forearmLength
  elbow.add(wrist)
  joint(wrist, [0, 0, 0], .25)
  box(wrist, [.55, .21, .37], [0, .23, 0], steel)
  box(wrist, [.12, .47, .15], [0, .47, 0], steel)
  const grip = new THREE.Group()
  grip.name = 'package-grip'
  grip.position.y = toolOffset
  wrist.add(grip)
  const fingers = [-1, 1].map(side => {
    const finger = new THREE.Group()
    wrist.add(finger)
    box(finger, [.07, .65, .24], [0, .94, 0], dark)
    box(finger, [.14, .055, .24], [-side * .035, 1.28, 0], steel)
    return finger
  })
  tube(shoulder, [[.22, -.1, -.3], [.34, .7, -.3], [.3, 1.7, -.3], [0, 2, -.3]], dark, .045)
  logo(robot, siKubernetes, .64, [0, 1.07, .49], blue)
  label(robot, 'Kubernetes', 1.7, .25, [0, .3, 1.14], '#137dce')
  for (let index = 0; index < 3; index++) {
    box(robotics, [1.05, .26, 1.05], [6.4, .2, -3 + index * 1.55], porcelain)
    box(robotics, [.62, .65, .62], [6.4, .65, -3 + index * 1.55], blue)
  }
  label(robotics, 'ORCHESTRATION', 2.6, .35, [6, .3, 1], '#26353d')
  const pallet = new THREE.Group()
  pallet.name = 'transfer-pallet'
  root.add(pallet)
  for (const side of [-.42, .42]) box(pallet, [.16, .14, .94], [side, .07, 0], porcelain)
  box(pallet, [1.08, .09, .94], [0, .185, 0], porcelain)
  for (const side of [-.5, .5]) box(robotics, [.1, .32, 1], [4.3 + side, .16, .8], steel)

  const forklift = new THREE.Group()
  forklift.name = 'terraform-forklift'
  robotics.add(forklift)
  box(forklift, [1.15, .58, 1.35], [0, .65, .12], terraformBlue, .18)
  box(forklift, [1.08, .62, .45], [0, 1.03, .55], terraformBlue, .12)
  box(forklift, [.62, .14, .5], [0, 1.05, .1], yellow)
  box(forklift, [.62, .58, .14], [0, 1.33, .36], yellow)
  const wheels: THREE.Mesh[] = []
  for (const side of [-1, 1]) for (const axle of [-.45, .56]) {
    const wheel = cylinder(forklift, .3, .2, [side * .6, .3, axle], dark)
    wheel.rotation.z = Math.PI / 2
    wheels.push(wheel)
    const hub = cylinder(forklift, .19, .22, [side * .6, .3, axle], steel)
    hub.rotation.z = Math.PI / 2
  }
  for (const side of [-.46, .46]) {
    box(forklift, [.085, 1.55, .085], [side, 1.62, .48], terraformBlue)
    box(forklift, [.085, 1.55, .085], [side, 1.62, -.46], terraformBlue)
    box(forklift, [.1, 2.05, .13], [side, 1.1, -.76], steel)
  }
  box(forklift, [1.18, .13, 1.12], [0, 2.38, .01], terraformBlue)
  logo(forklift, siTerraform, .75, [0, 2.95, -.15], terraformBlue)
  label(forklift, 'Terraform', 1.04, .23, [0, 2.35, .58], '#5752cd')
  const steering = mesh(forklift, new THREE.TorusGeometry(.18, .035, 10, 24), dark, [0, 1.45, -.32])
  steering.rotation.x = -.5
  const forks = new THREE.Group()
  forks.name = 'fork-carriage'
  forklift.add(forks)
  box(forks, [.97, .34, .12], [0, .17, -.75], yellow)
  for (const side of [-.3, .3]) box(forks, [.13, .06, 1.02], [side, -.03, -1.18], yellow, .025)
  const load = new THREE.Group()
  load.name = 'forklift-load'
  load.position.set(0, .23, -1.25)
  forks.add(load)
  for (const side of [-.44, .44]) box(forklift, [.16, .12, .05], [side, .85, -.58], light)
  cylinder(forklift, .1, .12, [.38, 2.51, .3], orange)

  const ansible = new THREE.Group()
  ansible.position.set(.1, 0, 1.45)
  robotics.add(ansible)
  box(ansible, [2.25, .35, 1.55], [0, .25, 0], dark, .2)
  box(ansible, [1.45, 1.6, .22], [.35, 1.22, -.55], dark, .2)
  box(ansible, [1.25, 1.3, .06], [.35, 1.24, -.41], porcelain, .15)
  logo(ansible, siAnsible, 1.05, [.35, 1.28, -.367], dark)
  label(ansible, 'Ansible', 1.4, .3, [.35, 2.21, -.4], '#26353d')
  for (let index = 0; index < 5; index++) cylinder(ansible, .13, .07, [.05 + index % 3 * .37, .47, -.02 + Math.floor(index / 3) * .43], yellow)
  cylinder(ansible, .29, .1, [-.75, .49, .15], steel)
  const joystick = new THREE.Group()
  joystick.position.set(-.75, .55, .15)
  ansible.add(joystick)
  cylinder(joystick, .055, .65, [0, .32, 0], yellow)
  mesh(joystick, new THREE.SphereGeometry(.19, 24, 16), yellow, [0, .69, 0])

  const monitoring = stations[3]
  const console = new THREE.Group()
  console.position.set(-8, 0, -2)
  console.rotation.y = .12
  monitoring.add(console)
  box(console, [2.65, .22, 1.02], [0, .15, 0], dark, .14)
  box(console, [2.45, 3.65, .49], [0, 1.95, 0], orange, .3)
  box(console, [2.15, 3.26, .16], [0, 1.97, .26], porcelain, .23)
  label(console, 'Grafana', 1.9, .28, [0, 3.26, .352], '#e7eef1', '#27444f')
  box(console, [1.82, 1.28, .1], [0, 1.38, .4], glass, .16)
  for (let index = 0; index < 5; index++) box(console, [.2, .22 + index * .14, .085], [-.65 + index * .32, 1.0 + index * .07, .49], index % 2 ? yellow : orange, .025)
  tube(console, [[-.71, 1.69, .5], [-.35, 1.56, .5], [0, 1.75, .5], [.35, 1.83, .5], [.7, 1.88, .5]], orange, .035)
  logo(console, siGrafana, 1.02, [0, 2.55, .44], orange)
  for (const offset of [-.9, .9]) for (const height of [.55, 3.39]) bolt(console, [offset, height, .36])
  label(console, 'METRICS / LOGS / TRACES', 1.72, .17, [0, .57, .353], '#e7eef1', '#49606a')
  const tank = new THREE.Group()
  tank.position.set(-8, 0, 1.4)
  monitoring.add(tank)
  cylinder(tank, .86, .25, [0, .17, 0], orange)
  cylinder(tank, .72, 1.56, [0, 1.03, 0], porcelain)
  cylinder(tank, .72, .25, [0, 1.89, 0], porcelain, .54)
  cylinder(tank, .54, .12, [0, 2.07, 0], steel)
  const port = cylinder(tank, .37, .13, [0, 1.15, .72], orange)
  port.rotation.x = Math.PI / 2
  const face = cylinder(tank, .29, .025, [0, 1.15, .8], white)
  face.rotation.x = Math.PI / 2
  logo(tank, siPrometheus, .43, [0, 1.15, .822], orange)
  for (const offset of [-.4, .4]) {
    const socket = cylinder(tank, .14, .17, [offset, .52, .62], orange)
    socket.rotation.x = Math.PI / 2
  }
  const flameShape = new THREE.Shape()
  flameShape.moveTo(-.4, 0)
  flameShape.bezierCurveTo(-.7, .4, -.25, .62, -.29, 1.02)
  flameShape.bezierCurveTo(-.02, .84, -.12, .6, .07, .53)
  flameShape.bezierCurveTo(.32, .76, .21, 1.1, .26, 1.2)
  flameShape.bezierCurveTo(.77, .65, .58, .22, .4, 0)
  flameShape.closePath()
  const flame = mesh(tank, new THREE.ExtrudeGeometry(flameShape, { depth: .18, bevelEnabled: true, bevelThickness: .035, bevelSize: .035, bevelSegments: 3, steps: 1 }), orange, [0, 2.46, -.05])
  cylinder(tank, .47, .13, [0, 2.32, 0], orange)
  label(tank, 'Prometheus', 1.6, .24, [0, .14, .871], '#f27916', '#ffffff')
  const cablePaths = [
    tube(root, [[-8.4, .52, 2.02], [-8.4, .16, 2.7], [-7.8, .16, 3.15], [-2, .16, 3.15], [-1.5, .16, 2.6], [-1.5, .16, 1.6], [-.9, .2, 1.6]], white, .07),
    tube(root, [[-7.6, .52, 2.02], [-7.4, .16, 2.45], [-6.9, .16, 2.45], [-6.3, .16, 1.5]], white, .07),
    tube(root, [[-8, .5, -1.6], [-8.8, .18, -1.1], [-8.8, .18, .9], [-8.6, .65, 1.4]], white, .075),
    tube(root, [[1.1, .16, 1.5], [1.8, .16, 1.5], [2, .16, .5], [2, .16, -1.1], [3.3, .2, -1.3]], white, .07),
    tube(root, [[6.4, .16, -3], [7.25, .16, -3], [7.5, .16, -2.5], [7.5, .16, .1], [6.4, .16, .1]], white, .07),
  ]
  for (let index = 0; index < 14; index++) box(root, [.38, .012, .04], [-3.6 + index * .7, -.035, 4.15], yellow, .008)
  for (const side of [-.55, .55]) box(root, [.08, .025, 1.15], [-2.8 + side, 0, 5.1], yellow)
  const depot = label(root, 'DEPLOYMENT', 2.1, .35, [-2.8, .04, 6.05], '#344950', '#e7eef1')
  depot.rotation.x = -Math.PI / 2
  const packets = cablePaths.map(() => mesh(root, new THREE.SphereGeometry(.115, 12, 12), mint, [0, 0, 0]))
  const ground = mesh(root, new THREE.PlaneGeometry(200, 200), material('#344950', .28, .42), [0, -.08, 0])
  ground.rotation.x = -Math.PI / 2
  ground.castShadow = false
  const grid = new THREE.GridHelper(70, 70, '#57737b', '#415a63')
  grid.position.y = -.07
  root.add(grid)
  stations.forEach((station, index) => station.traverse(object => { object.userData.stage = index }))

  return {
    root, stations, anchors, parcel, pallet, forklift, grip,
    update(time: number, selected: number) {
      const state = factoryMotion(time)
      rings.forEach((ring, index) => { ring.visible = selected === index })
      const beltTime = Math.min(state.seconds, 7)
      slats.forEach((slat, index) => { slat.position.x = -3.2 + (index * .235 + beltTime * .92) % 7.05 })
      const angles = solveArm(state.armTarget)
      shoulder.rotation.z = angles.shoulder
      elbow.rotation.z = angles.elbow
      wrist.rotation.z = angles.wrist
      robot.rotation.y = angles.yaw
      fingers.forEach((finger, index) => { finger.position.x = (index ? 1 : -1) * (state.closed ? .32 : .45) })
      forklift.position.copy(state.forkliftPosition)
      forklift.rotation.y = state.forkliftYaw
      forks.position.y = state.forkHeight
      wheels.forEach(wheel => { wheel.rotation.x = state.forkliftPosition.x * 3 + state.forkliftPosition.z * 3 })
      joystick.rotation.z = state.owner === 'forklift' ? Math.sin(time) * .14 : 0
      const carrier = state.owner === 'gripper' ? grip : state.owner === 'forklift' ? load : root
      carrier.add(parcel)
      parcel.rotation.set(0, 0, 0)
      if (carrier === grip) parcel.rotation.z = Math.PI
      parcel.position.copy(carrier === root ? state.packagePosition : new THREE.Vector3())
      if (state.owner === 'forklift') { load.add(pallet); pallet.position.set(0, -.23, 0); pallet.rotation.set(0, 0, 0) }
      else { root.add(pallet); pallet.position.copy(state.owner === 'destination' ? state.packagePosition : new THREE.Vector3(4.3, .55, .8)).add(new THREE.Vector3(0, -.23, 0)); pallet.rotation.set(0, state.owner === 'destination' ? Math.PI / 2 : 0, 0) }
      parcel.userData.stage = state.owner === 'belt' ? 1 : 2
      parcel.traverse(object => { object.userData.stage = parcel.userData.stage })
      flame.position.y = 2.46 + Math.sin(time * 1.4) * .06
      flame.rotation.y = Math.sin(time * .6) * .16
      packets.forEach((packet, index) => packet.position.copy(cablePaths[index].getPoint((time * .13 + index * .3) % 1)))
      root.updateMatrixWorld(true)
      return state
    },
    dispose() {
      const geometries = new Set<THREE.BufferGeometry>()
      root.traverse(object => {
        if (object instanceof THREE.Mesh || object instanceof THREE.Line) {
          geometries.add(object.geometry)
          for (const surface of Array.isArray(object.material) ? object.material : [object.material]) materials.push(surface)
        }
      })
      geometries.forEach(geometry => geometry.dispose())
      new Set(materials).forEach(surface => surface.dispose())
      textures.forEach(texture => texture.dispose())
    },
  }
}