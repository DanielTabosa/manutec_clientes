/* Cadastros da interface própria: fluxo visual contra servidor local em banco descartável. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const base = process.env.QA_BASE_URL || 'http://127.0.0.1:8765';
  assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname));
  const out = process.env.QA_SCREENSHOT_DIR || require('node:os').tmpdir();
  const errors = [];
  const contato = 'Contato Visual ' + Date.now();
  const entrar = async opcoes => {
    const ctx = await browser.newContext({viewport: {width: 1440, height: 900}, ...opcoes});
    const page = await ctx.newPage();
    page.on('pageerror', e => errors.push(e.message));
    page.on('dialog', d => d.accept());
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
    // Novo cliente com consulta de CNPJ real (CNPJ público) e validação de obrigatórios.
    await page.goto(base + '/clientes/novo/');
    await page.getByLabel('CNPJ', {exact: true}).fill('00.000.000/0001-91');
    await page.getByText(/Consulta concluída|Consulta indisponível|não encontrado/).waitFor({timeout: 30000});
    await shot(page, 'cad-novo-cliente');
    await page.getByLabel('Razão social').fill('');
    await page.getByRole('button', {name: 'Cadastrar cliente'}).click();
    await page.getByText('Confira os campos destacados.').waitFor();
    await shot(page, 'cad-novo-cliente-erros');
    // Ficha do cliente, contato novo e destinatários.
    await page.goto(base + '/clientes/?q=Sol');
    await page.getByRole('link', {name: 'Condomínio Visual Sol'}).click();
    await page.getByRole('link', {name: 'Novo contato'}).click();
    await page.getByLabel('Nome', {exact: true}).fill(contato);
    await page.getByLabel('E-mail').fill('visual.' + Date.now() + '@example.invalid');
    await page.getByLabel('Data de início').fill('2024-01-01');
    await page.getByRole('button', {name: 'Cadastrar contato'}).click();
    await page.getByText('Contato cadastrado.', {exact: false}).waitFor();
    await shot(page, 'cad-ficha-cliente');
    await page.getByRole('link', {name: 'Configurar'}).click();
    await page.getByRole('heading', {name: 'Quem recebe documentos'}).waitFor();
    const linha = page.locator('[data-destinatario]').filter({hasText: contato});
    await linha.locator('input[name$="-nota_fiscal"]').check();
    await page.getByRole('button', {name: 'Salvar destinatários'}).click();
    await page.getByText('Destinatários atualizados.', {exact: false}).waitFor();
    await shot(page, 'cad-destinatarios');
    // Administradoras.
    await page.getByRole('link', {name: 'Administradoras', exact: true}).click();
    await shot(page, 'cad-administradoras');
    await page.getByRole('link', {name: 'Administradora Visual Alfa'}).click();
    await page.getByRole('heading', {name: 'Contatos da empresa'}).waitFor();
    await shot(page, 'cad-administradora');

    const mobile = await entrar({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});
    for (const url of ['/clientes/novo/', '/administradoras/']) {
      await mobile.goto(base + url);
      assert.equal(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, 'rolagem horizontal em ' + url);
    }
    await mobile.goto(page.url().replace(/administradoras\/\d+\/$/, 'clientes/'));
    await mobile.goto(base + '/clientes/?q=Sol');
    await mobile.getByRole('link', {name: 'Condomínio Visual Sol'}).click();
    await mobile.getByRole('link', {name: 'Configurar'}).click();
    assert.equal(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, 'rolagem horizontal nos destinatários');
    await shot(mobile, 'cad-mobile-destinatarios');
    assert.deepEqual(errors, []);
    console.log('OK: novo cliente com consulta, erros de validação, contato, destinatários, administradoras; mobile sem rolagem horizontal.');
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e.message); process.exit(1); });
