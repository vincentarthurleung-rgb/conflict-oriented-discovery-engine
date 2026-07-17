const { test, expect } = require('@playwright/test');
const fs = require('fs');

const out = 'test-results/system-a-v2-integration';
fs.mkdirSync(out, { recursive: true });

async function login(page) {
  await page.goto('/login');
  await page.getByLabel('Username').fill('owner');
  await page.getByLabel('Password').fill('correct horse battery staple');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.locator('#current-user')).toContainText('Owner');
}

test('v2 domain, capability and conditional evaluation flow', async ({ page }, testInfo) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => { if (response.status() >= 500) errors.push(`${response.status()} ${response.url()}`); });
  await login(page);
  await page.goto('/discover');
  await expect(page.getByRole('heading', { name: '按领域浏览' })).toBeVisible();
  await expect(page.locator('.case-card')).toHaveCount(11);
  const domains = await page.request.get('/api/domains').then(response => response.json());
  const hasV2Domains = domains.items.some(item => item.domain_id === 'pathway_biology');
  if (hasV2Domains) {
    await expect(page.getByRole('link', { name: 'Pathway Biology' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'General Biomedical' })).toBeVisible();
  }
  await expect(page.getByRole('link', { name: '待分类 / 旧版领域信息' })).toBeVisible();
  await page.screenshot({ path: `${out}/v2-discover-${testInfo.project.name}.png`, fullPage: true });

  const selectedDomain = hasV2Domains ? 'Pathway Biology' : '待分类 / 旧版领域信息';
  await page.getByRole('link', { name: selectedDomain }).click();
  await expect(page.getByRole('heading', { name: selectedDomain })).toBeVisible();
  await expect(page.locator('.case-card')).toHaveCount(hasV2Domains ? 5 : 11);
  await page.screenshot({ path: `${out}/v2-domain-${testInfo.project.name}.png`, fullPage: true });

  await page.goto('/case/wnt_beta_catenin_cancer_stemness_immunity_discovery_v1');
  await expect(page.locator('.case-status-stack')).toContainText('尚未有效生成');
  await expect(page.locator('.case-status-stack')).toContainText(hasV2Domains ? '部分覆盖' : '实验上下文 可用');
  const dossier = await page.locator('.mechanism-unit a[href^="/dossier/"]').first().getAttribute('href');
  await page.goto(dossier);
  await page.locator('#reasoning-trace').scrollIntoViewIfNeeded();
  await expect(page.locator('#reasoning-trace')).toContainText('已生成记录，但尚无可用实验推理步骤');
  await page.screenshot({ path: `${out}/v2-wnt-reasoning-${testInfo.project.name}.png` });

  await page.goto('/owner/claim-sampling');
  await expect(page.getByRole('heading', { name: 'Claim Evaluation Sampling' })).toBeVisible();
  const readiness = await page.request.get('/api/owner/claim-evaluation/readiness').then(response => response.json());
  if (readiness.source_unit_count) {
    await expect(page.locator('#workspace')).toContainText(`${readiness.source_unit_count} 个源文本单元`);
    await expect(page.locator('#workspace')).toContainText('needs_exhaustive_gold');
    await page.locator('#claim-sample-size').fill('7');
    await page.locator('#claim-sample-seed').fill('17');
    await page.locator('#claim-sample-domains').fill(hasV2Domains ? 'pathway_biology' : '');
    await page.getByRole('button', { name: '创建确定性 Pilot 批次' }).click();
    await expect(page.locator('#claim-sample-message')).toContainText(/Pilot 抽样批次已创建|相同批次已存在/);
    await expect(page.locator('#claim-sample-message')).toContainText('7 /');
    await expect(page.locator('#claim-sample-message')).toContainText('Claim Recall / F1 仍需穷尽式 Gold');
  } else {
    await expect(page.locator('#workspace')).toContainText('0 个源文本单元');
    await expect(page.getByRole('button', { name: '创建确定性 Pilot 批次' })).toBeDisabled();
  }
  await expect(page.locator('#workspace')).toContainText('不可用指标不会显示为 0');
  await page.screenshot({ path: `${out}/v2-claim-sampling-${testInfo.project.name}.png`, fullPage: true });

  if (testInfo.project.name === 'chromium-1366') {
    await page.goto('/discover');
    await page.evaluate(() => { document.body.style.zoom = '200%'; });
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    await page.screenshot({ path: `${out}/v2-200-percent-zoom.png`, fullPage: true });
  }
  expect(errors).toEqual([]);
});
