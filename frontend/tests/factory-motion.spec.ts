import { test, expect } from '@playwright/test'
import { Vector3 } from 'three'
import { factoryMotion, cycleDuration, solveArm, robotBase, upperArmLength, forearmLength, toolOffset, handoff, destination } from '../src/factoryMotion'

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
  expect(factoryMotion(8).owner).toBe('belt')
  expect(factoryMotion(12).owner).toBe('gripper')
  expect(factoryMotion(17).owner).toBe('pallet')
  expect(factoryMotion(26).owner).toBe('forklift')
  expect(factoryMotion(32).owner).toBe('destination')
  expect(factoryMotion(17).packagePosition.distanceTo(handoff)).toBeLessThan(.0001)
  expect(factoryMotion(32).packagePosition.distanceTo(destination)).toBeLessThan(.0001)
  for (const boundary of [7, 9, 11, 14, 16, 18, 20, 23, 25, 29, 31, 33, 34]) {
    expect(factoryMotion(boundary - .001).packagePosition.distanceTo(factoryMotion(boundary).packagePosition)).toBeLessThan(.005)
  }
  for (let time = 0; time < cycleDuration; time += .1) {
    const state = factoryMotion(time)
    expect(state.cycle).toBe(0)
    expect(state.beltRunning).toBe(time < 7)
    const angles = solveArm(state.armTarget)
    const local = new Vector3(-Math.sin(angles.shoulder) * upperArmLength - Math.sin(angles.shoulder + angles.elbow) * forearmLength, Math.cos(angles.shoulder) * upperArmLength + Math.cos(angles.shoulder + angles.elbow) * forearmLength - toolOffset, 0)
    const contact = local.applyAxisAngle(new Vector3(0, 1, 0), angles.yaw).add(robotBase)
    expect(contact.distanceTo(state.armTarget)).toBeLessThan(.001)
  }
  expect(factoryMotion(cycleDuration).cycle).toBe(1)
  expect(factoryMotion(cycleDuration).owner).toBe('belt')
})

test('rendered package stays attached to the real gripper and forklift sockets', async ({ page }) => {
  await page.goto('/app/')
  const results = await page.evaluate(async () => {
    const modulePath = '/app/src/factory.ts'
    const { createFactory } = await import(modulePath)
    const factory = createFactory()
    const errors: number[] = []
    const owners: string[] = []
    for (const time of [0, 8, 9, 10, 12, 15, 16, 18, 22, 24, 27, 30, 31, 35]) {
      const state = factory.update(time, 2)
      const position = factory.parcel.position.clone()
      factory.parcel.getWorldPosition(position)
      errors.push(position.distanceTo(state.packagePosition))
      owners.push(factory.parcel.parent.name)
    }
    const logos: string[] = []
    factory.root.traverse((object: { name: string }) => { if (object.name.startsWith('logo-')) logos.push(object.name) })
    const count = factory.root.getObjectsByProperty('name', 'active-package').length
    factory.dispose()
    return { errors, owners, logos, count }
  })
  expect(Math.max(...results.errors)).toBeLessThan(.001)
  expect(results.owners).toContain('package-grip')
  expect(results.owners).toContain('forklift-load')
  expect(results.count).toBe(1)
  for (const slug of ['kubernetes', 'terraform', 'ansible', 'grafana', 'prometheus', 'docker', 'gitlab']) expect(results.logos).toContain(`logo-${slug}`)
})

for (const width of [1440, 390]) {
  test(`handoff screenshots and cycle inspection at ${width}px`, async ({ page }, testInfo) => {
    test.setTimeout(90_000)
    await page.setViewportSize({ width, height: 1000 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/app/')
    const scrub = async (time: string) => {
      await page.getByLabel('Factory cycle position').fill(time)
      await expect(page.getByLabel('Factory cycle position')).toHaveValue(time)
    }
    await scrub('12')
    await expect(page.locator('.cycle-timeline output')).toHaveText('Transferring')
    await page.getByRole('tab', { name: '03 Evaluation' }).click()
    await page.getByRole('button', { name: 'Focus selected station' }).click()
    await page.screenshot({ path: testInfo.outputPath(`arm-${width}.png`), fullPage: true })
    await page.getByRole('button', { name: 'Reset view' }).click()
    await scrub('27')
    await expect(page.locator('.cycle-timeline output')).toHaveText('Delivering')
    await page.screenshot({ path: testInfo.outputPath(`factory-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}