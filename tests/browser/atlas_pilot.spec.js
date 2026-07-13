const { test, expect } = require('@playwright/test');
const fs = require('fs');

fs.mkdirSync('test-results/screenshots', { recursive: true });

const password = 'correct horse battery staple';

async function login(page, username, displayName) {
  await page.goto('/login');
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.locator('#current-user')).toContainText(displayName);
}

function runtimeAudit(page) {
  const issues = [];
  page.on('pageerror', error => issues.push(`pageerror: ${error.message}`));
  page.on('console', message => {
    if (message.type() === 'error') issues.push(`console: ${message.text()}`);
  });
  page.on('response', response => {
    if (response.status() >= 500) issues.push(`HTTP ${response.status()}: ${response.url()}`);
  });
  return issues;
}

async function acknowledgeAllGuidelines(page) {
  for (;;) {
    const buttons = page.getByRole('button', { name: '我已阅读并确认' });
    const workspace = page.getByRole('heading', { name: '证据判断工作台' });
    await expect.poll(async () => {
      if (await workspace.count()) return 'ready';
      if (await buttons.count()) return 'acknowledge';
      return 'loading';
    }).not.toBe('loading');
    if (await workspace.count()) return;
    const response = page.waitForResponse(r => r.url().includes('/api/my/onboarding/acknowledge') && r.request().method() === 'POST');
    await buttons.first().click();
    await response;
    await page.goto('/review');
  }
}

test('owner pages render in their content region without runtime failures', async ({ page }, testInfo) => {
  const issues = runtimeAudit(page);
  await login(page, 'owner', 'Owner');
  const pages = [
    ['/owner', 'Active users'],
    ['/owner/system', 'System State'],
    ['/owner/people', 'Create Account'],
    ['/owner/access', 'Users'],
    ['/owner/projects', 'Pilot Setup Wizard'],
    ['/owner/assignments', 'Assignments'],
    ['/owner/adjudication', 'Adjudication Queue'],
    ['/owner/gold', 'Blocking reasons'],
    ['/owner/evaluation', 'Evaluation scope'],
    ['/owner/quality', 'Quality warnings'],
    ['/owner/audit', 'Audit log'],
    ['/owner/exports', 'Exports'],
  ];
  for (const [path, text] of pages) {
    const response = await page.goto(path);
    expect(response.status(), path).toBe(200);
    await expect(page.locator('#owner-page-body')).toContainText(text);
    await expect(page.locator('#owner-page-body .loading')).toHaveCount(0);
    if (['/owner', '/owner/projects', '/owner/access'].includes(path)) {
      const name = path === '/owner' ? 'overview' : path.split('/').pop();
      await page.screenshot({ path: `test-results/screenshots/owner-${name}-${testInfo.project.name}.png` });
    }
  }
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  expect(issues).toEqual([]);
  await page.screenshot({ path: `test-results/screenshots/owner-exports-${testInfo.project.name}.png` });
});

test('graph starts with case overview then exposes a readable local graph and details', async ({ page }, testInfo) => {
  const issues = runtimeAudit(page);
  await login(page, 'owner', 'Owner');
  await page.goto('/graph');
  await expect(page.getByRole('heading', { name: '研究问题概览' })).toBeVisible();
  await expect(page.locator('.graph-case-overview')).toContainText('保持隔离');
  await expect(page.locator('#global-graph-svg')).toBeHidden();
  await page.screenshot({ path: `test-results/screenshots/graph-case-overview-${testInfo.project.name}.png` });

  await page.getByRole('button', { name: '打开局部图' }).first().click();
  await expect(page.locator('#global-graph-svg')).toBeVisible();
  await expect(page.locator('.graph-node')).toHaveCount(2);
  await expect(page.locator('.graph-edge')).toHaveCount(1);
  expect(await page.locator('.graph-node.show-label').count()).toBeLessThanOrEqual(8);
  await page.screenshot({ path: `test-results/screenshots/graph-local-${testInfo.project.name}.png` });
  await page.locator('.graph-node').first().click();
  await expect(page.locator('#graph-detail-side')).toContainText('Canonical name');
  await page.screenshot({ path: `test-results/screenshots/graph-node-detail-${testInfo.project.name}.png` });
  await page.locator('.graph-edge').first().click();
  await expect(page.locator('#graph-detail-side')).toContainText('来源说明');
  await expect(page.locator('#graph-detail-side')).toContainText('打开机制档案与证据');
  await page.screenshot({ path: `test-results/screenshots/graph-edge-detail-${testInfo.project.name}.png` });
  expect(issues).toEqual([]);
});

