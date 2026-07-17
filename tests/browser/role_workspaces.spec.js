const { test, expect } = require('@playwright/test');

const password = 'correct horse battery staple';

async function login(page, username, landing) {
  await page.goto('/login');
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(new RegExp(`${landing.replace('/', '\\/')}$`));
  await expect(page.locator('#current-user')).not.toBeEmpty();
}

async function getJson(page, path) {
  return page.evaluate(async path => {
    const response = await fetch(path, { credentials: 'same-origin' });
    let body;
    try { body = await response.json(); } catch (_) { body = {}; }
    return { status: response.status, body };
  }, path);
}

async function postJson(page, path, payload = {}) {
  return page.evaluate(async ({ path, payload }) => {
    const session = await fetch('/api/session', { credentials: 'same-origin' }).then(r => r.json());
    const response = await fetch(path, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token },
      body: JSON.stringify(payload),
    });
    let body;
    try { body = await response.json(); } catch (_) { body = {}; }
    return { status: response.status, body };
  }, { path, payload });
}

function navIds(page) {
  return page.locator('nav [data-nav-id]').evaluateAll(nodes => nodes.map(node => node.dataset.navId));
}

test.describe('role workspaces', () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== 'chromium-1366', 'The six-role authorization audit runs once.');
  });

  test('researcher lands in research and direct URLs are server denied', async ({ page }) => {
    await login(page, 'researcher', '/discover');
    await expect(page.getByRole('heading', { name: '理解文献证据为何一致，又为何不同' })).toBeVisible();
    const nav = await navIds(page);
    expect(nav).toContain('domains');
    expect(nav).toContain('cases');
    expect(nav).not.toContain('review');
    expect(nav).not.toContain('owner');
    expect(nav).not.toContain('console');
    for (const path of ['/review', '/owner', '/console']) {
      const response = await page.goto(path);
      expect(response.status(), path).toBe(403);
      await expect(page.getByRole('heading', { name: '你没有访问此页面的权限' })).toBeVisible();
      await expect(page.locator('body')).toContainText('当前角色：researcher');
    }
    expect((await getJson(page, '/api/entities')).status).toBe(403);
  });

  test('reviewer sees only their task and no peer answer in network payload', async ({ page }) => {
    await login(page, 'primary', '/review');
    await expect(page.locator('#workspace h1')).toContainText(/审核/);
    const nav = await navIds(page);
    expect(nav).toContain('review');
    expect(nav).not.toContain('adjudication');
    expect(nav).not.toContain('owner');
    expect(nav).not.toContain('console');
    const list = await getJson(page, '/api/review-items');
    expect(list.status).toBe(200);
    expect([...new Set(list.body.items.map(item => item.review_item_id))]).toContain('browser-item-1');
    expect(JSON.stringify(list.body)).not.toContain('Secondary reviewer disagreement note');
    const own = await getJson(page, '/api/review-item/browser-item-1');
    expect(own.status).toBe(200);
    expect(JSON.stringify(own.body)).not.toContain('Secondary reviewer disagreement note');
    expect((await getJson(page, '/api/review-item/not-assigned-object')).status).toBe(404);
    expect((await getJson(page, '/api/review-export.jsonl')).status).toBe(403);
    expect((await page.goto('/adjudication')).status()).toBe(403);
    expect((await page.goto('/owner')).status()).toBe(403);
    expect((await page.goto('/console')).status()).toBe(403);
  });

  test('empty reviewer gets an explained empty state', async ({ page }) => {
    await login(page, 'empty-reviewer', '/review');
    await expect(page.getByRole('heading', { name: '当前没有分配给你的审核任务' })).toBeVisible();
    await expect(page.getByRole('link', { name: '浏览研究资料' })).toBeVisible();
  });

  test('adjudicator gets only assigned workflow-ready disagreements', async ({ page }) => {
    await login(page, 'adjudicator', '/adjudication');
    await expect(page.getByRole('heading', { name: '我的仲裁' })).toBeVisible();
    const nav = await navIds(page);
    expect(nav).toContain('adjudication');
    expect(nav).not.toContain('review');
    expect(nav).not.toContain('owner');
    expect(nav).not.toContain('console');
    const queue = await getJson(page, '/api/adjudication/queue');
    expect(queue.status).toBe(200);
    for (const item of queue.body.items) expect(item.status).toBe('needs_adjudication');
    const outside = await getJson(page, '/api/adjudication/browser-item-2?project_id=not-assigned');
    expect(outside.status).toBe(404);
    expect(JSON.stringify(outside.body)).not.toMatch(/Primary reviewer evidence note|Secondary reviewer disagreement note/);
    expect((await page.goto('/owner')).status()).toBe(403);
    expect((await page.goto('/console')).status()).toBe(403);
  });

  test('developer gets technical diagnostics without governance or blind data', async ({ page }) => {
    await login(page, 'developer', '/console');
    await expect(page.getByRole('heading', { name: 'Developer Console' })).toBeVisible();
    const nav = await navIds(page);
    expect(nav).toContain('console');
    expect(nav).not.toContain('review');
    expect(nav).not.toContain('admin');
    expect(nav).not.toContain('owner');
    const consolePayload = await getJson(page, '/api/console/overview');
    expect(consolePayload.status).toBe(200);
    expect(consolePayload.body.blind_review_payload_included).toBe(false);
    expect(JSON.stringify(consolePayload.body)).not.toMatch(/annotations|Primary reviewer evidence note|Secondary reviewer disagreement note/);
    for (const path of ['/api/review-items', '/api/adjudication/queue', '/api/owner/users', '/api/owner/gold/readiness']) {
      expect((await getJson(page, path)).status, path).toBe(403);
    }
    expect((await page.goto('/admin')).status()).toBe(403);
    expect((await page.goto('/owner')).status()).toBe(403);
  });

  test('admin operates ordinary users and Pilot UI but cannot replace owner', async ({ page }) => {
    await login(page, 'admin', '/admin');
    await expect(page.getByRole('heading', { name: 'Admin 运营工作台' })).toBeVisible();
    const nav = await navIds(page);
    expect(nav).toContain('admin');
    expect(nav).not.toContain('console');
    expect(nav).not.toContain('owner');
    await page.goto('/admin/users');
    await expect(page.getByRole('heading', { name: '创建普通账号' })).toBeVisible();
    await expect(page.locator('#admin-role option')).toHaveCount(3);
    await page.goto('/admin/invites');
    await expect(page.getByRole('heading', { name: '创建普通角色邀请码' })).toBeVisible();
    await page.getByLabel('标签').fill('Browser researcher invite');
    await page.getByRole('button', { name: '创建邀请码' }).click();
    await expect(page.locator('#admin-invite-message')).toContainText('邀请码仅本次显示');
    await page.goto('/admin/projects');
    await expect(page.getByRole('heading', { name: '创建 Pilot 与双人任务' })).toBeVisible();
    const users = await getJson(page, '/api/admin/users');
    const owner = users.body.items.find(user => user.role === 'owner');
    expect(owner.admin_mutable).toBe(false);
    expect((await postJson(page, `/api/admin/user/${owner.user_id}/disable`)).status).toBe(403);
    expect((await postJson(page, `/api/admin/user/${owner.user_id}/change-role`, { role: 'researcher' })).status).toBe(403);
    expect((await postJson(page, `/api/admin/user/${users.body.items.find(user => user.username === 'empty-reviewer').user_id}/change-role`, { role: 'owner' })).status).toBe(403);
    expect((await getJson(page, '/api/owner/gold/readiness')).status).toBe(403);
    expect((await getJson(page, '/api/db/health')).status).toBe(403);
    expect((await page.goto('/console')).status()).toBe(403);
    expect((await page.goto('/owner')).status()).toBe(403);
  });

  test('owner governs without receiving early blind answers', async ({ page }) => {
    await login(page, 'owner', '/owner');
    await expect(page.getByRole('heading', { name: 'Owner 工作台' })).toBeVisible();
    const nav = await navIds(page);
    expect(nav).toContain('owner');
    expect(nav).not.toContain('console');
    expect(nav).not.toContain('review');
    const status = await getJson(page, '/api/owner/adjudication/status');
    expect(status.status).toBe(200);
    expect(status.body.blind_payload_included).toBe(false);
    expect(JSON.stringify(status.body)).not.toMatch(/annotations|Primary reviewer evidence note|Secondary reviewer disagreement note/);
    expect((await getJson(page, '/api/owner/users')).status).toBe(200);
    const projects = await getJson(page, '/api/owner/projects');
    expect((await getJson(page, `/api/owner/gold/readiness?project_id=${projects.body.items[0].project_id}`)).status).toBe(200);
    expect((await getJson(page, '/api/db/health')).status).toBe(403);
  });

  test('root, safe next, role change, revoke and disable invalidate sessions', async ({ browser }) => {
    const safeContext = await browser.newContext({ viewport: { width: 1366, height: 768 } });
    const safePage = await safeContext.newPage();
    await safePage.goto('/login?next=%2Fowner');
    await safePage.getByLabel('Username').fill('researcher');
    await safePage.getByLabel('Password').fill(password);
    await safePage.getByRole('button', { name: 'Sign in' }).click();
    await expect(safePage).toHaveURL(/\/discover$/);
    await safeContext.close();

    const ownerContext = await browser.newContext({ viewport: { width: 1366, height: 768 } });
    const ownerPage = await ownerContext.newPage();
    await login(ownerPage, 'owner', '/owner');
    const users = (await getJson(ownerPage, '/api/owner/users')).body.items;
    const byName = name => users.find(user => user.username === name);

    const roleContext = await browser.newContext({ viewport: { width: 1366, height: 768 } });
    const rolePage = await roleContext.newPage();
    await login(rolePage, 'role-changing', '/review');
    expect((await postJson(ownerPage, `/api/owner/user/${byName('role-changing').user_id}/change-role`, { role: 'researcher' })).status).toBe(200);
    expect((await roleContext.request.get('http://localhost:18765/api/session')).status()).toBe(401);
    await rolePage.goto('/review');
    await expect(rolePage).toHaveURL(/\/login\?next=/);
    await login(rolePage, 'role-changing', '/discover');
    expect(await navIds(rolePage)).not.toContain('review');
    await roleContext.close();

    const revokeContext = await browser.newContext({ viewport: { width: 1366, height: 768 } });
    const revokePage = await revokeContext.newPage();
    await login(revokePage, 'session-target', '/discover');
    expect((await postJson(ownerPage, `/api/owner/user/${byName('session-target').user_id}/revoke-sessions`)).status).toBe(200);
    expect((await revokeContext.request.get('http://localhost:18765/api/session')).status()).toBe(401);
    await revokeContext.close();

    const disableContext = await browser.newContext({ viewport: { width: 1366, height: 768 } });
    const disablePage = await disableContext.newPage();
    await login(disablePage, 'disable-target', '/discover');
    expect((await postJson(ownerPage, `/api/owner/user/${byName('disable-target').user_id}/disable`)).status).toBe(200);
    expect((await disableContext.request.get('http://localhost:18765/api/session')).status()).toBe(401);
    await disablePage.goto('/login');
    await disablePage.getByLabel('Username').fill('disable-target');
    await disablePage.getByLabel('Password').fill(password);
    await disablePage.getByRole('button', { name: 'Sign in' }).click();
    await expect(disablePage).toHaveURL(/\/login$/);
    await expect(disablePage.locator('.error')).toContainText('账号不可用');
    await disableContext.close();
    await ownerContext.close();
  });

  test('workspace stays usable at keyboard focus, 200 percent zoom and narrow width', async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await context.newPage();
    await login(page, 'researcher', '/discover');
    await page.keyboard.press('Tab');
    await expect(page.locator(':focus')).toBeVisible();
    await page.evaluate(() => { document.body.style.zoom = '200%'; });
    await expect(page.getByRole('heading', { name: '理解文献证据为何一致，又为何不同' })).toBeVisible();
    const width = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(width).toBeLessThanOrEqual(1);
    await context.close();
  });
});
