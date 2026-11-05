import { test, expect } from '@playwright/test';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';

let origin;
let fixture;
let port;
test.beforeAll(async () => {
  fixture=spawn(process.env.PILOT_TEST_PYTHON || 'python',[
    fileURLToPath(new URL('../../backend/tests/serve_pilot_access_browser.py',import.meta.url)),
  ],{stdio:['ignore','pipe','pipe']});
  port=await new Promise((resolve,reject)=>{
    let buffer='';
    fixture.stdout.on('data',chunk=>{
      buffer+=chunk.toString();
      if(buffer.includes('\n')) {
        try {resolve(JSON.parse(buffer.split('\n')[0]).port);} catch(error) {reject(error);}
      }
    });
    fixture.once('error',reject);
    fixture.once('exit',code=>reject(new Error(`Synthetic portal exited: ${code}`)));
  });
  origin=`http://127.0.0.1:${port}`;
});
test.afterAll(async () => {
  if(fixture && fixture.exitCode===null) {
    const exited=once(fixture,'exit');fixture.kill();await exited;
  }
});

test('Browser form retains its origin and completes mandatory first change',async({page,context})=>{
  let observedOrigin;
  page.on('request',request=>{if(request.url().endsWith('/acceso/entrar'))observedOrigin=request.headers().origin;});
  await page.goto(origin+'/acceso/');
  await expect(page.getByText('Votación Centro de Padres IAC',{exact:true})).toBeVisible();
  await page.getByLabel('Correo',{exact:true}).fill('member@example.invalid');
  await page.getByLabel('Contraseña',{exact:true}).fill('Synthetic-Initial-2026');
  await page.getByRole('button',{name:'Ingresar',exact:true}).click();
  await expect(page).toHaveURL(origin+'/acceso/cambiar-clave');
  expect(observedOrigin).toBe(origin);
  await expect(page.getByRole('link',{name:'Abrir mi función',exact:true})).toHaveCount(0);
  await page.getByLabel('Nueva contraseña',{exact:true}).fill('Synthetic-Replacement-2026');
  await page.getByLabel('Confirmación',{exact:true}).fill('Synthetic-Replacement-2026');
  await page.getByRole('button',{name:'Guardar y continuar',exact:true}).click();
  await expect(page).toHaveURL(origin+'/acceso/panel');
  await expect(page.getByRole('link',{name:'Abrir mi función',exact:true})).toBeVisible();
  const session=(await context.cookies()).find(cookie=>cookie.name==='__Host-theogen_pilot');
  expect(session?.secure).toBe(true);expect(session?.httpOnly).toBe(true);
  await page.getByRole('button',{name:'Cerrar sesión',exact:true}).click();
  await page.getByLabel('Correo',{exact:true}).fill('member@example.invalid');
  await page.getByLabel('Contraseña',{exact:true}).fill('Synthetic-Initial-2026');
  await page.getByRole('button',{name:'Ingresar',exact:true}).click();
  await expect(page.getByText('No se completó la operación',{exact:true})).toBeVisible();
});

test('IAC identity preserves ballot controls and raw cryptographic data',async({page})=>{
  await page.setContent('<title>Belenios</title><div id="brand">Belenios</div><label>Belenios candidate<input value="Belenios raw credential"></label><pre id="archive">Belenios raw archive</pre><script type="application/json" id="crypto">{"protocol":"Belenios"}</script>');
  await page.addScriptTag({path:fileURLToPath(new URL('../../deploy/pilot-access/iac.js',import.meta.url))});
  await expect(page.locator('#iac-identity')).toBeVisible();
  await expect(page).toHaveTitle('Votación Centro de Padres IAC');
  await expect(page.locator('#brand')).toHaveText('plataforma de votación');
  await expect(page.locator('label')).toHaveText('Belenios candidate');
  await expect(page.locator('input')).toHaveValue('Belenios raw credential');
  await expect(page.locator('#archive')).toHaveText('Belenios raw archive');
  expect(await page.locator('#crypto').textContent()).toBe('{"protocol":"Belenios"}');
  await page.evaluate(()=>{document.body.innerHTML='<h1>Belenios</h1>';});
  await expect(page.locator('#iac-identity')).toHaveCount(1);
  await expect(page.locator('h1')).toHaveText('plataforma de votación');
});

test('IAC identity preserves visible URLs and their link and form destinations',async({page})=>{
  const urls = [
    'https://theogen-belenios-pilot.example.invalid/election#SyntheticElection',
    'http://belenios.example.invalid/election?lang=es&return=%2Ftrustee#SyntheticElection',
    '//theogen-belenios-pilot.example.invalid/election#SyntheticElection',
    '/belenios/election#SyntheticElection',
    './belenios/election#SyntheticElection',
    '../belenios/election#SyntheticElection',
    'belenios.example.invalid/election#SyntheticElection',
    'mailto:support@belenios.example.invalid',
    'urn:belenios:synthetic-election',
    'Belenios: https://belenios.example.invalid/election#SyntheticElection',
  ];
  await page.setContent('<title>Belenios</title><h1 id="brand">Belenios</h1><main id="references"></main>');
  await page.evaluate(values=>{
    const container=document.getElementById('references');
    values.forEach((value,index)=>{
      const node=document.createElement('div');node.id=`reference-${index}`;node.textContent=value;container.append(node);
    });
    const link=document.createElement('a');link.id='native-link';link.setAttribute('href',values[0]);link.textContent=values[0];container.append(link);
    const form=document.createElement('form');form.id='native-form';form.setAttribute('action',values[1]);container.append(form);
  },urls);
  await page.addScriptTag({path:fileURLToPath(new URL('../../deploy/pilot-access/iac.js',import.meta.url))});
  await expect(page.locator('#brand')).toHaveText('plataforma de votación');
  for (const [index,value] of urls.entries()) expect(await page.locator(`#reference-${index}`).textContent()).toBe(value);
  expect(await page.locator('#native-link').textContent()).toBe(urls[0]);
  await expect(page.locator('#native-link')).toHaveAttribute('href',urls[0]);
  await expect(page.locator('#native-form')).toHaveAttribute('action',urls[1]);
});

test('IAC identity preserves visible URLs after asynchronous native rendering',async({page})=>{
  const url='https://theogen-belenios-pilot.example.invalid/trustee#synthetic-capability';
  await page.setContent('<title>Belenios</title><main id="native"></main>');
  await page.addScriptTag({path:fileURLToPath(new URL('../../deploy/pilot-access/iac.js',import.meta.url))});
  await page.evaluate(value=>{
    const container=document.getElementById('native');
    const heading=document.createElement('h1');heading.id='dynamic-brand';heading.textContent='Belenios';
    const reference=document.createElement('div');reference.id='dynamic-url';reference.textContent=value;
    container.append(heading,reference);
  },url);
  // Wait for branding to prove the observer ran before comparing the URL bytes.
  await expect(page.locator('#dynamic-brand')).toHaveText('plataforma de votación');
  expect(await page.locator('#dynamic-url').textContent()).toBe(url);
  await page.evaluate(value=>{document.getElementById('dynamic-url').textContent=value;document.getElementById('dynamic-brand').textContent='Belenios';},url+'?round=2');
  await expect(page.locator('#dynamic-brand')).toHaveText('plataforma de votación');
  expect(await page.locator('#dynamic-url').textContent()).toBe(url+'?round=2');
  await expect(page.locator('#iac-identity')).toHaveCount(1);
});
