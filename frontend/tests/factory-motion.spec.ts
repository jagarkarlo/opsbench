import { test, expect } from '@playwright/test'
import { Vector3 } from 'three'
import { factoryMotion, cycleDuration, solveArm, robotBase, upperArmLength, forearmLength, toolOffset, handoff, destination, platformDrop, orchestrationSlots } from '../src/factoryMotion'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/**', route => {
    const endpoint = new URL(route.request().url()).pathname
    const data = endpoint.endsWith('/health') ? { status: 'ok', version: 'test' }
      : endpoint.endsWith('/scenarios') ? { scenarios: [] }
      : endpoint.endsWith('/runs') ? { runs: [], count: 0 }
      : endpoint.endsWith('/portfolio') ? { leaderboard: [] } : { operations: [] }
    return route.fulfill({ json: data })
  })
})

test('single package has continuous ownership through the full delivery cycle', () => {
  const dockHalfWidth = .825
  const dockHalfDepth = .775
  const baseRadius = 1.13
  const dockDistance = Math.hypot(Math.max(Math.abs(robotBase.x - handoff.x) - dockHalfWidth, 0), Math.max(Math.abs(robotBase.z - handoff.z) - dockHalfDepth, 0))
  expect(dockDistance - baseRadius).toBeGreaterThan(.4)
  expect(factoryMotion(8).owner).toBe('belt')
  expect(factoryMotion(12).owner).toBe('gripper')
  expect(factoryMotion(10).owner).toBe('docker')
  expect(factoryMotion(19).owner).toBe('gripper')
  expect(factoryMotion(24).owner).toBe('destination')
  expect(factoryMotion(10).packagePosition.distanceTo(handoff)).toBeLessThan(.0001)
  expect(factoryMotion(24).packagePosition.distanceTo(destination)).toBeLessThan(.0001)
  for (const boundary of [7, 9, 10, 12, 14, 18, 20, 22, 26]) {
    expect(factoryMotion(boundary - .001).packagePosition.distanceTo(factoryMotion(boundary).packagePosition)).toBeLessThan(.005)
  }
  for (let time = 0; time < cycleDuration; time += .1) {
    const state = factoryMotion(time)
    expect(state.cycle).toBe(0)
    expect(state.beltRunning).toBe(time < 9)
    expect(state.platformOnForklift).toBe(time < 10)
    if (time < 9) {
      expect(state.owner).toBe('belt')
      expect(state.packagePosition.y).toBe(handoff.y)
      expect(state.packagePosition.z).toBe(handoff.z)
    }
    if (time >= 10) expect(state.platformPosition.distanceTo(platformDrop)).toBeLessThan(.0001)
    expect(state.platformPosition.distanceTo(destination)).toBeGreaterThan(2.6)
    const next = factoryMotion(time + .001)
    const travel = next.forkliftPosition.clone().sub(state.forkliftPosition)
    const forward = new Vector3(0, 0, -1).applyAxisAngle(new Vector3(0, 1, 0), state.forkliftYaw)
    expect(travel.clone().cross(forward).length()).toBeLessThan(.000001)
    if (time < 8) expect(travel.dot(forward)).toBeGreaterThanOrEqual(0)
    if (time >= 10 && time < 18) expect(travel.dot(forward)).toBeLessThanOrEqual(0)
    expect(state.forkliftPosition.x).toBeGreaterThanOrEqual(10)
    expect(state.forkliftPosition.z).toBeCloseTo(.5)
    for (const slot of orchestrationSlots) expect(Math.hypot(state.forkliftPosition.x - slot.x, state.forkliftPosition.z - slot.z)).toBeGreaterThan(2.3)
    expect(state.platformPosition.distanceTo(next.platformPosition)).toBeLessThan(.005)
    const angles = solveArm(state.armTarget)
    const local = new Vector3(-Math.sin(angles.shoulder) * upperArmLength - Math.sin(angles.shoulder + angles.elbow) * forearmLength, Math.cos(angles.shoulder) * upperArmLength + Math.cos(angles.shoulder + angles.elbow) * forearmLength - toolOffset, 0)
    const contact = local.applyAxisAngle(new Vector3(0, 1, 0), angles.yaw).add(robotBase)
    expect(contact.distanceTo(state.armTarget)).toBeLessThan(.001)
  }
  expect(factoryMotion(cycleDuration).cycle).toBe(1)
  expect(factoryMotion(cycleDuration).owner).toBe('belt')
})

test('rendered package stays attached to the gripper and only empty platforms ride the forklift', async ({ page }) => {
  await page.goto('/app/')
  const results = await page.evaluate(async () => {
    const modulePath = '/app/src/factory.ts'
    const { createFactory } = await import(modulePath)
    const factory = createFactory()
    const errors: number[] = []
    const owners: string[] = []
    const dockerPositions: string[] = []
    const receivingPlatform = factory.root.getObjectByName('orchestration-platform-5')!
    const receiverPositions: string[] = []
    let receiverError = 0
    for (const time of [0, 7, 8, 9, 9.999, 10, 12, 14, 16, 18, 19, 20, 24, 27]) {
      const state = factory.update(time, 2)
      const position = factory.parcel.position.clone()
      factory.parcel.getWorldPosition(position)
      errors.push(position.distanceTo(state.packagePosition))
      factory.pallet.getWorldPosition(position)
      errors.push(position.distanceTo(state.platformPosition))
      owners.push(factory.parcel.parent.name)
      dockerPositions.push(factory.docker.matrixWorld.elements.join(','))
      receiverPositions.push(receivingPlatform.matrixWorld.elements.join(','))
      if (state.owner === 'destination') {
        receivingPlatform.getWorldPosition(position)
        position.y += .115
        position.x += .32
        receiverError = Math.max(receiverError, position.distanceTo(state.packagePosition))
      }
    }
    const logos: string[] = []
    let orchestrationPlatforms = 0
    factory.root.traverse((object: { name: string }) => {
      if (object.name.startsWith('logo-')) logos.push(object.name)
      if (object.name.startsWith('orchestration-platform-')) orchestrationPlatforms++
    })
    const count = factory.root.getObjectsByProperty('name', 'active-package').length
    const deployedContainers = factory.root.getObjectsByProperty('name', 'deployed-container').length
    factory.dispose()
    return { errors, owners, logos, count, dockerPositions, orchestrationPlatforms, deployedContainers, receiverPositions, receiverError, receiverContainers: receivingPlatform.getObjectsByProperty('name', 'deployed-container').length }
  })
  expect(Math.max(...results.errors)).toBeLessThan(.001)
  expect(results.owners).toContain('package-grip')
  expect(results.owners).not.toContain('forklift-load')
  expect(results.count).toBe(1)
  expect(results.orchestrationPlatforms).toBe(5)
  expect(results.deployedContainers).toBe(9)
  expect(results.receiverContainers).toBe(1)
  expect(results.receiverError).toBeLessThan(.001)
  expect(new Set(results.receiverPositions).size).toBe(1)
  expect(new Set(results.dockerPositions).size).toBe(1)
  for (const slug of ['kubernetes', 'terraform', 'ansible', 'grafana', 'prometheus', 'docker', 'git', 'jira']) expect(results.logos).toContain(`logo-${slug}`)
})

test('Terraform clears all illuminated connections and source stations stay separate', async ({ page }) => {
  await page.goto('/app/')
  const result = await page.evaluate(async () => {
    const modulePath = '/app/src/factory.ts'
    const { createFactory } = await import(modulePath)
    const factory = createFactory()
    factory.update(0, 2)
    const points: { x: number; y: number; z: number }[] = []
    const connections: string[] = []
    factory.root.traverse((object: { name: string; geometry?: { attributes: { position: { count: number; getX: (index: number) => number; getY: (index: number) => number; getZ: (index: number) => number } } } }) => {
      if (!object.name.startsWith('connection-') || !object.geometry) return
      connections.push(object.name)
      const vertices = object.geometry.attributes.position
      for (let index = 0; index < vertices.count; index++) points.push({ x: vertices.getX(index), y: vertices.getY(index), z: vertices.getZ(index) })
    })
    let collisions = 0
    for (let time = 0; time < 28; time += .25) {
      factory.update(time, 2)
      for (const point of points) {
        const local = factory.forklift.worldToLocal(factory.forklift.position.clone().set(point.x, point.y, point.z))
        if (Math.abs(local.x) < .85 && local.z > -2.25 && local.z < .95) collisions++
      }
    }
    const sources = ['jira', 'code', 'git'].map(name => {
      const station = factory.root.getObjectByName(`source-${name}`)!
      return station.getWorldPosition(station.position.clone()).x
    })
    const buildEdge = factory.stations[1].position.x - 3.05 - .425
    factory.dispose()
    return { collisions, connections, sources, buildGap: buildEdge - sources[2] - .775 }
  })
  expect(result.collisions).toBe(0)
  expect(result.connections).toContain('connection-ansible-orchestration')
  expect(result.connections).toContain('connection-orchestration-prometheus')
  expect(result.connections.filter(name => name.includes('grafana'))).toEqual(['connection-prometheus-grafana'])
  expect(result.sources[1] - result.sources[0]).toBeCloseTo(2.8)
  expect(result.sources[2] - result.sources[1]).toBeCloseTo(2.8)
  expect(result.buildGap).toBeGreaterThan(1.5)
})

for (const width of [1440, 390]) {
  test(`handoff screenshots and cycle inspection at ${width}px`, async ({ page }, testInfo) => {
    test.setTimeout(90_000)
    await page.setViewportSize({ width, height: 1000 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/app/')
    await expect(page.getByLabel('Factory cycle position')).toHaveCount(0)
    await page.getByRole('button', { name: 'Inspect animation cycle' }).click()
    const scrub = async (time: string) => {
      await page.getByLabel('Factory cycle position').fill(time)
      await expect(page.getByLabel('Factory cycle position')).toHaveValue(time)
    }
    await scrub('10')
    await expect(page.locator('.cycle-timeline output')).toHaveText('Docker staging')
    await page.getByRole('tab', { name: '03 Evaluation' }).click()
    await page.getByRole('button', { name: 'Focus selected station' }).click()
    await page.screenshot({ path: testInfo.outputPath(`arm-${width}.png`), fullPage: true })
    await page.getByRole('button', { name: 'Reset view' }).click()
    await scrub('19')
    await expect(page.locator('.cycle-timeline output')).toHaveText('Deploying')
    await page.screenshot({ path: testInfo.outputPath(`factory-${width}.png`), fullPage: true })
    await page.getByRole('button', { name: 'Top view' }).click()
    await scrub('8')
    await page.screenshot({ path: testInfo.outputPath(`yard-plan-${width}.png`), fullPage: true })
    await page.getByRole('button', { name: 'Reset view' }).click()
    const colors = await page.locator('canvas').evaluate((element: HTMLCanvasElement) => {
      const gl = element.getContext('webgl2')!
      const pixels = new Uint8Array(element.width * element.height * 4)
      gl.readPixels(0, 0, element.width, element.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels)
      const distinct = new Set<number>()
      for (let index = 0; index < pixels.length; index += 16) distinct.add((pixels[index] >> 4) * 256 + (pixels[index + 1] >> 4) * 16 + (pixels[index + 2] >> 4))
      return distinct.size
    })
    expect(colors).toBeGreaterThan(80)
    await page.getByRole('button', { name: 'Inspect animation cycle' }).click()
    await page.getByRole('button', { name: 'Play animation' }).click()
    const canvas = page.locator('canvas')
    const still = await canvas.evaluate((element: HTMLCanvasElement) => element.toDataURL())
    await expect.poll(() => canvas.evaluate((element: HTMLCanvasElement) => element.toDataURL())).not.toBe(still)
    await page.screenshot({ path: testInfo.outputPath(`continuous-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}