/* Contratos na interface própria: fluxo visual contra servidor local em banco descartável. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const base = process.env.QA_BASE_URL || 'http://127.0.0.1:8765';
  assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname));
  const out = process.env.QA_SCREENSHOT_DIR || require('node:os').tmpdir();
  const errors = [];
  const tipo = 'Tipo Visual ' + Date.now();
  const entrar = async opcoes => {
    const ctx = await browser.newContext({viewport: {width: 1440, height: 900}, ...opcoes});
    const page = await ctx.newPage();
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(base + '/entrar/');
    await page.getByLabel('Usuário').fill('visual_qa');
    await page.getByLabel('Senha').fill('teste-visual-isolado');
    await page.getByRole('button', {name: 'Entrar'}).click();
    await page.getByRole('heading', {name: /Olá/}).waitFor();
    return page;
  };
  const shot = (page, nome) => page.screenshot({path: `${out}/${nome}.png`, fullPage: true});
  try {
    const page = await entrar();
    // Início: "Ver todos" no topo de cada quadro.
    for (const nome of ['Clientes cadastrados', 'Administradoras', 'Contratos ativos']) {
      const quadro = page.locator('section', {has: page.getByRole('heading', {name: nome, exact: true})}).first();
      await quadro.getByRole('link', {name: /Ver tod/}).first().waitFor();
    }
    await shot(page, 'ctr-inicio');
    // Tipo novo pela tela de tipos.
    await page.goto(base + '/contratos/tipos/');
    await page.getByLabel('Nome do tipo').fill(tipo);
    await page.getByRole('button', {name: 'Cadastrar tipo'}).click();
    await page.getByText(`Tipo “${tipo}” cadastrado.`).waitFor();
    await shot(page, 'ctr-tipos');
    // Contrato novo na ficha do cliente.
    await page.goto(base + '/clientes/?q=Visual Sol');
    await page.getByRole('link', {name: 'Condomínio Visual Sol'}).first().click();
    await page.getByRole('link', {name: 'Novo contrato'}).click();
    await page.getByLabel('Tipo').selectOption({label: tipo});
    await page.getByLabel('Situação').selectOption('suspenso');
    await page.getByLabel('Início').fill('2025-02-01');
    await shot(page, 'ctr-form');
    await page.getByRole('button', {name: 'Cadastrar contrato'}).click();
    await page.getByText('Contrato cadastrado.').waitFor();
    await page.locator('tr[data-contrato]', {hasText: tipo}).waitFor();
    await shot(page, 'ctr-ficha');
    // Lista com filtro por situação e por tipo.
    await page.goto(base + '/contratos/?situacao=suspenso');
    await page.locator('tr[data-contrato]', {hasText: tipo}).waitFor();
    await page.getByLabel('Tipo de contrato').selectOption({label: `${tipo} (1)`});
    await page.waitForURL(/tipo=\d+/);
    assert.equal(await page.locator('tr[data-contrato]').count(), 1);
    await shot(page, 'ctr-lista');
    // Celular: sem rolagem horizontal.
    const cel = await entrar({viewport: {width: 390, height: 844}, isMobile: true});
    for (const rota of ['/', '/contratos/', '/contratos/tipos/']) {
      await cel.goto(base + rota);
      const largura = await cel.evaluate(() => document.documentElement.scrollWidth);
      assert.ok(largura <= 390, `${rota} rola na horizontal (${largura}px)`);
    }
    await shot(cel, 'ctr-lista-celular');
    assert.deepEqual(errors, []);
    console.log('Contratos: fluxo visual aprovado; capturas em', out);
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e); process.exit(1); });
