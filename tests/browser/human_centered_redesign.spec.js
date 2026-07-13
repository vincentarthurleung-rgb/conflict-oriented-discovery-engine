const { test, expect } = require('@playwright/test');
const fs = require('fs');

const out = 'test-results/human-centered-redesign';
const password = 'correct horse battery staple';
fs.mkdirSync(out, { recursive: true });

async function login(page, username = 'owner') {
  await page.goto('/login');
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.locator('#current-user')).toContainText(username === 'owner' ? 'Owner' : username === 'primary' ? 'Primary' : username);
}

async function finishOnboarding(page) {
  for (;;) {
    const confirm = page.getByRole('button', { name: '我已阅读并确认' });
    const workspace = page.getByRole('heading', { name: '证据判断工作台' });
    await expect.poll(async () => {
      if (await workspace.count()) return 'ready';
      if (await confirm.count()) return 'confirm';
      return 'loading';
    }).not.toBe('loading');
    if (await workspace.count()) return;
    await Promise.all([
      page.waitForResponse(r => r.url().includes('/api/my/onboarding/acknowledge') && r.request().method() === 'POST'),
      confirm.first().click(),
    ]);
    await page.goto('/review');
  }
}

function runtimeAudit(page) {
  const issues = [];
  page.on('pageerror', e => issues.push(`pageerror: ${e.message}`));
  page.on('console', m => { if (m.type() === 'error') issues.push(`console: ${m.text()}`); });
  page.on('response', r => { if (r.status() >= 500) issues.push(`HTTP ${r.status()}: ${r.url()}`); });
  return issues;
}

test('researcher completes the Wnt evidence-reading path on real eleven-case data', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-1366', 'The complete evidence walkthrough is captured once at the primary viewport.');
  const issues = runtimeAudit(page);
  await page.goto('/login');
  await page.screenshot({ path: `${out}/01-login.png` });
  await login(page);

  await expect(page.getByRole('heading', { name: '理解文献证据为何一致，又为何不同' })).toBeVisible();
  await expect(page.locator('.case-card')).toHaveCount(11);
  await page.screenshot({ path: `${out}/02-home.png`, fullPage: true });
  await page.locator('#research-cases').scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${out}/03-case-cards.png` });

  const wnt = page.locator('.case-card').filter({ hasText: 'Wnt / β-catenin' });
  await expect(wnt).toContainText('当前未发现正式冲突');
  await wnt.getByRole('link', { name: /查看证据概况/ }).click();
  await expect(page.getByRole('heading', { name: 'Wnt / β-catenin、干性与免疫' })).toBeVisible();
  await expect(page.locator('.answer-panel')).toContainText('正式冲突');
  await page.screenshot({ path: `${out}/04-wnt-case-overview.png`, fullPage: true });

  const dossierHref = await page.locator('.mechanism-unit a[href^="/dossier/"]').first().getAttribute('href');
  await page.goto(dossierHref);
  await expect(page.getByRole('heading', { name: '证据显示了什么' })).toBeVisible();
  await expect(page.locator('#evidence-shows')).toContainText(/PMID|PMCID|全文/);
  const dossierHeader = await page.locator('.dossier-header').boundingBox();
  const sectionJump = await page.locator('.section-jump').boundingBox();
  expect(dossierHeader && sectionJump && dossierHeader.y + dossierHeader.height <= sectionJump.y).toBeTruthy();
  await page.screenshot({ path: `${out}/05-dossier.png`, fullPage: true });
  await page.locator('#reasoning-trace').scrollIntoViewIfNeeded();
  await expect(page.locator('#reasoning-trace')).toContainText(/实验推理证据链|该运行未生成全文推理证据链/);
  await page.screenshot({ path: `${out}/06-reasoning-trace.png` });
  await page.locator('#context-matrix').scrollIntoViewIfNeeded();
  await expect(page.getByRole('button', { name: '简化比较' })).toBeVisible();
  await page.getByRole('button', { name: '完整矩阵' }).click();
  await page.screenshot({ path: `${out}/07-context-matrix.png` });

  await page.goto('/graph');
  await expect(page.getByRole('heading', { name: '研究问题概览' })).toBeVisible();
  await page.screenshot({ path: `${out}/12-global-case-overview.png` });
  await page.locator('.case-overview-card').filter({ hasText: 'wnt_beta_catenin' }).getByRole('button', { name: '打开局部图' }).click();
  await expect(page.locator('.graph-node').first()).toBeVisible();
  await page.screenshot({ path: `${out}/13-single-case-map.png` });
  await page.locator('.graph-node').first().click();
  await expect(page.locator('#graph-detail-side')).not.toContainText('点击节点');
  await page.screenshot({ path: `${out}/14-node-detail.png` });
  expect(issues).toEqual([]);
});

test('reviewer and owner task workspaces expose actions before internals', async ({ browser }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-1366', 'Role walkthrough is captured once.');
  const reviewerContext = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const reviewer = await reviewerContext.newPage();
  await login(reviewer, 'primary');
  await reviewer.goto('/review');
  await finishOnboarding(reviewer);
  await expect(reviewer.getByRole('heading', { name: '证据判断工作台' })).toBeVisible();
  await reviewer.locator('.review-layer-card').first().click();
  await expect(reviewer.locator('.review-save-btn')).toContainText('提交判断并进入下一条');
  // Capture the independently scrolling workbench itself so the task,
  // evidence and action stay together without Chromium stitching artifacts.
  await reviewer.locator('.review-workspace').screenshot({ path: `${out}/08-review-task.png` });
  await reviewerContext.close();

  const ownerContext = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const owner = await ownerContext.newPage();
  await login(owner);
  await owner.goto('/owner');
  await expect(owner.locator('.owner-action-hero')).toBeVisible();
  await owner.screenshot({ path: `${out}/09-owner-dashboard.png`, fullPage: true });
  await owner.goto('/owner/adjudication');
  await expect(owner.locator('#owner-page-body')).toContainText(/Adjudication|仲裁|disagreement/);
  await owner.screenshot({ path: `${out}/10-adjudication.png`, fullPage: true });
  await owner.goto('/owner/evaluation');
  await expect(owner.locator('#owner-page-body')).toContainText(/当前不能运行|可以运行/);
  await owner.screenshot({ path: `${out}/11-evaluation-readiness.png`, fullPage: true });
  await ownerContext.close();
});

test('empty, error, responsive and 200 percent zoom states remain actionable', async ({ page }, testInfo) => {
  await login(page);
  await page.goto('/library');
  await expect(page.locator('.empty').first()).toBeVisible();
  if (testInfo.project.name === 'chromium-1366') await page.screenshot({ path: `${out}/15-empty-state.png`, fullPage: true });

  await page.route('**/api/graph/case-overview*', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: 'temporary_unavailable' }) }));
  await page.goto('/graph');
  await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible();
  if (testInfo.project.name === 'chromium-1366') await page.screenshot({ path: `${out}/16-error-state.png` });

  await page.goto('/discover');
  if (testInfo.project.name === 'chromium-1366') await page.evaluate(() => { document.body.style.zoom = '200%'; });
  await expect(page.getByRole('heading', { name: '理解文献证据为何一致，又为何不同' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
});
