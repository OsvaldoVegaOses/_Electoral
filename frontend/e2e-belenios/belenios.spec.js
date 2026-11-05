import { test, expect } from '@playwright/test';

const election = { id: 1, nombre: 'Ensayo familiar Belenios', estado: 'Borrador', regla_votacion: 'Un voto por familia', tipo_votacion: 'Centro de Padres', school_id: 1, school: { nombre: 'Institución ficticia', rbd: 'SYNTHETIC' }, committee_members: [], candidates: [], total_voters: 3, voted_count: 0 };
const voters = [0, 1, 2].map(i => ({ id: i + 1, nombre: `Persona ficticia ${i}`, rut: `SYNTHETIC-${i}`, familia_id: i < 2 ? 'ficticia-1' : 'ficticia-2', estado: 'Pendiente' }));
const binding = { policy: 'R2', trustee_policy: { count: 5, threshold: 3 }, approval_ref: 'poc-review-1', uuid: 'Abc123Def456Gh', phase: 'Draft', inflight: null, total_people: 3, total_units: 2, result: null, public_url: 'http://127.0.0.1:18002/election#Abc123Def456Gh', admin_url: 'http://127.0.0.1:18002/admin#elections/Abc123Def456Gh' };

async function setup(page, state, onPrepare, roster = voters) {
  await page.route('**/*', route => {
    const url = route.request().url();
    return url.startsWith('http://127.0.0.1:5174/') || url.startsWith('data:') || url.startsWith('blob:') ? route.continue() : route.abort();
  });
  await page.route('**/api/**', async route => {
    const req = route.request(), path = new URL(req.url()).pathname;
    const respond = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (path === '/api/auth/me') return respond({ id: 1, nombre: 'Operador ficticio', rol: 'Administrador General', email: 'operador@ejemplo.test' });
    if (path === '/api/elections/1') return respond(election);
    if (path === '/api/elections/1/voters') {
      const query = new URL(req.url()).searchParams;
      const skip = Number(query.get('skip') || 0), limit = Number(query.get('limit') || 100);
      return respond(roster.slice(skip, skip + limit));
    }
    if (path === '/api/elections/1/candidates') return respond([{ id: 1, nombre: 'Lista A' }, { id: 2, nombre: 'Lista B' }]);
    if (path === '/api/elections/1/belenios') return respond(state);
    if (path === '/api/elections/1/belenios/prepare') return onPrepare(req.postDataJSON(), respond);
    throw new Error('Unexpected API request: ' + path);
  });
  await page.goto('/elecciones/1');
}

async function fill(page) {
  await page.getByRole('combobox', { name: 'Política de voto' }).click();
  await page.getByRole('option', { name: 'R2: se rechaza un segundo voto' }).click();
  await page.getByLabel('Referencia de aprobación de la comisión').fill('poc-review-1');
  await page.getByLabel('Número de custodios').fill('5');
  await page.getByLabel('Aportes necesarios para descifrar').fill('3');
  for (const [unit, person] of [[1, 0]]) {
    await page.getByRole('combobox', { name: `Representante de unidad ${unit}` }).click();
    await page.getByRole('option', { name: `Persona ficticia ${person}` }).click();
  }
  await page.getByRole('checkbox').check();
}

test('explicit policy and representatives prepare one external unit per family', async ({ page }) => {
  const state = { enabled: true, binding: null }; let posted = 0;
  await setup(page, state, async (body, respond) => {
    posted++;
    expect(body.policy).toBe('R2'); expect(body.representative_ids).toEqual([1, 3]);
    expect(body.trustee_policy).toEqual({ count: 5, threshold: 3 });
    expect(JSON.stringify(body)).not.toContain('SYNTHETIC'); expect(body.ballot_mode).toBe('mandatory_single_choice_no_blank_no_null');
    state.binding = { ...binding }; return respond(state.binding, 201);
  });
  await expect(page.getByRole('button', { name: 'Preparar elección en Belenios' })).toBeDisabled();
  await fill(page);
  await page.getByRole('button', { name: 'Preparar elección en Belenios' }).click();
  await expect(page.getByText('3 personas · 2 unidades habilitadas')).toBeVisible();
  await expect(page.getByText('Complete la ceremonia aprobada: 3 de 5 custodios.', { exact: false })).toBeVisible();
  await expect(page.getByRole('tab')).toHaveCount(0);
  expect(posted).toBe(1);
  await page.screenshot({ path: '../.runtime/belenios-bound.png', fullPage: true });
});

