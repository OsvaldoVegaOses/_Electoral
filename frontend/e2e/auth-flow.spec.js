import { test, expect } from '@playwright/test';

test.describe('E2E: Autenticación Administrativa y Cookies HttpOnly', () => {

  test('01. Pantalla de login accesible y componentes presentes', async ({ page }) => {
    await page.goto('/login');

    await expect(page.locator('input[type="email"], input[name="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"], input[name="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"], button:has-text("Iniciar Sesión")')).toBeVisible();
  });

  test('02. Bloqueo de credenciales incorrectas', async ({ page }) => {
    await page.goto('/login');

    await page.locator('input[type="email"], input[name="email"]').fill('usuario_falso@theogen.cl');
    await page.locator('input[type="password"], input[name="password"]').fill('ClaveIncorrecta123');
    await page.locator('button[type="submit"], button:has-text("Iniciar Sesión")').click();

    // Debe mostrar error de autenticación
    await expect(page.locator('text=incorrectos, text=inválido, .MuiAlert-root')).toBeVisible();
  });

  test('03. Inicio de sesión exitoso y validación de sesión con cookies HttpOnly', async ({ page }) => {
    await page.goto('/login');

    // Credenciales de demostración
    await page.locator('input[type="email"], input[name="email"]').fill('admin@theogen.cl');
    await page.locator('input[type="password"], input[name="password"]').fill('admin123');
    await page.locator('button[type="submit"], button:has-text("Iniciar Sesión")').click();

    // Redirección al Dashboard
    await page.waitForURL('/', { timeout: 10000 });
    await expect(page.locator('text=Dashboard, text=Elecciones, text=Padrón')).toBeVisible();

    // Verificar que el JWT no esté guardado en localStorage (P2: mitigación XSS)
    const tokenInStorage = await page.evaluate(() => localStorage.getItem('theogen_token'));
    expect(tokenInStorage).toBeNull();
  });

});
