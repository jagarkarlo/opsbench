import * as THREE from 'three'
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js'
import { SVGLoader } from 'three/addons/loaders/SVGLoader.js'
import { siKubernetes, siTerraform, siAnsible, siGrafana, siPrometheus, siDocker, siGit, siJira, type SimpleIcon } from 'simple-icons'
import { factoryMotion, solveArm, robotBase, upperArmLength, forearmLength, toolOffset, handoff, orchestrationSlots, platformDrop } from './factoryMotion'

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
  const tube = (parent: Parent, points: Position[], surface: THREE.Material, radius = .065, name = '') => {
    const curve = new THREE.CatmullRomCurve3(points.map(point => new THREE.Vector3(...point)), false, 'centripetal')
    const cable = mesh(parent, new THREE.TubeGeometry(curve, 64, radius, 10, false), surface, [0, 0, 0])
    cable.name = name
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
  const anchors = [new THREE.Vector3(-10.8, .95, -4.15), new THREE.Vector3(-1.9, 1.3, -4.3), new THREE.Vector3(6.1, 1.6, -.8), new THREE.Vector3(0, 1.8, 4.4)]
  const rings = anchors.map((anchor, index) => {
    const ring = mesh(root, new THREE.TorusGeometry(index === 1 ? 2.25 : 1.5, .025, 8, 90), light, [anchor.x, .065, anchor.z])
    ring.rotation.x = Math.PI / 2
    return ring
  })

  const platform = stations[0]
  platform.position.x = -2.8
  for (const [index, title] of ['JIRA', 'CODE', 'GIT'].entries()) {
    const position = -10.8 + index * 2.8
    box(platform, [1.55, .3, 1.6], [position, .22, -4], porcelain).name = `source-${title.toLowerCase()}`
    box(platform, [1.25, .04, .08], [position, .4, -3.28], light)
    label(platform, title, 1.3, .3, [position, .25, -3.18], '#26353d')
  }
  logo(platform, siJira, .85, [-10.8, 1.65, -4], blue)
  box(platform, [1.18, .7, .12], [-10.8, .82, -3.9], dark)
  label(platform, 'OPS-042', .95, .25, [-10.8, .91, -3.83])
  label(platform, 'IN PROGRESS', 1, .19, [-10.8, .61, -3.83], '#267965')
  box(platform, [1.3, .09, .88], [-8, .47, -3.85], steel)
  box(platform, [1.3, .94, .08], [-8, .97, -4.22], dark)
  box(platform, [1.13, .74, .025], [-8, .99, -4.17], glass)
  label(platform, '</>', .8, .4, [-8, 1.03, -4.15], '#112f43', '#65dbc0')
  for (let row = 0; row < 3; row++) for (let key = 0; key < 8; key++) box(platform, [.095, .016, .085], [-8.48 + key * .135, .524, -4.02 + row * .13], dark, .01)
  logo(platform, siGit, .95, [-5.2, 1.4, -4], orange)
  cylinder(platform, .08, .55, [-5.2, .67, -4], steel)
  const cablePaths = [
    tube(root, [[-12.8, .2, -4], [-12.45, .2, -4], [-11.95, .2, -4]], light),
    tube(root, [[-9.65, .2, -4], [-9.3, .2, -4], [-8.85, .2, -4]], light),
    tube(root, [[-7.2, .2, -4], [-6.35, .2, -4], [-5.5, .65, -4]], light),
  ]

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
  box(delivery, [.85, 1.7, .2], [-3.05, 1.6, -2.56], porcelain)
  box(delivery, [.85, 1.7, .2], [-3.05, 1.6, -1.04], porcelain)
  box(delivery, [.85, .35, 1.7], [-3.05, 2.5, -1.8], porcelain)
  label(delivery, 'BUILD', .77, .28, [-3.05, 2.48, -.94], '#112f43', '#88e4fa')
  box(delivery, [.08, 1.13, .08], [-2.59, 1.8, -1.1], light)
  box(delivery, [.08, 1.13, .08], [-2.59, 1.8, -2.5], light)
  cylinder(delivery, .18, .13, [-3.05, 2.74, -1.8], orange)
  tube(delivery, [[.1, .3, -.85], [.1, 2.4, -.85], [.1, 2.7, -1.1], [.1, 2.7, -2.5], [.1, 2.4, -2.75], [.1, .3, -2.75]], red, .115)
  label(delivery, 'QUALITY GATE', 1.42, .32, [.1, 2.3, -.71], '#26353d', '#d0fbff')
  box(delivery, [.92, .66, .12], [.1, 1.62, -.69], porcelain)
  const checkShape = new THREE.Shape()
  checkShape.moveTo(-.32, .02)
  checkShape.lineTo(-.19, -.11)
  checkShape.lineTo(-.04, .04)
  checkShape.lineTo(.29, .39)
  checkShape.lineTo(.39, .28)
  checkShape.lineTo(-.04, -.17)
  checkShape.closePath()
  mesh(delivery, new THREE.ExtrudeGeometry(checkShape, { depth: .035, bevelEnabled: false }), mint, [.1, 1.52, -.62])
  box(delivery, [.16, .9, 1.45], [.1, 1.6, -1.8], new THREE.MeshPhysicalMaterial({ color: '#80e6e5', transparent: true, opacity: .14, depthWrite: false, roughness: .1 }))
  for (const offset of [1.8, 2.0]) cylinder(delivery, .055, 3.3, [offset, 1.65, -3.2], steel)
  box(delivery, [2.8, .87, .18], [1.9, 3.43, -3.2], porcelain, .15)
  label(delivery, 'CI / CD', 1.75, .62, [2.19, 3.43, -3.1], '#f6d6cc', '#ab3323')
  logo(delivery, siGit, .55, [.94, 3.43, -3.07], orange)
  const parcel = new THREE.Group()
  parcel.name = 'active-package'
  root.add(parcel)
  box(parcel, [.56, .6, .6], [0, .3, 0], blue)
  box(parcel, [.11, .012, .6], [0, .608, 0], white)
  logo(parcel, siDocker, .32, [0, .32, .307], white)
  label(delivery, 'RELEASE', 1.05, .28, [2.8, .66, -.965], '#e7eef1', '#273f4a')
  label(delivery, 'v1.4.2', 1.08, .34, [2.8, 1.8, -2.43], '#267965')
  box(delivery, [.08, .8, .08], [2.8, 1.39, -2.47], steel)
  box(delivery, [6.9, .05, .04], [.2, 1.07, -.99], light)

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
  for (const [slotIndex, slot] of orchestrationSlots.entries()) {
    const platform = new THREE.Group()
    platform.name = `orchestration-platform-${slotIndex + 1}`
    platform.position.copy(slot)
    robotics.add(platform)
    box(platform, [1.42, .23, 1.24], [0, 0, 0], porcelain)
    box(platform, [1.18, .03, .05], [0, .125, .61], light)
    for (const side of slotIndex === orchestrationSlots.length - 1 ? [-.32] : [-.32, .32]) {
      const container = new THREE.Group()
      container.name = 'deployed-container'
      container.position.set(side, .42, 0)
      platform.add(container)
      box(container, [.54, .6, .72], [0, 0, 0], blue)
      box(container, [.09, .012, .72], [0, .306, 0], white)
      logo(container, siDocker, .28, [0, .02, .367], white)
    }
  }
  const yardLabel = label(robotics, 'ORCHESTRATION', 2.8, .35, [7.45, .04, -4.55], '#344950', '#b2fff0')
  yardLabel.rotation.x = -Math.PI / 2
  for (const side of [-1, 1]) {
    box(robotics, [.04, .025, 1.65], [platformDrop.x + side * .84, .015, platformDrop.z], yellow, .008)
    box(robotics, [1.72, .025, .04], [platformDrop.x, .015, platformDrop.z + side * .82], yellow, .008)
  }
  const pallet = new THREE.Group()
  pallet.name = 'transfer-pallet'
  root.add(pallet)
  for (const side of [-.42, .42]) box(pallet, [.16, .14, 1.24], [side, .07, 0], porcelain)
  box(pallet, [1.42, .09, 1.24], [0, .185, 0], porcelain)
  const docker = new THREE.Group()
  docker.name = 'stationary-docker-platform'
  docker.position.copy(handoff).setY(0)
  robotics.add(docker)
  box(docker, [1.65, 1.12, 1.55], [0, .56, 0], porcelain)
  box(docker, [1.5, .04, .08], [0, .91, .79], light)
  label(docker, 'DOCKER', 1.32, .3, [0, .65, .79], '#137dce')
  box(docker, [2.15, .08, 1.36], [-.25, 1.08, 0], dark)
  for (let index = 0; index < 10; index++) {
    const roller = cylinder(docker, .09, 1.34, [-1.2 + index * .2, handoff.y - .09, 0], steel)
    roller.rotation.x = Math.PI / 2
  }
  box(docker, [.14, 1.5, .14], [.3, .85, -1.2], steel)
  box(docker, [1.45, 1.12, .14], [.3, 1.88, -1.2], dark)
  logo(docker, siDocker, .85, [.3, 2.02, -1.11], blue)
  label(docker, 'Docker', 1.16, .27, [.3, 1.55, -1.12], '#26353d')
  tube(docker, [[.3, .13, -1.2], [.65, .13, -1.05], [.65, .45, -.77]], light)

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
  for (const side of [-.3, .3]) box(forks, [.13, .06, 1.42], [side, -.03, -1.4], yellow, .025)
  const load = new THREE.Group()
  load.name = 'forklift-load'
  load.position.set(0, .23, -1.7)
  forks.add(load)
  for (const side of [-.44, .44]) box(forklift, [.16, .12, .05], [side, .85, -.58], light)
  cylinder(forklift, .1, .12, [.38, 2.51, .3], orange)

  const ansible = new THREE.Group()
  ansible.name = 'ansible-console'
  ansible.position.set(7, 0, 3.4)
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
  console.position.set(-1.7, 0, 4.7)
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
  label(console, 'METRICS', 1.72, .17, [0, .57, .353], '#e7eef1', '#49606a')
  const tank = new THREE.Group()
  tank.position.set(2, 0, 4.7)
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
  cablePaths.push(
    tube(root, [[5.45, .16, -3.4], [5.45, .16, -1.45], [5.45, .16, .5], [5.45, .16, 1.7]], light, .065, 'connection-orchestration-bus'),
    tube(root, [[7, .16, 2.62], [7, .16, 1.9], [6.8, .16, 1.7], [5.45, .16, 1.7]], light, .065, 'connection-ansible-orchestration'),
    tube(root, [[5.45, .16, 1.7], [4.6, .16, 1.7], [4.35, .16, 2.1], [4.35, .16, 3.8], [3.9, .16, 4.2], [2.65, .52, 4.3]], light, .065, 'connection-orchestration-prometheus'),
    tube(root, [[1.3, .52, 4.4], [.4, .18, 4.4], [-.35, .3, 4.55]], light, .065, 'connection-prometheus-grafana'),
  )
  for (const depth of [-3.4, -1.45, .5]) {
    cablePaths.push(tube(root, [[5.45, .16, depth], [5.57, .16, depth], [5.69, .16, depth]], light, .065, `connection-platform-inner-${depth}`))
    cablePaths.push(tube(root, [[7.11, .16, depth], [7.45, .16, depth], [7.79, .16, depth]], light, .065, `connection-platform-outer-${depth}`))
  }
  for (const [text, position, width] of [
    ['ANSIBLE', [7, .06, 4.6], 1.4],
    ['PROMETHEUS', [2, .06, 5.72], 2.1],
    ['GRAFANA', [-1.7, .06, 5.72], 1.4],
  ] as [string, Position, number][]) {
    const sign = label(root, text, width, .3, position, '#344950', '#b2fff0')
    sign.rotation.x = -Math.PI / 2
  }
  for (let index = 0; index < 6; index++) for (const side of [-1, 1]) box(root, [.3, .012, .04], [9.6 + index * .65, -.035, .5 + side * 1.1], yellow, .008)
  const depot = label(root, 'INFRASTRUCTURE', 2.5, .35, [11.4, .04, 2.15], '#344950', '#e7eef1')
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
    root, stations, anchors, parcel, pallet, forklift, grip, docker,
    update(time: number, selected: number) {
      const state = factoryMotion(time)
      rings.forEach((ring, index) => { ring.visible = selected === index })
      const beltTime = Math.min(state.seconds, 9)
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
      wheels.forEach(wheel => { wheel.rotation.x = state.forkliftPosition.x / .3 })
      joystick.rotation.z = state.owner === 'destination' ? Math.sin(time) * .14 : 0
      const carrier = state.owner === 'gripper' ? grip : root
      carrier.add(parcel)
      parcel.rotation.set(0, 0, 0)
      if (carrier === grip) parcel.rotation.z = Math.PI
      parcel.position.copy(carrier === root ? state.packagePosition : new THREE.Vector3())
      if (state.platformOnForklift) { load.add(pallet); pallet.position.set(0, -.23, 0) }
      else { root.add(pallet); pallet.position.copy(state.platformPosition) }
      pallet.rotation.set(0, state.platformOnForklift ? -state.forkliftYaw : 0, 0)
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