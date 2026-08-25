import { test, expect } from '@playwright/test'

async function mockSession(page, role = 'customer') {
  await page.addInitScript(({ role }) => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('user', JSON.stringify({ id: 1, role }))
  }, { role })
  await page.route('**/api/v1/users/me', async (route) => {
    await route.fulfill({ json: { id: 1, role, display_name: 'E2E Demo' } })
  })
}

test('customer can enter the booking discovery flow', async ({ page }) => {
  await mockSession(page, 'customer')
  await page.route('**/api/v1/photographers**', async (route) => {
    await route.fulfill({ json: [] })
  })

  await page.goto('/discover')
  await expect(page.locator('.discover')).toBeVisible()
  await expect(page.locator('.empty-state')).toContainText('暂无摄影师')
})

test('photographer can enter the project workspace', async ({ page }) => {
  await mockSession(page, 'photographer')
  await page.route('**/api/v1/recommendations/projects**', async (route) => {
    await route.fulfill({ json: { items: [], recommendation_id: 'e2e', algorithm_version: 'test' } })
  })
  await page.route('**/api/v1/projects/**', async (route) => {
    await route.fulfill({ json: [] })
  })

  await page.goto('/projects')
  await expect(page.locator('.page-container')).toBeVisible()
})

test('customer can open the mock AI assistant', async ({ page }) => {
  await mockSession(page, 'customer')
  await page.route('**/api/v1/ai/conversations**', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ json: [] })
      return
    }
    await route.fulfill({ json: { id: 1, title: 'E2E AI' } })
  })

  await page.goto('/ai-assistant')
  await expect(page.locator('.ai-page')).toBeVisible()
  await expect(page.locator('.chat-panel')).toBeVisible()
})
