import * as THREE from 'three'
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js'

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
  const stations = Array.from({ length: 4 }, (_, index) => {
    const group = new THREE.Group()
    group.userData.stage = index
    root.add(group)
    return group
  })
  const anchors = [new THREE.Vector3(-3.7, .8, 3.3), new THREE.Vector3(.1, 1.3, -2.1), new THREE.Vector3(5, 1.6, .8), new THREE.Vector3(-5.5, 1.8, -2.1)]
  const rings = anchors.map((anchor, index) => {
    const ring = mesh(root, new THREE.TorusGeometry(index === 1 ? 2.25 : 1.5, .025, 8, 90), light, [anchor.x, .065, anchor.z])
    ring.rotation.x = Math.PI / 2
    return ring
  })

  const platform = stations[0]
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
  tube(platform, [[-5.2, .16, 2.2], [-5.9, .16, 2.2], [-6.3, .16, 1.5], [-6.3, .16, -.8]], white, .08)

  const delivery = stations[1]
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
  label(delivery, 'CI / CD', 2.52, .62, [1.9, 3.43, -3.1], '#f6d6cc', '#ab3323')
  const parcels = Array.from({ length: 4 }, () => {
    const group = new THREE.Group()
    delivery.add(group)
    box(group, [.56, .6, .6], [0, .3, 0], blue)
    box(group, [.11, .012, .6], [0, .608, 0], white)
    label(group, 'pkg', .33, .19, [0, .32, .307], '#137dce')
    return group
  })
  label(delivery, 'RELEASE', 1.05, .28, [2.8, .66, -.965], '#e7eef1', '#273f4a')

  const robotics = stations[2]
  const robot = new THREE.Group()
  robot.position.set(5, 0, 1.1)
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
  box(shoulder, [.43, 1.4, .4], [0, .63, 0], porcelain, .16)
  box(shoulder, [.22, .82, .035], [0, .63, .22], deepBlue)
  const elbow = new THREE.Group()
  elbow.position.y = 1.3
  shoulder.add(elbow)
  joint(elbow, [0, 0, 0])
  box(elbow, [.35, 1.16, .34], [0, .54, 0], porcelain, .13)
  const wrist = new THREE.Group()
  wrist.position.y = 1.13
  elbow.add(wrist)
  joint(wrist, [0, 0, 0], .25)
  box(wrist, [.55, .21, .37], [0, .23, 0], steel)
  for (const side of [-1, 1]) {
    box(wrist, [.085, .42, .2], [side * .24, .48, 0], dark)
    box(wrist, [.16, .09, .2], [side * .2, .68, 0], steel)
  }
  tube(shoulder, [[.22, -.1, -.3], [.34, .4, -.3], [.3, 1, -.3], [0, 1.3, -.3]], dark, .045)
  label(robot, 'K8s', .53, .32, [0, 1.05, .453], '#e7eef1', '#126db2')
  for (let index = 0; index < 3; index++) {
    box(robotics, [.85, .26, .85], [3.2 + index * 1.2, .2, 3.5], porcelain)
    box(robotics, [.62, .65, .62], [3.2 + index * 1.2, .65, 3.5], blue)
  }
  label(robotics, 'ORCHESTRATION', 2.6, .35, [5, .3, 4.13], '#26353d')

  const monitoring = stations[3]
  const console = new THREE.Group()
  console.position.set(-5.55, 0, -2)
  console.rotation.y = .12
  monitoring.add(console)
  box(console, [2.65, .22, 1.02], [0, .15, 0], dark, .14)
  box(console, [2.45, 3.65, .49], [0, 1.95, 0], orange, .3)
  box(console, [2.15, 3.26, .16], [0, 1.97, .26], porcelain, .23)
  label(console, 'OBSERVABILITY', 1.9, .28, [0, 3.26, .352], '#e7eef1', '#27444f')
  box(console, [1.82, 1.28, .1], [0, 1.38, .4], glass, .16)
  for (let index = 0; index < 5; index++) box(console, [.2, .22 + index * .14, .085], [-.65 + index * .32, 1.0 + index * .07, .49], index % 2 ? yellow : orange, .025)
  tube(console, [[-.71, 1.69, .5], [-.35, 1.56, .5], [0, 1.75, .5], [.35, 1.83, .5], [.7, 1.88, .5]], orange, .035)
  const dial = mesh(console, new THREE.TorusGeometry(.38, .07, 14, 60), orange, [0, 2.55, .44])
  const needle = box(console, [.045, .3, .025], [0, 2.65, .47], orange, .012)
  const dialCenter = new THREE.Group()
  dialCenter.position.copy(dial.position)
  console.add(dialCenter)
  dialCenter.attach(needle)
  for (let index = 0; index < 10; index++) {
    const angle = index / 10 * Math.PI * 2
    box(console, [.035, .055, .02], [Math.sin(angle) * .5, 2.55 + Math.cos(angle) * .5, .41], steel, .005).rotation.z = -angle
  }
  for (const offset of [-.9, .9]) for (const height of [.55, 3.39]) bolt(console, [offset, height, .36])
  label(console, 'METRICS / LOGS / TRACES', 1.72, .17, [0, .57, .353], '#e7eef1', '#49606a')
  const tank = new THREE.Group()
  tank.position.set(-.5, 0, 2.25)
  monitoring.add(tank)
  cylinder(tank, .86, .25, [0, .17, 0], orange)
  cylinder(tank, .72, 1.56, [0, 1.03, 0], porcelain)
  cylinder(tank, .72, .25, [0, 1.89, 0], porcelain, .54)
  cylinder(tank, .54, .12, [0, 2.07, 0], steel)
  const port = cylinder(tank, .37, .13, [0, 1.15, .72], orange)
  port.rotation.x = Math.PI / 2
  const face = cylinder(tank, .29, .025, [0, 1.15, .8], white)
  face.rotation.x = Math.PI / 2
  label(tank, 'P', .31, .32, [0, 1.15, .822], '#ffffff', '#cf5420')
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
  label(tank, 'COLLECTOR', 1.22, .24, [0, .14, .871], '#f27916', '#ffffff')
  const cablePaths = [
    tube(root, [[-.9, .5, 2.96], [-1.2, .16, 3.4], [-1.2, .16, 4.55], [1.7, .16, 4.55], [2.2, .16, 3.5], [3.2, .2, 3.5]], white, .07),
    tube(root, [[-.1, .5, 2.96], [.3, .16, 3.4], [1.6, .16, 3.4], [2, .16, .1], [4.6, .18, .1]], white, .07),
    tube(root, [[-5.55, .5, -1.6], [-4.65, .18, -.5], [-2.25, .18, -.5], [-1.7, .18, 1.9], [-1.2, .65, 2.25]], white, .075),
  ]
  const packets = cablePaths.map(() => mesh(root, new THREE.SphereGeometry(.115, 12, 12), mint, [0, 0, 0]))
  const ground = mesh(root, new THREE.PlaneGeometry(200, 200), material('#344950', .28, .42), [0, -.08, 0])
  ground.rotation.x = -Math.PI / 2
  ground.castShadow = false
  const grid = new THREE.GridHelper(70, 70, '#57737b', '#415a63')
  grid.position.y = -.07
  root.add(grid)
  stations.forEach((station, index) => station.traverse(object => { object.userData.stage = index }))

  return {
    root, stations, anchors,
    update(time: number, selected: number) {
      rings.forEach((ring, index) => { ring.visible = selected === index })
      slats.forEach((slat, index) => { slat.position.x = -3.2 + (index * .235 + time * .7) % 7.05 })
      parcels.forEach((parcel, index) => parcel.position.set(-3.05 + (time * .7 + index * 1.7) % 6.8, 1.22, -1.8))
      shoulder.rotation.z = -.45 + Math.sin(time * .7) * .28
      elbow.rotation.z = 1.25 + Math.sin(time * .7 + 1.2) * .35
      wrist.rotation.z = .55 + Math.sin(time * .7 + 2) * .23
      robot.rotation.y = Math.sin(time * .35) * .35 - .25
      flame.position.y = 2.46 + Math.sin(time * 1.4) * .06
      flame.rotation.y = Math.sin(time * .6) * .16
      dialCenter.rotation.z = -.5 + Math.sin(time) * .6
      packets.forEach((packet, index) => packet.position.copy(cablePaths[index].getPoint((time * .13 + index * .3) % 1)))
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