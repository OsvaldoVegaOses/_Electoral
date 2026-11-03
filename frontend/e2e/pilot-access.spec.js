import { test, expect } from '@playwright/test';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';

const origin='https://pilot.example.invalid';
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
});
test.afterAll(async () => {
  if(fixture && fixture.exitCode===null) {
    const exited=once(fixture,'exit');fixture.kill();await exited;
  }
});

test('Browser form retains its origin and completes mandatory first change',async({page,context})=>{
  let observedOrigin;
  await context.route(origin+'/**',async route=>{
    const request=route.request();
    if(request.url().endsWith('/acceso/entrar'))observedOrigin=request.headers().origin;
    const upstream=await route.fetch({url:`http://127.0.0.1:${port}${new URL(request.url()).pathname}`,maxRedirects:0});
    await route.fulfill({response:upstream});
  });
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
