const { test, expect } = require('@playwright/test');
const fs = require('fs');

const output = 'test-results/admin-operations-redesign';
const password = 'correct horse battery staple';
fs.mkdirSync(output, { recursive: true });

async function login(page, username = 'admin') {
  await page.goto('/login');
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.locator('#current-user')).not.toBeEmpty();
}

async function openAssignmentPeople(page, captureSource = false) {
  await page.goto('/admin/assignments');
  await page.locator('[data-assignment-project]').filter({ hasText: 'Operations Pilot' }).click();
  await page.locator('[data-assignment-next]').click();
  if (captureSource) {
    await page.screenshot({ path: `${output}/assignment-source.png`, fullPage: true });
  }
  await page.locator('[data-assignment-source="existing_review_items"]').click();
  await page.locator('[data-assignment-next]').click();
  await expect(page.getByRole('heading', { name: '选择人员和分配策略' })).toBeVisible();
}

test('Admin operations overview and user management are action-oriented', async ({ page }, testInfo) => {
  await login(page);
  await expect(page.getByRole('heading', { name: '今天需要处理什么？' })).toBeVisible();
  await expect(page.getByText('没有任务的 Reviewer')).toBeVisible();
  await expect(page.getByText('从未登录').first()).toBeVisible();
  if (testInfo.project.name === 'chromium-1366') {
    await page.screenshot({ path: `${output}/admin-overview.png`, fullPage: true });
  }

  await page.goto('/admin/users');
  await expect(page.getByRole('heading', { name: '用户总览' })).toBeVisible();
  await expect(page.locator('[data-user-summary]')).toHaveCount(8);
  await page.locator('[data-user-summary="reviewers_without_tasks"]').click();
  await expect(page.locator('#user-table-body')).toContainText('Empty Reviewer');
  await page.locator('[data-user-summary="all"]').click();
  await page.locator('#user-search').fill('Empty Reviewer');
  await expect(page.locator('#user-table-body tr')).toHaveCount(1);
  await page.locator('#user-search').fill('');
  await page.locator('#user-role-filter').selectOption('reviewer');
  await page.locator('#user-task-filter').selectOption('false');
  await expect(page.locator('#user-table-body')).toContainText('Empty Reviewer');
  if (testInfo.project.name === 'chromium-1366') {
    await page.screenshot({ path: `${output}/users-overview.png`, fullPage: true });
  }
  await page.locator('[data-open-user]').filter({ hasText: /Empty Reviewer|查看/ }).first().click();
  await expect(page.locator('#user-drawer')).toHaveClass(/open/);
  await expect(page.locator('#role-impact')).toContainText('当前登录 Session 将失效');
  await expect(page.locator('#role-impact')).toContainText('现有 Assignment 不会自动删除');
  await expect(page.locator('#user-drawer')).toContainText('最近 7 天完成');
  await expect(page.locator('#user-drawer')).toContainText('任务来源分布');
  if (testInfo.project.name === 'chromium-1366') {
    await page.waitForTimeout(350);
    await page.screenshot({ path: `${output}/user-detail-drawer.png` });
    await page.screenshot({ path: `${output}/user-workload.png`, fullPage: true });
  }
  await page.keyboard.press('Escape');
  await expect(page.locator('#user-drawer')).not.toHaveClass(/open/);

  await page.locator('#user-role-filter').selectOption('');
  await page.locator('#user-task-filter').selectOption('');
  await page.locator('#user-sort').selectOption('pending_desc');
  await page.locator('tr').filter({ hasText: 'Empty Reviewer' }).locator('.user-check').check();
  page.once('dialog', async dialog => {
    expect(dialog.message()).toContain('1 位用户');
    expect(dialog.message()).toContain('Session');
    await dialog.dismiss();
  });
  await page.getByRole('button', { name: '批量禁用' }).click();
  await page.locator('#user-search').fill('no-such-operations-user');
  await expect(page.locator('.operations-empty')).toContainText('没有符合条件的用户');
  await page.locator('.operations-empty').getByRole('button', { name: '清除筛选' }).click();
  await page.locator('tr').filter({ hasText: '@owner' }).locator('[data-open-user]').first().click();
  await expect(page.locator('#user-drawer')).toContainText('该账号受保护');
  await expect(page.locator('#drawer-role')).toHaveCount(0);
});

