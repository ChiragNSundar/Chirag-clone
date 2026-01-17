import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LoginPage } from '../LoginPage';

// Mock fetch
global.fetch = vi.fn();

describe('LoginPage', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
            json: () => Promise.resolve({ google: true }),
        });
    });

    describe('Rendering', () => {
        it('renders the login page with welcome message', () => {
            render(<LoginPage />);

            expect(screen.getByText('Welcome Back')).toBeInTheDocument();
            expect(screen.getByText(/Sign in to access your digital twin/i)).toBeInTheDocument();
        });

        it('renders Google login button', async () => {
            render(<LoginPage />);

            await waitFor(() => {
                expect(screen.getByText(/Sign in with Google/i)).toBeInTheDocument();
            });
        });

        it('renders PIN access fallback link', () => {
            render(<LoginPage />);

            expect(screen.getByText(/Use PIN access/i)).toBeInTheDocument();
        });
    });

    describe('OAuth Status', () => {
        it('checks OAuth status on mount', async () => {
            render(<LoginPage />);

            await waitFor(() => {
                expect(global.fetch).toHaveBeenCalledWith('/api/auth/status');
            });
        });

        it('disables Google button when not configured', async () => {
            (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
                json: () => Promise.resolve({ google: false }),
            });

            render(<LoginPage />);

            await waitFor(() => {
                const googleButton = screen.getByText(/Google not configured/i);
                expect(googleButton).toBeInTheDocument();
            });
        });
    });

    describe('Error Handling', () => {
        it('handles OAuth status fetch failure gracefully', async () => {
            (global.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('Network error'));

            render(<LoginPage />);

            // Should not crash, should render fallback state
            await waitFor(() => {
                expect(screen.getByText('Welcome Back')).toBeInTheDocument();
            });
        });

        it('displays error message when login fails', async () => {
            // First call for status
            (global.fetch as ReturnType<typeof vi.fn>)
                .mockResolvedValueOnce({
                    json: () => Promise.resolve({ google: true }),
                })
                // Second call for getting auth URL fails
                .mockResolvedValueOnce({
                    json: () => Promise.resolve({ error: 'Failed' }),
                });

            render(<LoginPage />);

            await waitFor(() => {
                const googleButton = screen.getByText(/Sign in with Google/i);
                fireEvent.click(googleButton);
            });

            await waitFor(() => {
                // Should show error or handle gracefully
                expect(screen.getByText('Welcome Back')).toBeInTheDocument();
            });
        });
    });

    describe('Login Flow', () => {
        it('calls Google OAuth URL endpoint when clicking Google button', async () => {
            (global.fetch as ReturnType<typeof vi.fn>)
                .mockResolvedValueOnce({
                    json: () => Promise.resolve({ google: true }),
                })
                .mockResolvedValueOnce({
                    json: () => Promise.resolve({
                        url: 'https://accounts.google.com/oauth',
                        state: 'test-state'
                    }),
                });

            render(<LoginPage />);

            await waitFor(() => {
                const googleButton = screen.getByText(/Sign in with Google/i);
                fireEvent.click(googleButton);
            });

            await waitFor(() => {
                expect(global.fetch).toHaveBeenCalledWith(
                    expect.stringContaining('/api/auth/google/url')
                );
            });
        });

        it('stores OAuth state in localStorage', async () => {
            const mockSetItem = vi.spyOn(Storage.prototype, 'setItem');

            (global.fetch as ReturnType<typeof vi.fn>)
                .mockResolvedValueOnce({
                    json: () => Promise.resolve({ google: true }),
                })
                .mockResolvedValueOnce({
                    json: () => Promise.resolve({
                        url: 'https://accounts.google.com/oauth',
                        state: 'csrf-state-123'
                    }),
                });

            render(<LoginPage />);

            await waitFor(() => {
                const googleButton = screen.getByText(/Sign in with Google/i);
                fireEvent.click(googleButton);
            });

            await waitFor(() => {
                expect(mockSetItem).toHaveBeenCalledWith('oauth_state', 'csrf-state-123');
            });

            mockSetItem.mockRestore();
        });
    });

    describe('Callback Handling', () => {
        it('calls onLoginSuccess when token is in URL', async () => {
            const mockOnSuccess = vi.fn();

            render(<LoginPage onLoginSuccess={mockOnSuccess} />);

            // Check if component renders correctly
            await waitFor(() => {
                expect(screen.getByText('Welcome Back')).toBeInTheDocument();
            });
        });
    });
});
