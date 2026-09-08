import { MathUtils, Vector3 } from 'three'

export const cycleDuration = 28
export const pickup = new Vector3(1.35, 1.22, -4)
export const handoff = new Vector3(2.85, 1.22, -4)
export const destination = new Vector3(6.72, .26, -1.45)
export const platformDrop = new Vector3(8.5, .03, .5)
export const orchestrationSlots = [
  new Vector3(6.4, .145, -3.4), new Vector3(8.5, .145, -3.4),
  new Vector3(8.5, .145, -1.45), new Vector3(6.4, .145, .5),
  new Vector3(6.4, .145, -1.45),
]
export const robotBase = new Vector3(3.7, 1.57, -1.65)
export const upperArmLength = 2
export const forearmLength = 1.8
export const toolOffset = 1.28

const blend = (start: Vector3, end: Vector3, progress: number) => start.clone().lerp(end, MathUtils.smoothstep(progress, 0, 1))
const raisedHandoff = handoff.clone().add(new Vector3(0, 1.1, 0))
const raisedDestination = destination.clone().add(new Vector3(0, 1.4, 0))
const dock = new Vector3(12, 0, platformDrop.z)
const arrival = new Vector3(platformDrop.x + 1.7, 0, platformDrop.z)
const forkliftRoute = (progress: number) => blend(dock, arrival, progress)

export function factoryMotion(time: number) {
  const seconds = Math.max(0, time) % cycleDuration
  let phase = 'Conveying'
  let owner: 'belt' | 'gripper' | 'docker' | 'destination' = 'belt'
  let armTarget = raisedHandoff.clone()
  let packagePosition = blend(new Vector3(-5.05, 1.22, -4), pickup, seconds / 7)
  let forkliftPosition: Vector3
  const forkliftYaw = Math.PI / 2
  let forkHeight = .72
  let closed = false

  if (seconds >= 7 && seconds < 9) {
    phase = 'Docker delivery'
    packagePosition = blend(pickup, handoff, (seconds - 7) / 2)
  } else if (seconds >= 9 && seconds < 12) {
    owner = 'docker'; phase = 'Docker staging'
    packagePosition = handoff.clone()
    armTarget = blend(raisedHandoff, handoff, (seconds - 10) / 2)
  } else if (seconds >= 12 && seconds < 14) {
    owner = 'gripper'; phase = 'Docker pickup'; closed = true
    armTarget = blend(handoff, raisedHandoff, (seconds - 12) / 2)
  } else if (seconds >= 14 && seconds < 18) {
    owner = 'gripper'; phase = 'Orchestrating'; closed = true
    armTarget = blend(raisedHandoff, raisedDestination, (seconds - 14) / 4)
  } else if (seconds >= 18 && seconds < 20) {
    owner = 'gripper'; phase = 'Deploying'; closed = true
    armTarget = blend(raisedDestination, destination, (seconds - 18) / 2)
  } else if (seconds >= 20) {
    owner = 'destination'; phase = 'Monitoring'
    packagePosition = destination.clone()
    armTarget = seconds < 22 ? blend(destination, raisedDestination, (seconds - 20) / 2) : blend(raisedDestination, raisedHandoff, (seconds - 22) / 4)
  }
  if (seconds < 8) forkliftPosition = forkliftRoute(seconds / 8)
  else if (seconds < 10) {
    forkliftPosition = arrival.clone()
    forkHeight = MathUtils.lerp(.72, .03, MathUtils.smoothstep((seconds - 8) / 2, 0, 1))
  } else {
    forkliftPosition = forkliftRoute(1 - (seconds - 10) / 8)
    forkHeight = seconds < 18 ? .03 : MathUtils.lerp(.03, .72, MathUtils.smoothstep((seconds - 18) / 3, 0, 1))
  }
  if (owner === 'gripper') packagePosition = armTarget.clone()
  const platformOnForklift = seconds < 10
  const platformPosition = platformOnForklift ? new Vector3(0, forkHeight, -1.7).applyAxisAngle(new Vector3(0, 1, 0), forkliftYaw).add(forkliftPosition) : platformDrop.clone()
  return { seconds, phase, owner, armTarget, packagePosition, forkliftPosition, forkliftYaw, forkHeight, platformPosition, platformOnForklift, closed, beltRunning: seconds < 9, cycle: Math.floor(Math.max(0, time) / cycleDuration) }
}

export function solveArm(packageBottom: Vector3) {
  const target = packageBottom.clone().add(new Vector3(0, toolOffset, 0)).sub(robotBase)
  const radial = Math.hypot(target.x, target.z)
  const cosine = MathUtils.clamp((radial * radial + target.y * target.y - upperArmLength ** 2 - forearmLength ** 2) / (2 * upperArmLength * forearmLength), -1, 1)
  const bend = Math.acos(cosine)
  const shoulder = Math.atan2(radial, target.y) - Math.atan2(forearmLength * Math.sin(bend), upperArmLength + forearmLength * Math.cos(bend))
  return { yaw: -Math.atan2(target.z, target.x), shoulder: -shoulder, elbow: -bend, wrist: Math.PI + shoulder + bend }
}