test('reviewer disagreement reaches adjudication and frozen Pilot Gold', async ({ browser }, testInfo) => {
  test.setTimeout(90000);
  test.skip(testInfo.project.name !== 'chromium-1366', 'Write workflow runs once against the shared temporary database.');

  async function submitReview(username, displayName, label, note) {
    const context = await browser.newContext({ viewport: { width: 1366, height: 768 } });
    const page = await context.newPage();
    const issues = runtimeAudit(page);
    await login(page, username, displayName);
    await page.goto('/review');
    await acknowledgeAllGuidelines(page);
    await expect(page.getByRole('heading', { name: '证据判断工作台' })).toBeVisible();
    await page.locator('.review-layer-card').first().click();
    await expect(page.locator('.review-save-btn')).toBeVisible();
    await page.locator(`#review-quick-labels [data-label="${label}"]`).click();
    for (const field of ['same_normalized_pair', 'same_relation_family', 'same_outcome_definition', 'same_experimental_level', 'context_comparable']) {
      await page.locator(`[data-field="${field}"] select`).selectOption('true');
    }
    await page.locator('[data-field="sign_a"] select').selectOption('positive');
    await page.locator('[data-field="sign_b"] select').selectOption('negative');
    await page.locator('[data-field="true_conflict"] select').selectOption('true');
    await expect(page.locator('[data-field="conflict_type"]')).toBeVisible();
    await page.locator('[data-field="conflict_type"] select').selectOption('directional');
    await page.locator('[data-field="information_sufficient"] select').selectOption('true');
    await page.locator('#ann-notes').fill(note);
    await page.reload();
    await page.locator('.review-layer-card').first().click();
    await expect(page.locator('#ann-notes')).toHaveValue(note);
    await expect(page.locator(`#review-quick-labels [data-label="${label}"]`)).toHaveClass(/active/);
    if (username === 'primary') {
      await page.screenshot({ path: 'test-results/screenshots/reviewer-workspace-1366.png' });
    }
    await page.locator('.review-save-btn').click();
    await expect(page.getByText('Annotation saved')).toBeVisible();
    expect(issues).toEqual([]);
    await context.close();
  }

  await submitReview('primary', 'Primary', 'VALID', 'Primary reviewer evidence note');
  await submitReview('secondary', 'Secondary', 'PARTIAL', 'Secondary reviewer disagreement note');

  const adjudicatorContext = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const adjudicatorPage = await adjudicatorContext.newPage();
  const adjudicatorIssues = runtimeAudit(adjudicatorPage);
  await login(adjudicatorPage, 'adjudicator', 'Adjudicator');
  await adjudicatorPage.goto('/adjudication');
  await adjudicatorPage.locator('.adjudication-queue-item').first().click();
  await expect(adjudicatorPage.locator('.adjudication-compare')).toContainText('Reviewer A');
  await expect(adjudicatorPage.locator('.adjudication-compare')).toContainText('Reviewer B');
  await adjudicatorPage.locator('#adj-label').selectOption('VALID');
  adjudicatorPage.once('dialog', dialog => dialog.accept());
  await adjudicatorPage.locator('#adj-submit').click();
  await expect(adjudicatorPage.locator('#adj-message')).toContainText('Gold remains unfrozen');
  await adjudicatorPage.screenshot({ path: 'test-results/screenshots/adjudication-1366.png' });
  expect(adjudicatorIssues).toEqual([]);
  await adjudicatorContext.close();

  const ownerContext = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const ownerPage = await ownerContext.newPage();
  await login(ownerPage, 'owner', 'Owner');
  await ownerPage.goto('/owner/gold');
  await expect(ownerPage.locator('#owner-page-body')).toContainText('ready');
  ownerPage.once('dialog', dialog => dialog.accept());
  await ownerPage.getByRole('button', { name: 'Freeze next Pilot/Production Gold version' }).click();
  await expect(ownerPage.locator('#gold-message')).toContainText('v1');
  await ownerPage.screenshot({ path: 'test-results/screenshots/gold-frozen-1366.png' });
  await ownerPage.goto('/owner/evaluation');
  await expect(ownerPage.locator('#owner-page-body')).toContainText('configuration_mismatch');
  await expect(ownerPage.locator('#owner-page-body')).toContainText('project_namespace_not_production');
  await expect(ownerPage.getByRole('button', { name: 'Run evaluation' })).toHaveCount(0);
  await ownerPage.screenshot({ path: 'test-results/screenshots/evaluation-pilot-isolation-1366.png' });
  await ownerContext.close();
});

test('malformed graph response produces an actionable error state', async ({ page }, testInfo) => {
  await login(page, 'owner', 'Owner');
  await page.route('**/api/graph/case-overview', route => route.fulfill({ status: 200, contentType: 'text/html', body: '<html>bad response</html>' }));
  await page.goto('/graph');
  await expect(page.locator('#graph-case-overview')).toContainText('Invalid server response');
  await expect(page.locator('#graph-case-overview')).toContainText('/api/graph/case-overview');
  await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible();
  await page.screenshot({ path: `test-results/screenshots/error-state-${testInfo.project.name}.png` });
});

