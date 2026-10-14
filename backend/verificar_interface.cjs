/* Interface de operação: fluxo visual contra servidor local em banco descartável. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const base = process.env.QA_BASE_URL || 'http://127.0.0.1:8765';
  assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname));
  const out = process.env.QA_SCREENSHOT_DIR || require('node:os').tmpdir();
  const errors = [];
  const nova = async (opcoes = {}) => {
    const ctx = await browser.newContext({viewport: {width: 1440, height: 900}, ...opcoes});
    const page = await ctx.newPage();
    page.on('pageerror', e => errors.push(e.message));
    page.on('dialog', d => d.accept());
    return page;
  };
  const shot = (page, nome) => page.screenshot({path: `${out}/${nome}.png`, fullPage: true});
  try {
    const page = await nova();
    await page.goto(base + '/clientes/');
    await page.waitForURL('**/entrar/**');
    await shot(page, 'interface-login');
    await page.getByLabel('Usuário').fill('visual_qa');
    await page.getByLabel('Senha').fill('teste-visual-isolado');
    await page.getByRole('button', {name: 'Entrar'}).click();
    await page.waitForURL('**/clientes/');
    await page.goto(base + '/');
    await page.getByRole('heading', {name: /Olá/}).waitFor();
    await shot(page, 'interface-inicio');
    await page.getByRole('link', {name: 'Clientes', exact: true}).click();
    await page.getByLabel('Buscar cliente').fill('Sol');
    await page.getByLabel('Buscar cliente').press('Enter');
    assert.equal(await page.locator('[data-cliente]').count(), 1);
    await shot(page, 'interface-clientes');
    await page.getByRole('link', {name: 'Condomínio Visual Sol'}).click();
    await page.getByRole('heading', {name: 'Quem recebe documentos'}).waitFor();
    await shot(page, 'interface-cliente');
    await page.getByRole('button', {name: 'Preparar envio'}).click();
    await page.getByRole('heading', {name: 'Documentos'}).waitFor();
    await page.locator('#arquivos').setInputFiles([{name: 'boleto-' + Date.now() + '.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\ninterface ' + Date.now() + '\n%%EOF\n')}]);
    await page.locator('#categoria').selectOption('boleto');
    await page.getByRole('button', {name: 'Anexar', exact: true}).click();
    await page.getByText('1 documento(s) anexado(s).').waitFor();
    await shot(page, 'interface-preparacao');
    await page.goto(base + '/preparacoes/');
    await shot(page, 'interface-preparacoes');

    const mobile = await nova({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});
    await mobile.goto(base + '/entrar/');
    await mobile.getByLabel('Usuário').fill('visual_qa');
    await mobile.getByLabel('Senha').fill('teste-visual-isolado');
    await mobile.getByRole('button', {name: 'Entrar'}).click();
    await mobile.getByRole('heading', {name: /Olá/}).waitFor();
    await shot(mobile, 'interface-mobile-inicio');
    await mobile.getByRole('button', {name: 'Abrir menu'}).click();
    await mobile.waitForTimeout(400);
    await shot(mobile, 'interface-mobile-menu');
    await mobile.keyboard.press('Escape');
    await mobile.goto(page.url().replace('/preparacoes/', '/clientes/'));
    for (const url of ['/clientes/', '/preparacoes/']) {
      await mobile.goto(base + url);
      assert.equal(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, 'rolagem horizontal em ' + url);
    }
    await mobile.goto(base + '/preparacoes/');
    await mobile.locator('[data-preparacao] a').first().click();
    assert.equal(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, 'rolagem horizontal na preparação');
    await shot(mobile, 'interface-mobile-preparacao');

    const escuro = await nova({colorScheme: 'dark'});
    await escuro.goto(base + '/entrar/');
    await escuro.getByLabel('Usuário').fill('visual_qa');
    await escuro.getByLabel('Senha').fill('teste-visual-isolado');
    await escuro.getByRole('button', {name: 'Entrar'}).click();
    await escuro.getByRole('heading', {name: /Olá/}).waitFor();
    await escuro.goto(base + '/preparacoes/');
    await escuro.locator('[data-preparacao] a').first().click();
    await shot(escuro, 'interface-escuro-preparacao');
    assert.deepEqual(errors, []);
    console.log('OK: login, início, clientes, cliente, preparação, lista; mobile sem rolagem horizontal; modo escuro.');
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e.message); process.exit(1); });
