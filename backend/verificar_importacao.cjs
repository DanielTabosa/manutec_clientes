/* Início, importação CSV e retaguarda: fluxo visual contra servidor local em banco descartável. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const b = await chromium.launch({channel: 'msedge', headless: true});
  const base = process.env.QA_BASE_URL || 'http://127.0.0.1:8765';
  assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname));
  const out = process.env.QA_SCREENSHOT_DIR || require('node:os').tmpdir();
  const erros = [];
  const entrar = async opts => {
    const p = await (await b.newContext({viewport: {width: 1440, height: 900}, ...opts})).newPage();
    p.on('pageerror', e => { if (!/Transition was aborted/.test(e.message)) erros.push(e.message); }); p.on('dialog', d => d.accept());
    await p.goto(base + '/entrar/');
    await p.getByLabel('Usuário').fill('visual_qa'); await p.getByLabel('Senha').fill('teste-visual-isolado');
    await p.getByRole('button', {name: 'Entrar', exact: true}).click(); await p.waitForURL(base + '/');
    await p.waitForTimeout(500);
    return p;
  };
  const shot = (p, nome, full = false) => p.screenshot({path: `${out}/${nome}.png`, fullPage: full});
  try {
    const p = await entrar();
    await p.getByRole('heading', {name: 'Clientes cadastrados'}).waitFor();
    await shot(p, 'imp-inicio');
    // Importação de clientes com cabeçalhos variados, linhas incompletas e uma repetida
    const id = String(Date.now()).slice(-6);
    const csv = 'Condomínio;CNPJ;Município;UF;Administradora\n' +
      `Condomínio Importado Um ${id};${id}12000101;Fortaleza;CE;Administradora Visual Alfa\n` +
      `Edifício Importado Dois ${id};${id}12000202;;;Administradora Nova ${id}\n` +
      `Condomínio Visual Sol;99000000000100;;;\n` +
      ';11.111.111/0001-11;;;\n';
    await p.getByRole('link', {name: 'Importar CSV'}).first().click();
    await p.locator('input[name="tipo"][value="clientes"]').check();
    await p.locator('#arquivo').setInputFiles({name: 'clientes.csv', mimeType: 'text/csv', buffer: Buffer.from('﻿' + csv)});
    await shot(p, 'imp-envio');
    await p.getByRole('button', {name: 'Analisar arquivo'}).click();
    await p.waitForURL('**/importar/previa/');
    assert.equal(await p.locator('[data-linha="novo"]').count(), 2);
    assert.equal(await p.locator('[data-linha="existente"]').count(), 1);
    assert.equal(await p.locator('[data-linha="erro"]').count(), 1);
    await shot(p, 'imp-previa', true);
    await p.getByRole('button', {name: /Importar 2 registro/}).click();
    await p.waitForURL('**/importar/resultado/');
    await shot(p, 'imp-resultado');
    await p.goto(base + '/clientes/?pendencia=endereco');
    await p.getByText(`Edifício Importado Dois ${id}`).waitFor();
    await shot(p, 'imp-clientes-pendencia');
    // Retaguarda
    await p.goto(base + '/admin/'); await shot(p, 'imp-admin-inicio');
    await p.goto(base + '/admin/clientes/cliente/'); await shot(p, 'imp-admin-lista');
    await p.locator('#result_list tbody tr a').first().click(); await p.waitForTimeout(300); await shot(p, 'imp-admin-form');
    // Escuro e celular
    const d = await entrar({colorScheme: 'dark'}); await shot(d, 'imp-inicio-escuro');
    await d.goto(base + '/admin/'); await shot(d, 'imp-admin-escuro');
    const m = await entrar({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});
    assert.equal(await m.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, 'rolagem no início');
    await shot(m, 'imp-inicio-mobile', true);
    await m.goto(base + '/importar/');
    assert.equal(await m.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, 'rolagem na importação');
    assert.deepEqual(erros, []);
    console.log('OK: início, importação (2 novos, 1 existente, 1 erro), filtro de pendência, retaguarda, escuro e celular.');
  } finally { await b.close(); }
})().catch(e => { console.error(e.message); process.exit(1); });
