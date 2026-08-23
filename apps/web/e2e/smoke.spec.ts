import { expect, test } from '@playwright/test'

test('loads the MeetingHQ authentication shell', async ({ page }) => {
  await page.goto('/login')

  await expect(page).toHaveTitle('MeetingHQ')
  await expect(
    page.getByRole('heading', { name: 'Welcome back' }),
  ).toBeVisible()
  await expect(page.getByLabel('Work email')).toBeVisible()
  await expect(page.getByLabel('Password')).toBeVisible()
})
