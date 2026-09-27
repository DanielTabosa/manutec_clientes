const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1050}});
 const base=process.env.QA_BASE_URL||'http://127.0.0.1:8765';
 assert.ok(['127.0.0.1','localhost'].includes(new URL(base).hostname));
 const nome='Destinatário Visual sem email '+Date.now();
 const out=process.env.QA_SCREENSHOT_DIR||require('node:os').tmpdir();
 try{
 await page.goto(base+'/admin/');
 await page.locator('#id_username').fill('visual_qa');
 await page.locator('#id_password').fill('teste-visual-isolado');
 await page.locator('input[type=submit]').click();await page.waitForURL('**/admin/');
 await page.goto(base+'/admin/clientes/contatoadministradora/add/');
 await page.locator('#id_administradora').selectOption({label:'Administradora Visual Alfa'});
 await page.locator('#id_nome').fill(nome);
 await page.locator('#id_telefone').fill('85999990000');
 await page.locator('input[name=_save]').click();await page.waitForURL('**/contatoadministradora/');
 await page.goto(base+'/admin/clientes/administradora/?q=Administradora+Visual+Alfa');
 await page.locator('#result_list tbody tr').getByRole('link').first().click();
 await page.getByRole('link',{name:'Destinatários e histórico'}).click();
 const adminUrl=page.url();
 let row=page.locator('tr').filter({hasText:nome});
 await row.locator('input[name$="-boleto"]').check();
 await row.locator('input[name$="-laudo"]').check();
 await page.getByRole('button',{name:'Salvar destinatários'}).click();
 await page.waitForURL(adminUrl);
 assert.ok(await page.getByText('Este padrão é usado por 2 condomínio(s).').isVisible());
 await page.screenshot({path:out+'/destinatarios-padrao.png',fullPage:true});
 async function abrirCliente(nome){
 await page.goto(base+'/admin/clientes/cliente/?q='+encodeURIComponent(nome));
 await page.locator('#result_list tbody tr').getByRole('link').first().click();
 await page.getByRole('link',{name:'Destinatários e histórico'}).click();
 }
 await abrirCliente('Condomínio Visual Sol');
 assert.ok(await page.getByText('boleto, laudo (padrão da administradora)').isVisible());
 await page.locator('#id_modo').selectOption('usar');
 row=page.locator('tr').filter({hasText:nome});
 await row.locator('input[name$="-encerrado_local"]').check();
 await page.getByRole('button',{name:'Salvar destinatários'}).click();
 await page.waitForLoadState('networkidle');
 assert.ok(await page.getByText('Nenhum destinatário efetivo.',{exact:true}).isVisible());
 await page.screenshot({path:out+'/destinatarios-encerramento-local.png',fullPage:true});
 await abrirCliente('Condomínio Visual Mar');
 assert.ok(await page.getByText('boleto, laudo (padrão da administradora)').isVisible());
 await page.goto(adminUrl);
 row=page.locator('tr').filter({hasText:nome});
 await row.locator('input[name$="-boleto"]').uncheck();
 await row.locator('input[name$="-laudo"]').uncheck();
 await row.locator('input[name$="-cobranca"]').check();
 await page.getByRole('button',{name:'Salvar destinatários'}).click();
 await page.waitForLoadState('networkidle');
 await abrirCliente('Condomínio Visual Mar');
 assert.ok(await page.getByText('cobrança (padrão da administradora)').isVisible());
 await page.screenshot({path:out+'/destinatarios-heranca.png',fullPage:true});
 console.log('Visual: contato sem email, padrão de duas categorias, encerramento local, isolamento de outro cliente e alteração herdada aprovados.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exit(1)});