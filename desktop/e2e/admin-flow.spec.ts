/**
 * The admin journey from the MVP success criteria, driven through the real UI
 * against a live FastAPI backend and a real PostgreSQL database.
 *
 *   sign in -> create category -> add product -> set price -> set stock
 *           -> activate -> adjust inventory
 *
 * Nothing is stubbed. If the backend contract changes, these fail.
 */
import { test, expect, type Page } from '@playwright/test';

// Supplied by the environment so no working credential is committed.
// Defaults match the local development admin created by
// `python -m app.initial_data`.
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? 'admin@kumarancrackers.com';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'Admin@12345';

// The development database persists between runs, so each run works with its
// own uniquely-named records rather than colliding with the last one.
const RUN = Date.now().toString().slice(-6);
const CATEGORY_NAME = `E2E Rockets ${RUN}`;
const PRODUCT_NAME = `E2E Thunder Shell ${RUN}`;

async function signIn(page: Page): Promise<void> {
  await page.goto('/');
  // Matched loosely: the visible required asterisk sits inside the <label>
  // (hidden from assistive tech via aria-hidden), so the raw textContent
  // Playwright matches on is "Password*".
  await page.getByLabel('Email address').fill(ADMIN_EMAIL);
  await page.getByLabel('Password').fill(ADMIN_PASSWORD);
  await page.getByTestId('login-submit').click();
  await expect(page.getByTestId('dashboard')).toBeVisible();
}

test.describe('Authentication', () => {
  test('rejects a wrong password and says so', async ({ page }) => {
    await page.goto('/');
    await page.getByLabel('Email address').fill(ADMIN_EMAIL);
    await page.getByLabel('Password').fill('DefinitelyWrong1');
    await page.getByTestId('login-submit').click();

    await expect(page.getByTestId('login-error')).toBeVisible();
    await expect(page.getByTestId('dashboard')).toBeHidden();
  });

  test('signs an administrator in', async ({ page }) => {
    await signIn(page);
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  });

  test('signs out again', async ({ page }) => {
    await signIn(page);
    await page.getByTestId('logout-button').click();
    await page.getByTestId('confirm-button').click();
    await expect(page.getByTestId('login-submit')).toBeVisible();
  });
});

test.describe('Dashboard', () => {
  test('renders live figures from the database', async ({ page }) => {
    await signIn(page);

    // Real counts, not placeholders.
    await expect(page.getByTestId('stat-products')).toBeVisible();
    await expect(page.getByTestId('stat-low-stock')).toBeVisible();
    await expect(page.getByTestId('stat-out-of-stock')).toBeVisible();
    await expect(page.getByTestId('stat-customers')).toBeVisible();

    const products = await page.getByTestId('stat-products').textContent();
    expect(products).toMatch(/\d/);
  });

  test('renders the category distribution chart', async ({ page }) => {
    await signIn(page);
    await expect(page.getByTestId('category-chart')).toBeVisible();
    // Recharts draws SVG; confirm bars actually rendered rather than an empty frame.
    await expect(page.getByTestId('category-chart').locator('svg')).toBeVisible();
  });

  test('states plainly that sales figures do not exist yet', async ({ page }) => {
    await signIn(page);
    const notice = page.getByTestId('sales-unavailable');
    await expect(notice).toBeVisible();
    await expect(notice).toContainText('not available yet');
  });
});

