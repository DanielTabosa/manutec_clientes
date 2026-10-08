/* Fluxos locais do prototipo: nenhuma API, banco ou mensagem real. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const fs = require('node:fs');

(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const page = await browser.newPage({viewport: {width: 1440, height: 1050}});
  const errors = [], network = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (/^https?:/.test(request.url())) network.push(request.url()); });
  const url = pathToFileURL(path.join(__dirname, '../docs/prototipos/documentos/index.html')).href;
  const screenshotDir = process.env.QA_SCREENSHOT_DIR;
  try {
    await page.goto(url);
    await page.getByRole('button', {name: 'Continuar'}).click();
    await page.getByRole('button', {name: 'Usar documentos de exemplo'}).click();
    assert.equal(await page.locator('[data-attachment]').count(), 2);
    await page.getByRole('button', {name: 'Continuar'}).click();
    const recipients = page.locator('[data-recipient]');
    assert.match(await recipients.filter({hasText: 'Ana Lima'}).innerText(), /boleto-exemplo.pdf/);
    assert.match(await recipients.filter({hasText: 'Ana Lima'}).innerText(), /nota-exemplo.pdf/);
    assert.doesNotMatch(await recipients.filter({hasText: 'Bruno Costa'}).innerText(), /nota-exemplo.pdf/);
    assert.doesNotMatch(await recipients.filter({hasText: 'Carla Alves'}).innerText(), /boleto-exemplo.pdf/);
    assert.match(await recipients.filter({hasText: 'Davi Santos'}).innerText(), /Sem e-mail/);
    if (screenshotDir) {
      fs.mkdirSync(screenshotDir, {recursive: true});
      await page.screenshot({path: path.join(screenshotDir, 'documentos-conferencia.png'), fullPage: true});
    }
    await page.getByRole('button', {name: 'Continuar'}).click();
    assert.equal(await page.getByRole('button', {name: 'Simular preparação', exact: true}).isEnabled(), false);
    await page.getByLabel('Conferi os destinatários aptos e seus anexos.').check();
    await page.getByRole('button', {name: 'Simular preparação', exact: true}).click();
    await page.getByRole('heading', {name: 'Preparação simulada'}).waitFor();
    assert.match(await page.locator('#resultado').innerText(), /3 destinatários/);
    assert.match(await page.locator('#resultado').innerText(), /Nenhuma mensagem foi enviada/);
    await page.getByRole('button', {name: 'Voltar à revisão'}).click();
    assert.equal(await page.getByLabel('Conferi os destinatários aptos e seus anexos.').isChecked(), false);
    await page.getByRole('button', {name: '2 Anexos'}).click();
    await page.getByRole('button', {name: 'Remover nota-exemplo.pdf'}).click();
    await page.getByRole('button', {name: 'Continuar'}).click();
    assert.match(await recipients.filter({hasText: 'Carla Alves'}).innerText(), /Nenhum anexo/);
    await page.getByRole('button', {name: 'Continuar'}).click();
    assert.doesNotMatch(await page.locator('#revisao-lista').innerText(), /Carla Alves/);
    await page.getByRole('button', {name: '2 Anexos'}).click();
    await page.locator('#arquivos').setInputFiles({name: 'invalido.pdf', mimeType: 'application/pdf', buffer: Buffer.from('<html>invalido</html>')});
    await page.getByText('invalido.pdf: o arquivo não parece ser um PDF completo.').waitFor();
    assert.equal(await page.locator('[data-attachment]').count(), 1);
    await page.getByRole('button', {name: 'Visualizar boleto-exemplo.pdf'}).click();
    assert.equal(await page.locator('dialog').isVisible(), true);
    await page.getByRole('button', {name: 'Fechar visualização'}).click();
    await page.setViewportSize({width: 390, height: 844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    if (screenshotDir) await page.screenshot({path: path.join(screenshotDir, 'documentos-mobile.png'), fullPage: true});
    assert.deepEqual(errors, []);
    assert.deepEqual(network, []);
    console.log('OK: fluxo completo, categorias independentes, sem email, confirmacao, retorno, remocao, PDF invalido, visualizacao e mobile; nenhuma requisicao HTTP.');
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error.message); process.exit(1);});
