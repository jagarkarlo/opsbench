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
    })).toBeGreaterThan(1000)
    const before = await canvas.evaluate(element => element.toDataURL())
    await expect.poll(() => canvas.evaluate(element => element.toDataURL())).not.toBe(before)
    await page.getByRole('tab', { name: '03 Evaluation' }).click()
    await expect(page.locator('.inspector')).toContainText('03 / EVALUATION')
    await page.keyboard.press('ArrowRight')
    await expect(page.locator('.inspector')).toContainText('04 / RESULT')
    const nodePoint = await canvas.evaluate(element => {
      const gl = element.getContext('webgl2')!
      const pixels = new Uint8Array(element.width * element.height * 4)
      gl.readPixels(0, 0, element.width, element.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels)
      let totalX = 0, totalY = 0, count = 0
      for (let index = 0; index < pixels.length; index += 4) {
        if (pixels[index + 1] > pixels[index] * 1.3 && pixels[index + 1] > pixels[index + 2] * 1.08 && pixels[index + 1] > 140 && pixels[index + 3] > 0) {
          totalX += (index / 4) % element.width
          totalY += Math.floor(index / 4 / element.width)
          count++
        }
      }
      if (!count) throw Error('Scenario node not visible')
      return { x: totalX / count / element.width * element.clientWidth, y: (1 - totalY / count / element.height) * element.clientHeight }
    })
    await canvas.click({ position: nodePoint })
    await expect(page.locator('.inspector')).toContainText('01 / SCENARIO')
    await page.getByRole('button', { name: 'Zoom in', exact: true }).click()
    await page.getByRole('button', { name: 'Reset view' }).click()
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