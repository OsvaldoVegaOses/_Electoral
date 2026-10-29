import { test, expect } from '@playwright/test';

test.describe('E2E: Autenticación Administrativa y Cookies HttpOnly', () => {

  test('01. Pantalla de login accesible y componentes presentes', async ({ page }) => {
    await page.goto('/login');

    await expect(page.getByLabel('Correo Electrónico')).toBeVisible();
    await expect(page.getByLabel('Contraseña')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Entrar a la Plataforma' })).toBeVisible();
  });

  test('02. Bloqueo de credenciales incorrectas', async ({ page }) => {
    await page.goto('/login');

    await page.getByLabel('Correo Electrónico').fill('usuario_falso@theogen.cl');
    await page.getByLabel('Contraseña').fill('ClaveIncorrecta123');
    await page.getByRole('button', { name: 'Entrar a la Plataforma' }).click();

    // Debe mostrar error de autenticación
    await expect(page.getByRole('alert')).toContainText('incorrectos');
  });

  test('03. Inicio de sesión exitoso y validación de sesión con cookies HttpOnly', async ({ page }) => {
    await page.goto('/login');

    // Credenciales de demostración
    await page.getByLabel('Correo Electrónico').fill(process.env.E2E_ADMIN_EMAIL || 'admin@theogen.cl');
    await page.getByLabel('Contraseña').fill(process.env.E2E_ADMIN_PASSWORD || 'admin123');
    await page.getByRole('button', { name: 'Entrar a la Plataforma' }).click();

    // Redirección al Dashboard
    await page.waitForURL('/', { timeout: 10000 });
    const accountMenu = page.getByRole('button', { name: /Administrador General/ });
    await expect(accountMenu).toBeVisible();

    const cookies = await page.context().cookies();
    expect(cookies.find((cookie) => cookie.name === 'access_token')?.httpOnly).toBe(true);

    // Verificar que el JWT no esté guardado en localStorage (P2: mitigación XSS)
    const tokenInStorage = await page.evaluate(() => localStorage.getItem('theogen_token'));
    expect(tokenInStorage).toBeNull();

    await accountMenu.click();
    await page.getByRole('menuitem', { name: /Cerrar Sesión/ }).click();
    await page.waitForURL('**/login');
    await expect(page.getByRole('heading', { name: 'Iniciar Sesión' })).toBeVisible();
    const cookiesAfterLogout = await page.context().cookies();
    expect(cookiesAfterLogout.find((cookie) => cookie.name === 'access_token')).toBeUndefined();
  });

});
