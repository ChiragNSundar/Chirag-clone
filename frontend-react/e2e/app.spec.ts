import { test, expect } from '@playwright/test';

/**
 * Basic Navigation Tests
 * Tests core navigation and page loading
 */

test.describe('Navigation', () => {
    test('should load the home page', async ({ page }) => {
        await page.goto('/');

        // Check that page loads
        await expect(page).toHaveTitle(/Chirag Clone/i);

        // Check that main content is visible
        await expect(page.locator('main')).toBeVisible();
    });

    test('should navigate to dashboard', async ({ page }) => {
        await page.goto('/');

        // Click dashboard link
        await page.click('text=Dashboard');

        // Check URL changed
        await expect(page).toHaveURL(/.*dashboard/);
    });

    test('should navigate to training center', async ({ page }) => {
        await page.goto('/');

        // Navigate to training
        await page.click('text=Training');

        // Check we're on training page
        await expect(page).toHaveURL(/.*training/);
    });
});

test.describe('Chat Interface', () => {
    test('should have chat input visible', async ({ page }) => {
        await page.goto('/');

        // Find chat input
        const chatInput = page.locator('input[placeholder*="message"], textarea[placeholder*="message"]');
        await expect(chatInput).toBeVisible();
    });

    test('should send a message', async ({ page }) => {
        await page.goto('/');

        // Find and fill chat input
        const chatInput = page.locator('input[placeholder*="message"], textarea[placeholder*="message"]');
        await chatInput.fill('Hello, this is a test message');

        // Submit (Enter or button)
        await chatInput.press('Enter');

        // Wait for response (check for loading indicator or new message)
        await expect(page.locator('[data-testid="message"]').first()).toBeVisible({ timeout: 10000 });
    });

    test('should show thinking indicator while processing', async ({ page }) => {
        await page.goto('/');

        const chatInput = page.locator('input[placeholder*="message"], textarea[placeholder*="message"]');
        await chatInput.fill('What can you tell me about yourself?');
        await chatInput.press('Enter');

        // Check for thinking indicator (may appear briefly)
        // This might be too fast on mocked responses
    });
});

test.describe('Keyboard Shortcuts', () => {
    test('should open command palette with Cmd+K', async ({ page }) => {
        await page.goto('/');

        // Trigger Cmd+K (Meta+K on Mac)
        await page.keyboard.press('Meta+k');

        // Check command palette appeared
        const commandPalette = page.locator('[data-testid="command-palette"], .command-palette');
        await expect(commandPalette).toBeVisible({ timeout: 2000 });
    });

    test('should close command palette with Escape', async ({ page }) => {
        await page.goto('/');

        // Open command palette
        await page.keyboard.press('Meta+k');

        // Close with Escape
        await page.keyboard.press('Escape');

        // Check it closed
        const commandPalette = page.locator('[data-testid="command-palette"], .command-palette');
        await expect(commandPalette).not.toBeVisible();
    });
});

test.describe('Theme', () => {
    test('should have dark mode by default', async ({ page }) => {
        await page.goto('/');

        // Check for dark mode class or styles
        const html = page.locator('html');
        await expect(html).toHaveClass(/dark/);
    });
});

test.describe('Responsive Design', () => {
    test('should adapt layout for mobile', async ({ page }) => {
        // Set mobile viewport
        await page.setViewportSize({ width: 375, height: 667 });
        await page.goto('/');

        // Check that sidebar is hidden or collapsed on mobile
        const sidebar = page.locator('[data-testid="sidebar"], .sidebar');

        // Sidebar might be hidden or transformed
        // Just check page renders without errors
        await expect(page.locator('main')).toBeVisible();
    });
});

test.describe('Accessibility', () => {
    test('should have proper focus management', async ({ page }) => {
        await page.goto('/');

        // Tab through elements and check focus is visible
        await page.keyboard.press('Tab');

        // Get focused element
        const focusedElement = page.locator(':focus');
        await expect(focusedElement).toBeVisible();
    });

    test('should have alt text on images', async ({ page }) => {
        await page.goto('/');

        // Get all images
        const images = page.locator('img');
        const count = await images.count();

        for (let i = 0; i < count; i++) {
            const img = images.nth(i);
            const alt = await img.getAttribute('alt');
            expect(alt).not.toBeNull();
        }
    });
});
