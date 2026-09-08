import { test, expect, type Page } from '@playwright/test'

async function mockApi(page: Page, partial = false) {
  await page.route('**/api/v1/**', route => {
    const endpoint = new URL(route.request().url()).pathname
    if (partial && endpoint.endsWith('/runs')) return route.fulfill({ status: 503, body: 'Unavailable' })
    const data = endpoint.endsWith('/health') ? { status: 'ok', version: 'test' }
      : endpoint.endsWith('/scenarios') ? { scenarios: partial ? [{ scenario_id: 'real-test', title: 'API test scenario', category: 'test' }] : [] }
      : endpoint.endsWith('/runs') ? { runs: [], count: 0 }
      : endpoint.endsWith('/portfolio') ? { leaderboard: [] }
      : { operations: [] }
    return route.fulfill({ json: data })
  })
}

test('empty API results never retain demo rows', async ({ page }) => {
  await mockApi(page)
  await page.goto('/app/')
  await expect(page.getByText('API CONNECTED', { exact: true })).toBeVisible()
  await expect(page.getByText('No scenarios available.')).toBeVisible()
  await page.getByLabel('Demo dataset').check()
  await expect(page.getByRole('heading', { name: 'Kubernetes image pull failure' })).toBeVisible()
  await page.getByLabel('Demo dataset').uncheck()
  await expect(page.getByText('No scenarios available.')).toBeVisible()
  await expect(page.getByText('demo-run-1', { exact: true })).toHaveCount(0)
})

test('one failed endpoint preserves successful sources', async ({ page }) => {
  await mockApi(page, true)
  await page.goto('/app/')
  await expect(page.getByRole('heading', { name: 'API test scenario' })).toBeVisible()
  await expect(page.getByText('1 API sources unavailable')).toBeVisible()
  await expect(page.getByText('Run source unavailable.')).toBeVisible()
})

for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test(`interactive workflow and results at ${viewport.width}px`, async ({ page }, testInfo) => {
    test.setTimeout(60_000)
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.setViewportSize(viewport)
    await mockApi(page)
    await page.goto('/app/')
    await page.getByLabel('Demo dataset').check()
    const canvas = page.locator('canvas')
    await expect(canvas).toBeVisible()
    await expect.poll(() => canvas.evaluate(element => {
      const gl = element.getContext('webgl2')!
      const pixels = new Uint8Array(element.width * element.height * 4)
      gl.readPixels(0, 0, element.width, element.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels)
      let count = 0
      for (let index = 3; index < pixels.length; index += 4) if (pixels[index]) count++
      return count
    }), { timeout: 15_000 }).toBeGreaterThan(1000)
    const before = await canvas.evaluate(element => element.toDataURL())
    await expect.poll(() => canvas.evaluate(element => element.toDataURL())).not.toBe(before)
    await page.getByRole('tab', { name: '03 Evaluation' }).click()
    await expect(page.locator('.inspector')).toContainText('03 / EVALUATION')
    await page.keyboard.press('ArrowRight')
    await expect(page.locator('.inspector')).toContainText('04 / RESULT')
    await page.keyboard.press('1')
    await expect(page.locator('.inspector')).toContainText('01 / SCENARIO')
    await page.getByRole('button', { name: 'Focus selected station' }).click()
    await page.getByRole('tab', { name: '04 Result' }).click()
    const nodePoint = await canvas.evaluate(element => ({ x: element.clientWidth / 2, y: element.clientHeight / 2 }))
    await canvas.click({ position: nodePoint })
    await expect(page.locator('.inspector')).toContainText('01 / SCENARIO')
    await page.getByRole('button', { name: 'Zoom in', exact: true }).click()
    await page.getByRole('button', { name: 'Reset view' }).click()
    await page.getByRole('button', { name: 'Pause animation' }).click()
    await expect(page.getByRole('button', { name: 'Play animation' })).toBeVisible()
    await page.getByLabel('Animation speed').selectOption('2')
    await expect(page.getByLabel('Animation speed')).toHaveValue('2')
    await page.getByRole('button', { name: 'Top view' }).click()
    await expect(page.locator('.scene-view-label')).toContainText('CAMERA / PLAN')
    await page.getByRole('button', { name: 'Pan camera' }).click()
    await expect(page.getByRole('button', { name: 'Pan camera' })).toHaveAttribute('aria-pressed', 'true')
    await canvas.scrollIntoViewIfNeeded()
    const bounds = (await canvas.boundingBox())!
    expect(await page.evaluate(({ x, y }) => document.elementFromPoint(x, y)?.tagName, { x: bounds.x + bounds.width * .5, y: bounds.y + bounds.height * .5 })).toBe('CANVAS')
    const priorPan = await canvas.evaluate(element => element.toDataURL())
    await page.mouse.move(bounds.x + bounds.width * .5, bounds.y + bounds.height * .5)
    await page.mouse.down()
    await page.mouse.move(bounds.x + bounds.width * .5 + 55, bounds.y + bounds.height * .5 + 15, { steps: 10 })
    await page.mouse.up()
    await expect.poll(() => canvas.evaluate(async element => {
      await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
      return element.toDataURL()
    }), { timeout: 15_000 }).not.toBe(priorPan)
    await page.getByRole('button', { name: 'Orbit camera' }).click()
    await page.getByRole('button', { name: 'Focus selected station' }).click()
    await expect(page.locator('.scene-view-label')).toContainText('CAMERA / STATION 01')
    await page.getByRole('button', { name: 'Expand scene', exact: true }).click()
    await expect(page.locator('.scene-expanded')).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath(`station-detail-${viewport.width}.png`), fullPage: true })
    await page.getByRole('button', { name: 'Collapse scene' }).click()
    await page.getByRole('button', { name: 'Reset view' }).click()
    await page.getByRole('button', { name: 'Play animation' }).click()
    await page.getByLabel('Search scenarios').fill('drift')
    await expect(page.locator('.scenario')).toHaveCount(1)
    await page.locator('.scenario').click()
    await expect(page.locator('.scene-heading')).toContainText('GitOps drift detection')
    await page.getByLabel('Search scenarios').fill('')
    await expect(page.locator('.inspector')).toContainText('demo-drift')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`workspace-${viewport.width}.png`), fullPage: true })
    await page.getByRole('button', { name: 'Runs', exact: true }).click()
    await page.getByLabel('Compare demo-run-1').check()
    await page.getByLabel('Compare demo-run-2').check()
    await expect(page.getByText('Different scenarios: scores are not directly comparable.')).toBeVisible()
    await page.getByRole('button', { name: 'demo-run-1', exact: true }).click()
    await expect(page.getByRole('dialog')).toContainText('Synthetic demonstration report')
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).toHaveCount(0)
    expect(errors).toEqual([])
  })
}

test('reduced motion starts paused and supports explicit playback', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await mockApi(page)
  await page.goto('/app/')
  await expect(page.getByRole('button', { name: 'Play animation' })).toBeVisible()
  const canvas = page.locator('canvas')
  const settledFrame = await canvas.evaluate(async element => {
    await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
    return element.toDataURL()
  })
  const laterFrame = await canvas.evaluate(async element => {
    for (let frame = 0; frame < 6; frame++) await new Promise(requestAnimationFrame)
    return element.toDataURL()
  })
  expect(laterFrame).toBe(settledFrame)
  await page.getByRole('button', { name: 'Play animation' }).click()
  await expect.poll(() => canvas.evaluate(element => element.toDataURL())).not.toBe(settledFrame)
})