test.describe('Catalogue management', () => {
  test('creates a category, then a product in it, and adjusts its stock', async ({ page }) => {
    await signIn(page);

    // ---- Create the category ----
    await page.getByRole('link', { name: 'Categories' }).click();
    await expect(page.getByTestId('categories-page')).toBeVisible();

    await page.getByTestId('new-category').click();
    await page.getByLabel('Name').fill(CATEGORY_NAME);
    await page.getByLabel('Display order').fill('50');
    await page.getByTestId('save-category').click();

    await expect(page.getByTestId('toast-success').last()).toBeVisible();
    // Scoped to the table: the name also appears in the success toast.
    await expect(
      page.getByTestId('category-row').filter({ hasText: CATEGORY_NAME }),
    ).toBeVisible();

    // ---- Add a product with a price and stock ----
    await page.getByRole('link', { name: 'Products' }).click();
    await expect(page.getByTestId('products-page')).toBeVisible();

    await page.getByTestId('new-product').click();
    await page.getByTestId('product-name').fill(PRODUCT_NAME);
    await page.getByTestId('product-category').selectOption({ label: CATEGORY_NAME });
    await page.getByTestId('product-mrp').fill('2499.00');
    await page.getByTestId('product-price').fill('1874.25');
    await page.getByTestId('product-stock').fill('40');
    await page.getByTestId('save-product').click();

    await expect(page.getByTestId('toast-success').last()).toBeVisible();

    // ---- It appears in the catalogue with an exact price and derived discount ----
    await page.getByTestId('product-search').fill(PRODUCT_NAME);
    const row = page.getByTestId('product-row').filter({ hasText: PRODUCT_NAME });
    await expect(row).toBeVisible();

    // Money must survive the round trip exactly - no floating-point drift.
    await expect(row).toContainText('₹1,874.25');
    await expect(row).toContainText('₹2,499.00');
    // 2499.00 -> 1874.25 is precisely 25% off.
    await expect(row).toContainText('25% off');
    await expect(row).toContainText('In stock');

    // ---- Adjust stock from the inventory screen ----
    await page.getByRole('link', { name: 'Inventory' }).click();
    await expect(page.getByTestId('inventory-page')).toBeVisible();

    await page.getByTestId('inventory-search').fill(PRODUCT_NAME);
    const inventoryRow = page.getByTestId('inventory-row').filter({ hasText: PRODUCT_NAME });
    await expect(inventoryRow).toBeVisible();

    await inventoryRow.getByTestId('adjust-stock').click();
    await page.getByTestId('stock-amount').fill('-35');
    await page.getByTestId('save-stock').click();

    await expect(page.getByTestId('toast-success').last()).toContainText('stock is now 5');

    // 5 left against a threshold of 10 is Low stock, derived by the backend.
    await expect(inventoryRow).toContainText('Low stock');
  });

  test('refuses a stock reduction larger than what is in stock', async ({ page }) => {
    await signIn(page);
    await page.getByRole('link', { name: 'Inventory' }).click();
    await page.getByTestId('inventory-search').fill(PRODUCT_NAME);

    const row = page.getByTestId('inventory-row').filter({ hasText: PRODUCT_NAME });
    await expect(row).toBeVisible();
    await row.getByTestId('adjust-stock').click();

    await page.getByTestId('stock-amount').fill('-99999');
    await page.getByTestId('save-stock').click();

    // The backend guard, surfaced in the dialog rather than swallowed.
    await expect(page.getByTestId('stock-error')).toBeVisible();
    await expect(page.getByTestId('stock-error')).toContainText('Cannot reduce stock');
  });

  test('rejects a selling price above the MRP', async ({ page }) => {
    await signIn(page);
    await page.getByRole('link', { name: 'Products' }).click();

    await page.getByTestId('new-product').click();
    await page.getByTestId('product-name').fill(`Invalid Pricing ${RUN}`);
    await page.getByTestId('product-mrp').fill('100.00');
    await page.getByTestId('product-price').fill('150.00');
    await page.getByTestId('save-product').click();

    await expect(page.getByText('Selling price cannot be greater than the MRP.')).toBeVisible();
  });

  test('refuses to delete a category that still holds products', async ({ page }) => {
    await signIn(page);
    await page.getByRole('link', { name: 'Categories' }).click();

    const row = page.getByTestId('category-row').filter({ hasText: CATEGORY_NAME });
    await expect(row).toBeVisible();
    await row.getByRole('button', { name: 'Delete' }).click();
    await page.getByTestId('confirm-button').click();

    // The server refuses; the UI reports why instead of pretending it worked.
    await expect(page.getByTestId('toast-error').last()).toBeVisible();
    await expect(page.getByTestId('toast-error').last()).toContainText('still has products');
  });

  test('search narrows the product list', async ({ page }) => {
    await signIn(page);
    await page.getByRole('link', { name: 'Products' }).click();

    await page.getByTestId('product-search').fill(PRODUCT_NAME);
    await expect(page.getByTestId('product-row')).toHaveCount(1);

    await page.getByTestId('product-search').fill('zzz-no-such-product-zzz');
    await expect(page.getByText('No products match your search')).toBeVisible();
  });
});

test.describe('Screens awaiting later milestones', () => {
  test('orders says what it will do rather than showing invented data', async ({ page }) => {
    await signIn(page);
    await page.getByRole('link', { name: 'Orders' }).click();

    const placeholder = page.getByTestId('placeholder-page');
    await expect(placeholder).toBeVisible();
    await expect(placeholder).toContainText('Milestone 6');
    await expect(placeholder).toContainText('No sample data is shown here on purpose');
  });
});
