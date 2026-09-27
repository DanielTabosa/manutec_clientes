const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
 const browser = await chromium.launch({channel:'msedge',headless:true});
 const page = await browser.newPage({viewport:{width:1440,height:1000}});
 const base=process.env.QA_BASE_URL || 'http://127.0.0.1:8765';
 assert.ok(['127.0.0.1','localhost'].includes(new URL(base).hostname));
 const out=process.env.QA_SCREENSHOT_DIR || require('node:os').tmpdir();
 try {
 await page.goto(base+'/admin/');
 await page.locator('#id_username').fill('visual_qa');
 await page.locator('#id_password').fill('teste-visual-isolado');
 await page.locator('input[type=submit]').click();
 await page.waitForURL('**/admin/');
 await page.goto(base+'/admin/clientes/contatoadministradora/add/');
 await page.locator('#id_administradora').selectOption({label:'Administradora Visual Alfa'});
 await page.locator('#id_nome').fill('Ana Visual');
 await page.locator('#id_email').fill('ana@example.invalid');
 await page.locator('input[name=_save]').click();
 await page.waitForURL(url=>url.pathname.endsWith('/contatoadministradora/'));
 console.log('Cadastro de contato pelo navegador: OK');
 async function escolher(field, text) {
  await page.locator(`.field-${field} .select2-selection`).click();
  await page.locator('.select2-search__field').fill(text);
  await page.getByRole('option').filter({hasText:text}).click();
 }
 for (const nome of ['Condomínio Visual Sol','Condomínio Visual Mar']) {
  await page.goto(base+'/admin/clientes/responsabilidade/add/');
  await escolher('contato_administradora','Ana Visual');
  await escolher('cliente',nome);
  await page.locator('#id_funcao').fill('Financeiro');
  await page.locator('#id_data_inicio').fill('01/02/2020');
  await page.locator('input[name=_save]').click();
  await page.waitForURL('**/responsabilidade/');
 }
 console.log('Mesmo contato associado a dois clientes: OK');
 await page.goto(base+'/admin/clientes/responsabilidade/?q=Ana+Visual');
 assert.equal(await page.locator('#result_list tbody tr').count(),2);
 await page.screenshot({path:out+'/responsabilidades-antes.png',fullPage:true});
 await page.goto(base+'/admin/clientes/contatoadministradora/?q=Ana+Visual');
 await page.getByRole('link',{name:'Ana Visual',exact:true}).click();
 await page.locator('#id_telefone').fill('85999990000');
 await page.locator('input[name=_save]').click();
 await page.waitForURL(url=>url.pathname.endsWith('/contatoadministradora/'));
 console.log('Correção do contato compartilhado: OK');
 await page.goto(base+'/admin/clientes/cliente/?q=Condomínio+Visual+Sol');
 await page.locator('#result_list tbody tr').filter({hasText:'Condomínio Visual Sol'}).getByRole('link').click();
 await page.getByRole('link',{name:'Vincular, trocar ou encerrar'}).click();
 await page.locator('#id_acao').selectOption('vincular');
 await page.locator('#id_administradora').selectOption({label:'Administradora Visual Beta'});
 await page.locator('#id_data').fill('2020-03-01');
 await page.locator('input[type=submit]').click();
 await page.waitForURL(url=>url.pathname.endsWith('/change/'));
 await page.goto(base+'/admin/clientes/responsabilidade/?q=Ana+Visual');
 await page.locator('#result_list tbody tr').filter({hasText:'Condomínio Visual Sol'}).getByRole('link').first().click();
 assert.equal(await page.locator('#id_data_fim').inputValue(),'29/02/2020');
 assert.equal(await page.locator('#id_cliente').count(),0);
 await page.screenshot({path:out+'/responsabilidade-encerrada.png',fullPage:true});
 await page.goto(base+'/admin/clientes/responsabilidade/?q=Ana+Visual');
 await page.locator('#result_list tbody tr').filter({hasText:'Condomínio Visual Mar'}).getByRole('link').first().click();
 assert.equal(await page.locator('#id_data_fim').inputValue(),'');
 await page.locator('#id_data_fim').fill('01/04/2020');
 await page.locator('input[name=_save]').click();
 await page.waitForURL(url=>url.pathname.endsWith('/responsabilidade/'));
 await page.goto(base+'/admin/clientes/responsabilidade/?q=Ana+Visual');
 assert.equal(await page.locator('#result_list tbody tr').count(),2);
 await page.screenshot({path:out+'/responsabilidades-historico.png',fullPage:true});
 console.log('Troca encerrou Sol em 29/02/2020 e preservou Mar aberto; encerramento manual de Mar e histórico confirmados no navegador.');
 } finally { await browser.close(); }
})().catch(e=>{console.error(e.message);process.exit(1)});
