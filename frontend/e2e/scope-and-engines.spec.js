import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const fixtures = JSON.parse(readFileSync(process.env.S3_E2E_FIXTURES_FILE || '../.runtime/e2e-fixtures.json', 'utf8'));

test('comisión asignada, sin asignación y CSRF por HTTP real', async ({ request }) => {
  const login = await request.post('/api/auth/login', { data: {
    email: fixtures.commission_email, password: process.env.E2E_ADMIN_PASSWORD,
  } });
  expect(login.status()).toBe(200);
  const session = await login.json();
  expect((await request.get(`/api/elections/${fixtures.other_election_id}/belenios`)).status()).toBe(403);
  expect((await request.post(`/api/elections/${fixtures.election_id}/cerrar`, {
    headers: { Authorization: `Bearer ${session.access_token}` },
  })).status()).toBe(403);
  expect((await request.post('/api/auth/logout', { headers: { 'X-CSRF-Token': session.csrf_token } })).status()).toBe(200);
  expect((await request.post('/api/auth/login', { data: {
    email: fixtures.unassigned_email, password: process.env.E2E_ADMIN_PASSWORD,
  } })).status()).toBe(200);
  expect((await request.get(`/api/elections/${fixtures.election_id}/belenios`)).status()).toBe(403);
});

test('padrón Belenios con función apagada y sin fallback MVP', async ({ request, page }) => {
  const login = await request.post('/api/auth/login', { data: {
    email: process.env.E2E_ADMIN_EMAIL, password: process.env.E2E_ADMIN_PASSWORD,
  } });
  expect(login.status()).toBe(200);
  const headers = { 'X-CSRF-Token': (await login.json()).csrf_token };
  const voter = await request.post(`/api/elections/${fixtures.belenios_election_id}/voters`, {
    headers, data: { nombre: 'S3 Belenios Synthetic', rut: '16.234.567-2', familia_id: 'S3-UNIT' },
  });
  expect(voter.status()).toBe(201);
  expect((await request.post(`/api/elections/${fixtures.belenios_election_id}/abrir`, { headers })).status()).toBe(409);
  await page.goto('/login');
  await page.getByLabel('Correo Electrónico').fill(process.env.E2E_ADMIN_EMAIL);
  await page.getByLabel('Contraseña').fill(process.env.E2E_ADMIN_PASSWORD);
  await page.getByRole('button', { name: 'Entrar a la Plataforma' }).click();
  await page.waitForURL('/');
  await page.goto(`/elecciones/${fixtures.belenios_election_id}`);
  await expect(page.getByTestId('belenios-panel')).toBeVisible();
  await expect(page.getByText('Las operaciones del motor están deshabilitadas.', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Preparar elección en Belenios' })).toBeDisabled();
});