test('assignment wizard validates workload and creates atomically', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-1366', 'The write workflow runs once against the shared ephemeral database.');
  await login(page);
  await openAssignmentPeople(page, true);
  const primaryId = await page.locator('#assignment-primary option').filter({ hasText: 'Primary' }).getAttribute('value');
  const secondaryId = await page.locator('#assignment-secondary option').filter({ hasText: 'Secondary' }).getAttribute('value');
  const adjudicatorId = await page.locator('#assignment-adjudicator option').filter({ hasText: 'Adjudicator' }).getAttribute('value');
  await page.locator('#assignment-primary').selectOption(primaryId);
  await page.locator('#assignment-secondary').selectOption(primaryId);
  await page.locator('#assignment-adjudicator').selectOption(adjudicatorId);
  await page.locator('[data-assignment-next]').click();
  await expect(page.locator('.validation-list.blockers')).toContainText('Primary 与 Secondary');
  await expect(page.locator('[data-assignment-create]')).toBeDisabled();

  await page.locator('[data-assignment-back]').click();
  await page.locator('#assignment-primary').selectOption(primaryId);
  await page.locator('#assignment-secondary').selectOption(secondaryId);
  await page.locator('#assignment-adjudicator').selectOption(adjudicatorId);
  await page.locator('[data-assignment-next]').click();
  await expect(page.locator('.operations-loading')).toHaveCount(0);
  await expect(page.locator('.preview-metrics')).toContainText('Review Items');
  await expect(page.locator('table')).toContainText('分配后待办');
  await page.screenshot({ path: `${output}/assignment-workload-preview.png`, fullPage: true });
  await page.screenshot({ path: `${output}/assignment-final-preview.png`, fullPage: true });
  await expect(page.locator('[data-assignment-create]')).toBeEnabled();
  await page.locator('[data-assignment-create]').click();
  await expect(page.getByRole('heading', { name: '审核批次已创建' })).toBeVisible();
  await expect(page.locator('.creation-result')).toContainText('三个角色批次');
  await expect(page.locator('.creation-result')).toContainText('创建者');
  await page.screenshot({ path: `${output}/assignment-created.png`, fullPage: true });
  await page.getByRole('link', { name: '查看批次' }).click();
  await expect(page.getByRole('heading', { name: /Operations Pilot · 审核批次/ })).toBeVisible();
  await page.getByRole('button', { name: '用户负载' }).click();
  await expect(page.locator('#batch-tab-body')).toContainText('Primary');
  await page.screenshot({ path: `${output}/batch-detail.png`, fullPage: true });

  const changed = await page.evaluate(async () => {
    const session = await fetch('/api/session').then(r => r.json());
    const response = await fetch('/api/admin/batches/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token },
      body: JSON.stringify({
        project_id: 'does-not-matter',
        item_ids: [],
        expected_frame_hash: 'stale-frame-hash'
      })
    });
    return { status: response.status, body: await response.json() };
  });
  expect(changed.status).toBe(409);
  expect(JSON.stringify(changed.body)).toContain('sampling_frame_changed');
});

