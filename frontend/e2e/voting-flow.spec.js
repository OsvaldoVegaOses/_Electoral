import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const fixtures = JSON.parse(readFileSync(process.env.S3_E2E_FIXTURES_FILE || '../.runtime/e2e-fixtures.json', 'utf8'));

async function admin(request) {
  const login = await request.post('/api/auth/login', { data: {
    email: process.env.E2E_ADMIN_EMAIL, password: process.env.E2E_ADMIN_PASSWORD,
  } });
  expect(login.status()).toBe(200);
  return { 'X-CSRF-Token': (await login.json()).csrf_token };
}

test.describe('E2E: Flujo de Votación Pública y Comprobante Digital', () => {

  test('01. Navegación a la Sala de Votación y estado inicial', async ({ page }) => {
    await page.goto('/votar');

    // Verificar título institucional y componentes de votación
    await expect(page).toHaveTitle(/TheoGen Electoral|Votación/i);
    await expect(page.getByRole('textbox').first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Ingresar' })).toBeVisible();
  });

  test('02. Rechazo de token inválido o malformado', async ({ page }) => {
    await page.goto('/votar');

    const tokenInput = page.getByRole('textbox').first();
    await tokenInput.fill('token-completamente-invalido-000');
    
    const validateBtn = page.getByRole('button', { name: 'Ingresar' });
    await validateBtn.click();

    // Debe mostrar alerta de rechazo
    await expect(page.getByRole('alert')).toContainText('no reconocido');
  });

  test('03. Sanitización de URL si se ingresa con token en query string', async ({ page }) => {
    // Si un elector ingresa a /votar?token=demo-token, el frontend debe limpiar la barra de direcciones inmediatamente
    await page.goto('/votar?token=3a8f803d-0ccb-48b7-89f7-d92aa4c729de');

    // Esperar a que la URL se limpie para no exponer la credencial en historial
    await page.waitForTimeout(500);
    expect(page.url()).not.toContain('?token=');
  });

  test('04. Voto familiar, rechazo del segundo integrante, cierre y PDF con PostgreSQL real', async ({ page, request }) => {
    const headers = await admin(request);
    expect((await request.post(`/api/elections/${fixtures.election_id}/abrir`, { headers })).status()).toBe(200);
    await page.goto('/votar');

    // Token demo del seed
    const tokenInput = page.getByRole('textbox').first();
    await tokenInput.fill(fixtures.tokens[0]);

    const validateBtn = page.getByRole('button', { name: 'Ingresar' });
    await validateBtn.click();

    // Si el proceso demo está activo, se despliega la cédula de votación
    // o el mensaje informativo correspondiente
    await expect(page.getByRole('heading', { name: 'Seleccione su Preferencia' })).toBeVisible();
    await page.getByRole('heading', { name: 'S3 Lista A', exact: true }).click();
    await page.getByRole('button', { name: 'Continuar y Confirmar Voto' }).click();
    await page.getByRole('button', { name: 'Sí, Confirmar y Emitir' }).click();
    await expect(page.getByRole('heading', { name: '¡Sufragio Registrado Exitosamente!' })).toBeVisible();
    const duplicate = await request.post('/api/voting/submit', { data: { token: fixtures.tokens[1], candidate_id: fixtures.candidate_id } });
    // The first vote revokes the other member's credential before lookup.
    expect(duplicate.status()).toBe(400);
    expect((await duplicate.json()).detail).toBe('Token de votación inválido');
    expect((await request.post(`/api/elections/${fixtures.election_id}/cerrar`, { headers })).status()).toBe(200);
    const scrutiny = await request.get(`/api/reports/election/${fixtures.election_id}/scrutiny`);
    expect(scrutiny.status()).toBe(200);
    expect((await scrutiny.json()).participacion_porcentaje).toBe(50);
    const pdf = await request.get(`/api/reports/election/${fixtures.election_id}/acta-cierre/pdf`);
    expect(pdf.status()).toBe(200);
    expect((await pdf.body()).subarray(0, 4).toString()).toBe('%PDF');
  });

});
