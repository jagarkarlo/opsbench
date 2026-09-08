import { MathUtils, Vector3 } from 'three'

export const cycleDuration = 36
export const pickup = new Vector3(1.35, 1.22, -4)
export const handoff = new Vector3(4.3, .55, .8)
export const destination = new Vector3(-2.8, .26, 5.1)
export const robotBase = new Vector3(3.3, 1.57, -2.3)
export const upperArmLength = 2
export const forearmLength = 1.8
export const toolOffset = 1.28

const blend = (start: Vector3, end: Vector3, progress: number) => start.clone().lerp(end, MathUtils.smoothstep(progress, 0, 1))
const raisedPickup = pickup.clone().add(new Vector3(0, 1.1, 0))
const raisedHandoff = handoff.clone().add(new Vector3(0, 1.1, 0))
const dock = new Vector3(4.3, 0, 2.05)
const turn = new Vector3(4.3, 0, 5.1)
const arrival = new Vector3(-1.55, 0, 5.1)

export function factoryMotion(time: number) {
  const seconds = Math.max(0, time) % cycleDuration
  let phase = 'Conveying'
  let owner: 'belt' | 'gripper' | 'pallet' | 'forklift' | 'destination' = 'belt'
  let armTarget = raisedPickup.clone()
  let packagePosition = blend(new Vector3(-5.05, 1.22, -4), pickup, seconds / 7)
  let forkliftPosition = dock.clone()
  let forkliftYaw = 0
  let forkHeight = .32
  let closed = false

  if (seconds >= 7 && seconds < 9) {
    phase = 'Gripping'
    armTarget = blend(raisedPickup, pickup, (seconds - 7) / 2)
  } else if (seconds >= 9 && seconds < 11) {
    phase = 'Lifting'; owner = 'gripper'; closed = true
    armTarget = blend(pickup, raisedPickup, (seconds - 9) / 2)
  } else if (seconds >= 11 && seconds < 14) {
    phase = 'Transferring'; owner = 'gripper'; closed = true
    armTarget = blend(raisedPickup, raisedHandoff, (seconds - 11) / 3)
  } else if (seconds >= 14 && seconds < 16) {
    phase = 'Placing'; owner = 'gripper'; closed = true
    armTarget = blend(raisedHandoff, handoff, (seconds - 14) / 2)
  } else if (seconds >= 16) {
    owner = 'pallet'; phase = 'Releasing'
    packagePosition = handoff.clone()
    armTarget = seconds < 18 ? blend(handoff, raisedHandoff, (seconds - 16) / 2) : blend(raisedHandoff, raisedPickup, (seconds - 18) / 3)
    if (seconds >= 18 && seconds < 20) {
      phase = 'Forklift loading'; owner = 'forklift'
      forkHeight = MathUtils.lerp(.32, .72, MathUtils.smoothstep((seconds - 18) / 2, 0, 1))
    } else if (seconds >= 20 && seconds < 23) {
      phase = 'Reversing from dock'; owner = 'forklift'; forkHeight = .72
      forkliftPosition = blend(dock, turn, (seconds - 20) / 3)
    } else if (seconds >= 23 && seconds < 25) {
      phase = 'Turning to deployment'; owner = 'forklift'; forkHeight = .72
      forkliftPosition = turn.clone()
      forkliftYaw = MathUtils.lerp(0, Math.PI / 2, MathUtils.smoothstep((seconds - 23) / 2, 0, 1))
    } else if (seconds >= 25 && seconds < 29) {
      phase = 'Delivering'; owner = 'forklift'; forkHeight = .72
      forkliftPosition = blend(turn, arrival, (seconds - 25) / 4)
      forkliftYaw = Math.PI / 2
    } else if (seconds >= 29 && seconds < 31) {
      phase = 'Unloading'; owner = 'forklift'; forkliftPosition = arrival.clone(); forkliftYaw = Math.PI / 2
      forkHeight = MathUtils.lerp(.72, .03, MathUtils.smoothstep((seconds - 29) / 2, 0, 1))
    } else if (seconds >= 31) {
      phase = 'Returning'; owner = 'destination'; packagePosition = destination.clone()
      if (seconds < 33) { forkliftPosition = blend(arrival, turn, (seconds - 31) / 2); forkliftYaw = Math.PI / 2 }
      else if (seconds < 34) { forkliftPosition = turn.clone(); forkliftYaw = MathUtils.lerp(Math.PI / 2, 0, MathUtils.smoothstep(seconds - 33, 0, 1)) }
      else forkliftPosition = blend(turn, dock, (seconds - 34) / 2)
      forkHeight = .03
    }
  }
  if (owner === 'gripper') packagePosition = armTarget.clone()
  if (owner === 'forklift') packagePosition = new Vector3(0, forkHeight + .23, -1.25).applyAxisAngle(new Vector3(0, 1, 0), forkliftYaw).add(forkliftPosition)
  return { seconds, phase, owner, armTarget, packagePosition, forkliftPosition, forkliftYaw, forkHeight, closed, beltRunning: seconds < 7, cycle: Math.floor(Math.max(0, time) / cycleDuration) }
}

export function solveArm(packageBottom: Vector3) {
  const target = packageBottom.clone().add(new Vector3(0, toolOffset, 0)).sub(robotBase)
  const radial = Math.hypot(target.x, target.z)
  const cosine = MathUtils.clamp((radial * radial + target.y * target.y - upperArmLength ** 2 - forearmLength ** 2) / (2 * upperArmLength * forearmLength), -1, 1)
  const bend = Math.acos(cosine)
  const shoulder = Math.atan2(radial, target.y) - Math.atan2(forearmLength * Math.sin(bend), upperArmLength + forearmLength * Math.cos(bend))
  return { yaw: -Math.atan2(target.z, target.x), shoulder: -shoulder, elbow: -bend, wrist: Math.PI + shoulder + bend }
}