import { test, expect } from '@playwright/test';

test.describe('E2E: Flujo de Votación Pública y Comprobante Digital', () => {

  test('01. Navegación a la Sala de Votación y estado inicial', async ({ page }) => {
    await page.goto('/votar');

    // Verificar título institucional y componentes de votación
    await expect(page).toHaveTitle(/TheoGen Electoral|Votación/i);
    await expect(page.locator('input[placeholder*="token" i], input[type="text"]')).toBeVisible();
    await expect(page.locator('button:has-text("Validar"), button:has-text("Ingresar")')).toBeVisible();
  });

  test('02. Rechazo de token inválido o malformado', async ({ page }) => {
    await page.goto('/votar');

    const tokenInput = page.locator('input[placeholder*="token" i], input[type="text"]');
    await tokenInput.fill('token-completamente-invalido-000');
    
    const validateBtn = page.locator('button:has-text("Validar"), button:has-text("Ingresar")');
    await validateBtn.click();

    // Debe mostrar alerta de rechazo
    await expect(page.locator('text=no reconocido, text=inválido, .MuiAlert-root')).toBeVisible();
  });

  test('03. Sanitización de URL si se ingresa con token en query string', async ({ page }) => {
    // Si un elector ingresa a /votar?token=demo-token, el frontend debe limpiar la barra de direcciones inmediatamente
    await page.goto('/votar?token=3a8f803d-0ccb-48b7-89f7-d92aa4c729de');

    // Esperar a que la URL se limpie para no exponer la credencial en historial
    await page.waitForTimeout(500);
    expect(page.url()).not.toContain('?token=');
  });

  test('04. Validación de credencial de demostración y presentación de candidatos', async ({ page }) => {
    await page.goto('/votar');

    // Token demo del seed
    const tokenInput = page.locator('input[placeholder*="token" i], input[type="text"]');
    await tokenInput.fill('3a8f803d-0ccb-48b7-89f7-d92aa4c729de');

    const validateBtn = page.locator('button:has-text("Validar"), button:has-text("Ingresar")');
    await validateBtn.click();

    // Si el proceso demo está activo, se despliega la cédula de votación
    // o el mensaje informativo correspondiente
    const electionCard = page.locator('text=Elección, text=Candidato, text=Lista, .MuiCard-root');
    await expect(electionCard.first()).toBeVisible({ timeout: 10000 });
  });

});
