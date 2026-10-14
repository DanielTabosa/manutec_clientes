/* Fluxo visual da preparação de envio, somente contra servidor local em banco descartável. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const page = await browser.newPage({viewport: {width: 1440, height: 1050}});
  const base = process.env.QA_BASE_URL || 'http://127.0.0.1:8765';
  assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname));
  const out = process.env.QA_SCREENSHOT_DIR || require('node:os').tmpdir();
  const pdf = (nome, conteudo) => ({name: nome, mimeType: 'application/pdf', buffer: Buffer.from(`%PDF-1.4\n${conteudo}\n%%EOF\n`)});
  const id = Date.now(), nome = 'Bruno Visual ' + id, email = `bruno.${id}@example.invalid`;
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('dialog', d => d.accept());
  try {
    await page.goto(base + '/admin/');
    await page.locator('#id_username').fill('visual_qa');
    await page.locator('#id_password').fill('teste-visual-isolado');
    await page.locator('input[type=submit]').click(); await page.waitForURL('**/admin/');
    // Destinatário com e-mail no padrão da administradora: recebe boleto.
    await page.goto(base + '/admin/clientes/contatoadministradora/add/');
    await page.locator('#id_administradora').selectOption({label: 'Administradora Visual Alfa'});
    await page.locator('#id_nome').fill(nome);
    await page.locator('#id_email').fill(email);
    await page.locator('input[name=_save]').click(); await page.waitForURL('**/contatoadministradora/');
    await page.goto(base + '/admin/clientes/administradora/?q=Administradora+Visual+Alfa');
    await page.locator('#result_list tbody tr').getByRole('link').first().click();
    await page.getByRole('link', {name: 'Destinatários e histórico'}).click();
    await page.locator('tr').filter({hasText: nome}).locator('input[name$="-boleto"]').check();
    await page.getByRole('button', {name: 'Salvar destinatários'}).click();
    // Preparação a partir do cadastro do cliente.
    const preparar = async () => {
      await page.goto(base + '/admin/clientes/cliente/?q=Condom%C3%ADnio+Visual+Sol');
      await page.locator('#result_list tbody tr').getByRole('link').first().click();
      await page.getByRole('link', {name: 'Preparar envio de documentos'}).click();
      await page.locator('input[name=_save]').click();
      await page.getByRole('heading', {name: /Documentos/}).waitFor();
    };
    await preparar();
    await page.locator('#arquivos').setInputFiles([pdf('boleto-outubro.pdf', 'visual ' + id), {name: 'quebrado.pdf', mimeType: 'application/pdf', buffer: Buffer.from('<html>')}]);
    await page.locator('#categoria').selectOption('boleto');
    await page.locator('#referencia').fill('Vencimento 13/11/2026');
    await page.getByRole('button', {name: 'Anexar'}).click();
    await page.getByText('quebrado.pdf: o arquivo não parece ser um PDF completo.').waitFor();
    assert.equal(await page.locator('[data-documento]').count(), 1);
    assert.match(await page.locator('[data-envio]').filter({hasText: email}).innerText(), /boleto-outubro\.pdf/);
    assert.equal(await page.locator('#confirmar').isDisabled(), true);
    await page.screenshot({path: out + '/preparacao-rascunho.png', fullPage: true});
    await page.getByLabel('Conferi os destinatários aptos e seus anexos.').check();
    await page.getByRole('button', {name: 'Confirmar preparação'}).click();
    await page.getByText('Nenhuma mensagem foi enviada', {exact: false}).first().waitFor();
    await page.screenshot({path: out + '/preparacao-confirmada.png', fullPage: true});
    // Envio com backend de arquivo do servidor de QA: nenhuma mensagem real sai.
    await page.getByRole('button', {name: /Enviar e-mails \(1\)/}).click();
    await page.getByText('aceito(s) pelo servidor', {exact: false}).first().waitFor();
    assert.equal(await page.locator('[data-envio]').filter({hasText: email}).locator('[data-status-envio]').getAttribute('data-status-envio'), 'aceito');
    assert.equal(await page.getByRole('button', {name: /Enviar e-mails/}).count(), 0);
    await page.screenshot({path: out + '/preparacao-enviada.png', fullPage: true});
    // Mesmo PDF ao mesmo e-mail: alerta de reenvio e motivo exigido.
    await preparar();
    await page.locator('#arquivos').setInputFiles([pdf('boleto-copia.pdf', 'visual ' + id)]);
    await page.locator('#categoria').selectOption('boleto');
    await page.getByRole('button', {name: 'Anexar'}).click();
    await page.getByText('Possível reenvio.').waitFor();
    await page.getByLabel('Conferi os destinatários aptos e seus anexos.').check();
    await page.getByRole('button', {name: 'Confirmar preparação'}).click();
    await page.getByText('Informe o motivo do reenvio', {exact: false}).waitFor();
    await page.setViewportSize({width: 390, height: 844});
    assert.equal(await page.evaluate(() => document.querySelector('.prep').scrollWidth <= document.querySelector('.prep').clientWidth + 1), true);
    await page.screenshot({path: out + '/preparacao-reenvio-mobile.png', fullPage: true});
    assert.deepEqual(errors, []);
    console.log('OK: rascunho, PDF inválido, destinatários, confirmação, alerta de reenvio e mobile.');
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e.message); process.exit(1); });
