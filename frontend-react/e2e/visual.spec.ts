import { test, expect } from '@playwright/test';

test('landing page visual regression', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveScreenshot('landing-page.png');
});

test('chat interface visual regression', async ({ page }) => {
    await page.goto('/');
    // Wait for chat interface to load
    await expect(page.locator('input[placeholder="Type a message..."]')).toBeVisible();

    await expect(page).toHaveScreenshot('chat-interface.png');
});