test('unknown outcome exposes reconciliation and no repeat action', async ({ page }) => {
  await setup(page, { enabled: true, binding: { ...binding, phase: 'UNKNOWN', inflight: 'a4a1396b-7039-4326-bf9d-8418a25a916d' } });
  await expect(page.getByText('Operación pendiente o desconocida.', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Reconciliar estado cotejado' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Preparar elección en Belenios' })).toHaveCount(0);
  await expect(page.getByRole('tab')).toHaveCount(0);
});

test('verified aggregate result distinguishes people from units and keeps legal status', async ({ page }) => {
  await setup(page, { enabled: true, binding: { ...binding, phase: 'Verified', result: { options: [{ label: 'Lista A', votes: 1 }, { label: 'Lista B', votes: 1 }], counted_ballots: 2, enabled_units: 2, participation: 1.0 } } });
  await expect(page.getByTestId('belenios-verified-result')).toBeVisible();
  await expect(page.getByText('2 votos computados de 2 unidades · 100.0 %')).toBeVisible();
  await expect(page.getByText('Expediente técnico experimental.', { exact: false })).toBeVisible();
  await expect(page.getByRole('tab')).toHaveCount(0);
  await page.screenshot({ path: '../.runtime/belenios-result.png', fullPage: true });
});

test('lost preparation response is refreshed without another POST', async ({ page }) => {
  const state = { enabled: true, binding: null }; let posted = 0;
  await setup(page, state, async (_, respond) => {
    posted++; state.binding = { ...binding, phase: 'UNKNOWN', inflight: 'a4a1396b-7039-4326-bf9d-8418a25a916d' };
    return respond({ detail: 'Resultado remoto desconocido' }, 503);
  });
  await fill(page); await page.getByRole('button', { name: 'Preparar elección en Belenios' }).click();
  await expect(page.getByText('Operación pendiente o desconocida.', { exact: false })).toBeVisible();
  expect(posted).toBe(1);
});

test('disabled integration preserves the existing election screen', async ({ page }) => {
  await setup(page, { enabled: false, binding: null });
  await expect(page.getByTestId('belenios-panel')).toHaveCount(0);
  await expect(page.getByRole('tab').first()).toBeVisible();
});

test('custody is explicit and invalid thresholds cannot prepare an election', async ({ page }) => {
  let posted = 0;
  await setup(page, { enabled: true, binding: null }, () => { posted++; });
  await expect(page.getByLabel('Número de custodios')).toHaveValue('');
  await expect(page.getByLabel('Aportes necesarios para descifrar')).toHaveValue('');
  await fill(page);
  const prepare = page.getByRole('button', { name: 'Preparar elección en Belenios' });
  await expect(prepare).toBeEnabled();
  for (const threshold of ['5', '1', '2.5', '']) {
    await page.getByLabel('Aportes necesarios para descifrar').fill(threshold);
    await expect(prepare).toBeDisabled();
  }
  expect(posted).toBe(0);
});

test('a legacy binding cannot validate with an inferred custody policy', async ({ page }) => {
  await setup(page, { enabled: true, binding: { ...binding, trustee_policy: null } });
  await expect(page.getByText('Esta vinculación no tiene política de custodia registrada', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Validar preparación externa' })).toBeDisabled();
});

test('1000 family representatives are read across pages and prepared once', async ({ page }) => {
  const roster = Array.from({ length: 1000 }, (_, i) => ({ id: i + 1, nombre: `Persona ficticia ${i}`, familia_id: `F-${i}`, estado: 'Pendiente' }));
  const state = { enabled: true, max_units: 1000, binding: null };
  const pages = []; let posted = 0;
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.pathname === '/api/elections/1/voters') pages.push(Number(url.searchParams.get('skip') || 0));
  });
  await setup(page, state, async (body, respond) => {
    posted++;
    expect(body.representative_ids).toEqual(Array.from({ length: 1000 }, (_, i) => i + 1));
    expect(body.trustee_policy).toEqual({ count: 5, threshold: 3 });
    state.binding = { ...binding, total_people: 1000, total_units: 1000 };
    return respond(state.binding, 201);
  }, roster);
  await expect(page.getByText('1000 unidades tienen un solo integrante', { exact: false })).toBeVisible();
  expect(pages).toEqual([0, 500, 1000]);
  await page.getByRole('combobox', { name: 'Política de voto' }).click();
  await page.getByRole('option', { name: 'R2: se rechaza un segundo voto' }).click();
  await page.getByLabel('Referencia de aprobación de la comisión').fill('synthetic-capacity-1000');
  await page.getByLabel('Número de custodios').fill('5');
  await page.getByLabel('Aportes necesarios para descifrar').fill('3');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Preparar elección en Belenios' }).click();
  await expect(page.getByText('1000 personas · 1000 unidades habilitadas')).toBeVisible();
  expect(posted).toBe(1);
});