test('login, discover, role gates, and 200 percent zoom remain usable', async ({ browser }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-1366', 'Focused role and zoom audit runs once.');
  const ownerContext = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const ownerPage = await ownerContext.newPage();
  await ownerPage.goto('/login');
  await ownerPage.screenshot({ path: 'test-results/screenshots/login-1366.png' });
  await login(ownerPage, 'owner', 'Owner');
  await ownerPage.goto('/discover');
  await expect(ownerPage.locator('main')).toContainText('机制证据档案');
  await ownerPage.screenshot({ path: 'test-results/screenshots/discover-1366.png' });
  expect((await ownerPage.goto('/console')).status()).toBe(403);
  await ownerPage.goto('/graph');
  await ownerPage.evaluate(() => { document.body.style.zoom = '200%'; });
  await expect(ownerPage.getByRole('heading', { name: '研究问题概览' })).toBeVisible();
  const overflow = await ownerPage.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await ownerPage.screenshot({ path: 'test-results/screenshots/graph-overview-zoom-200.png', fullPage: true });
  await ownerContext.close();

  const reviewerContext = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const reviewerPage = await reviewerContext.newPage();
  await login(reviewerPage, 'primary', 'Primary');
  expect((await reviewerPage.goto('/owner')).status()).toBe(403);
  expect((await reviewerPage.goto('/console')).status()).toBe(403);
  await reviewerContext.close();

  const developerContext = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const developerPage = await developerContext.newPage();
  await login(developerPage, 'adjudicator', 'Adjudicator');
  expect((await developerPage.goto('/console')).status()).toBe(200);
  await expect(developerPage.getByRole('heading', { name: 'Developer Console' })).toBeVisible();
  await expect(developerPage.locator('body')).toContainText('source_file');
  await developerContext.close();
});

test('owner completes access management and Pilot creation in the temporary database', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-1366', 'Write audit runs once against the temporary database.');
  test.setTimeout(60000);
  const issues = runtimeAudit(page);
  await login(page, 'owner', 'Owner');

  await page.goto('/owner/users');
  await page.locator('#ou-username').fill('browser-managed');
  await page.locator('#ou-display').fill('Browser Managed');
  await page.locator('#ou-role').selectOption('reviewer');
  await page.getByRole('button', { name: 'Create temporary-password user' }).click();
  await expect(page.locator('#ou-created')).toContainText('Credential shown once');
  await page.getByRole('button', { name: 'Copy temporary password' }).click();
  await expect(page.getByRole('button', { name: 'Copy temporary password' })).toContainText('已复制');
  await page.reload();
  let row = page.getByRole('row').filter({ hasText: 'browser-managed' });
  await row.getByLabel('Role for browser-managed').selectOption('pharma');
  page.once('dialog', dialog => dialog.accept());
  await row.getByRole('button', { name: 'Change role' }).click();
  await expect(page.getByRole('row').filter({ hasText: 'browser-managed' }).getByLabel('Role for browser-managed')).toHaveValue('pharma');

  row = page.getByRole('row').filter({ hasText: 'browser-managed' });
  page.once('dialog', dialog => dialog.accept());
  await row.getByRole('button', { name: 'Disable' }).click();
  await expect(page.getByRole('row').filter({ hasText: 'browser-managed' })).toContainText('disabled');
  row = page.getByRole('row').filter({ hasText: 'browser-managed' });
  page.once('dialog', dialog => dialog.accept());
  await row.getByRole('button', { name: 'Enable' }).click();
  await expect(page.getByRole('row').filter({ hasText: 'browser-managed' })).toContainText('enabled');
  row = page.getByRole('row').filter({ hasText: 'browser-managed' });
  page.once('dialog', dialog => dialog.accept());
  await row.getByRole('button', { name: 'Revoke sessions' }).click();
  await expect(page.getByText('Sessions revoked')).toBeVisible();

  await page.goto('/owner/invites');
  await page.locator('#oi-label').fill('Browser internal pilot');
  await page.getByRole('button', { name: 'Create invite' }).click();
  await expect(page.locator('#oi-created')).toContainText('Invite shown once');
  await page.getByRole('button', { name: 'Copy invite code' }).click();
  await expect(page.getByRole('button', { name: 'Copy invite code' })).toContainText('已复制');
  await page.reload();
  const inviteRow = page.getByRole('row').filter({ hasText: 'Browser internal pilot' });
  page.once('dialog', dialog => dialog.accept());
  await inviteRow.getByRole('button', { name: 'Disable' }).click();
  await expect(page.getByRole('row').filter({ hasText: 'Browser internal pilot' })).toContainText('disabled');

  await page.goto('/owner/projects');
  await page.locator('#pilot-name').fill('Browser Created Pilot');
  await page.locator('#pilot-primary').selectOption({ label: /primary/ });
  await page.locator('#pilot-secondary').selectOption({ label: /secondary/ });
  await page.locator('#pilot-adjudicator').selectOption({ label: /adjudicator/ });
  await page.locator('#pilot-batch').fill('1');
  await page.getByRole('button', { name: 'Preview assignments' }).click();
  await expect(page.locator('#pilot-preview')).toContainText('Preview');
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Create Pilot from preview' }).click();
  await expect(page.locator('#pilot-preview')).toContainText('Pilot created');
  expect(issues).toEqual([]);
});
