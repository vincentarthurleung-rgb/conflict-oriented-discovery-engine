const { test, expect } = require('@playwright/test');

const ownerUser = process.env.ATLAS_OWNER_USERNAME || 'owner';
const ownerPassword = process.env.ATLAS_OWNER_PASSWORD || 'correct horse battery staple';

async function login(page) {
  await page.goto('/login');
  await page.getByLabel('Username').fill(ownerUser);
  await page.getByLabel('Password').fill(ownerPassword);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.locator('#current-user')).toContainText('Owner');
}

test('owner can inspect system state without placeholder zeroes', async ({ page }) => {
  await login(page);
  await page.goto('/owner/system');
  await expect(page.getByRole('heading', { name: 'System State' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Review items', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Assignments', exact: true })).toBeVisible();
  await expect(page.getByText('Schema 0008_system_a_ingestion_ledger')).toBeVisible();
});

test('pilot setup preview distinguishes cases from review items', async ({ page }) => {
  await login(page);
  await page.goto('/owner/projects');
  await page.getByRole('button', { name: 'Preview assignments' }).click();
  await expect(page.locator('#pilot-preview')).toContainText('Review Item count is not Case count');
  await expect(page.getByText('unique cases')).toBeVisible();
  await expect(page.getByText('unique review items')).toBeVisible();
});