test('sampling wizard separates purpose, previews distributions, and reuses identical create', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-1366', 'The sampling write workflow runs once.');
  await login(page);
  await page.goto('/admin/sampling');
  await expect(page.getByText('预测 Claim 精度审核')).toBeVisible();
  await expect(page.getByText('Source-unit 穷尽 Gold')).toBeVisible();
  await expect(page.getByText('不能单独评估 Recall / 完整 F1')).toBeVisible();
  await page.screenshot({ path: `${output}/sampling-purpose.png`, fullPage: true });
  await page.locator('[data-sampling-purpose="source_unit_exhaustive_gold"]').click();
  await page.locator('[data-sampling-next]').click();
  await expect(page.locator('.frame-card')).toContainText('12');
  await expect(page.locator('.frame-card')).toContainText('selected_for_l1_extraction');
  await page.screenshot({ path: `${output}/sampling-frame.png`, fullPage: true });
  await page.locator('[data-sampling-next]').click();
  await page.locator('#sample-min-domain').fill('1');
  await page.locator('#sample-min-case').fill('1');
  await page.locator('#sample-paper-cap').fill('2');
  await page.locator('[data-sampling-next]').click();
  await page.locator('#sample-size').fill('6');
  await page.locator('#sample-seed').fill('20260731');
  await page.locator('[data-sampling-next]').click();
  await expect(page.locator('.operations-loading')).toHaveCount(0);
  await expect(page.locator('table').first()).toContainText('抽样比例');
  await expect(page.locator('.preview-metrics')).toContainText('覆盖 Papers');
  await expect(page.locator('.wizard-content')).toContainText('重复');
  await expect(page.locator('.wizard-content')).toContainText('最大单 Paper');
  await page.screenshot({ path: `${output}/sampling-distribution.png`, fullPage: true });
  await page.locator('[data-sampling-create]').click();
  await expect(page.locator('.creation-result')).toContainText('抽样批次已创建');
  await expect(page.locator('.metric-readiness')).toContainText('needs_exhaustive_gold · null');
  await expect(page.locator('[data-sampling-to-assignment]')).toBeVisible();
  await page.screenshot({ path: `${output}/sampling-created.png`, fullPage: true });

  const repeat = await page.evaluate(async () => {
    const session = await fetch('/api/session').then(r => r.json());
    const response = await fetch('/api/admin/sampling/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token },
      body: JSON.stringify({
        purpose: 'source_unit_exhaustive_gold', sample_size: 6, random_seed: 20260731,
        min_per_domain: 1, min_per_case: 1, max_per_paper: 2,
        exclusions: {
          exclude_annotated: true, exclude_duplicate_source_unit: true,
          exclude_duplicate_text_hash: true, exclude_no_text: true,
          exclude_unsupported_schema: true, exclude_inactive_case: true,
          exclude_legacy_invalid: true
        }
      })
    });
    return response.json();
  });
  expect(repeat.creation_status).toBe('no_op');
  expect(repeat.reused).toBe(true);
});

test('role permissions and operations payload remain blind', async ({ browser }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-1366', 'Permission matrix is checked once.');
  for (const username of ['researcher', 'primary', 'adjudicator', 'developer']) {
    const context = await browser.newContext();
    const page = await context.newPage();
    await login(page, username);
    const result = await page.evaluate(async () => {
      const response = await fetch('/api/admin/users');
      return { status: response.status, text: await response.text() };
    });
    expect(result.status).toBe(403);
    await context.close();
  }
  const adminContext = await browser.newContext();
  const adminPage = await adminContext.newPage();
  await login(adminPage);
  const adminPayload = await adminPage.evaluate(async () => {
    const response = await fetch('/api/admin/users');
    return { status: response.status, text: await response.text() };
  });
  expect(adminPayload.status).toBe(200);
  expect(adminPayload.text).not.toMatch(/final_label|structured_fields_json|password_hash|reset_token|session_hash|session_version|invite_source|annotations/i);
  for (const path of ['/api/admin/batches', '/api/admin/sampling/frames']) {
    const result = await adminPage.evaluate(async path => {
      const response = await fetch(path);
      return { status: response.status, text: await response.text() };
    }, path);
    expect(result.status).toBe(200);
    expect(result.text).not.toMatch(/final_label|structured_fields_json|annotations/i);
  }
  await adminContext.close();

  const ownerContext = await browser.newContext();
  const ownerPage = await ownerContext.newPage();
  await login(ownerPage, 'owner');
  await ownerPage.goto('/owner/users');
  await expect(ownerPage.getByRole('heading', { name: '用户总览' })).toBeVisible();
  await expect(ownerPage.locator('.owner-side')).toContainText('Gold');
  await expect(ownerPage.locator('.owner-side')).toContainText('System State');
  await ownerContext.close();
});

test('responsive, zoom, keyboard, loading, failure and retry states remain usable', async ({ page }, testInfo) => {
  await login(page);
  await page.goto('/admin/users');
  await page.keyboard.press('Tab');
  expect(await page.evaluate(() => document.activeElement !== document.body)).toBe(true);
  if (testInfo.project.name === 'chromium-1366') {
    await page.evaluate(() => { document.body.style.zoom = '200%'; });
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);

  await page.route('**/api/admin/overview', route => route.fulfill({
    status: 503, contentType: 'application/json', body: JSON.stringify({ error: 'temporary_unavailable' })
  }));
  await page.goto('/admin');
  await expect(page.getByRole('button', { name: '重试' })).toBeVisible();
});
