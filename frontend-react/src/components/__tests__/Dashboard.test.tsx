import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { Dashboard } from '../Dashboard';

// Mock fetch
global.fetch = vi.fn();

// Mock ResizeObserver for Recharts
global.ResizeObserver = vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
}));

describe('Dashboard Component', () => {
    const mockData = {
        training: {
            total_examples: 150,
            sources: { whatsapp: 100, twitter: 50 },
            recent_activity: []
        },
        personality: {
            facts_count: 20,
            quirks_count: 5,
            emoji_count: 30,
            avg_message_length: 42,
            tone_markers: {},
            common_phrases: ["To be fair", "Actually"],
            top_emojis: { "😂": 10, "👍": 5 }
        },
        learning_progress: {
            personality_score: 75,
            data_sources_count: 2
        }
    };

    beforeEach(() => {
        vi.clearAllMocks();
        (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
            json: () => Promise.resolve(mockData),
        });
    });

    it('renders loading state initially', () => {
        // Prevent immediate resolution
        (global.fetch as ReturnType<typeof vi.fn>).mockImplementationOnce(() => new Promise(() => { }));

        render(<Dashboard />);
        expect(screen.getByText(/Loading analytics/i)).toBeInTheDocument();
    });

    it('renders dashboard with data', async () => {
        render(<Dashboard />);

        await waitFor(() => {
            expect(screen.getByText('Analytics Dashboard')).toBeInTheDocument();
        });

        // Check stat cards
        expect(screen.getByText('150')).toBeInTheDocument(); // Training examples
        expect(screen.getByText('20')).toBeInTheDocument(); // Facts
        expect(screen.getByText('5')).toBeInTheDocument(); // Quirks

        // Check charts/text
        expect(screen.getByText('Personality Completion')).toBeInTheDocument();
        expect(screen.getByText('"To be fair"')).toBeInTheDocument();
    });

    it('handles fetch error gracefully', async () => {
        (global.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('Network error'));

        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => { });

        render(<Dashboard />);

        await waitFor(() => {
            // Should still render (with empty or zero data) but not crash
            // Based on implementation, it might show 0s
            expect(screen.queryByText(/Loading analytics/i)).not.toBeInTheDocument();
        });

        expect(consoleSpy).toHaveBeenCalledWith(expect.stringContaining('Failed to fetch'), expect.any(Error));
        consoleSpy.mockRestore();
    });

    it('renders empty states when data is missing', async () => {
        const emptyData = {
            training: { total_examples: 0, sources: [], recent_activity: [] },
            personality: {
                facts_count: 0, quirks_count: 0, emoji_count: 0,
                avg_message_length: 0, tone_markers: {},
                common_phrases: [], top_emojis: {}
            },
            learning_progress: { personality_score: 0, data_sources_count: 0 }
        };

        (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
            json: () => Promise.resolve(emptyData),
        });

        render(<Dashboard />);

        await waitFor(() => {
            expect(screen.getByText('No phrases detected yet. Chat or upload more data!')).toBeInTheDocument();
            expect(screen.getByText('No emoji patterns detected yet')).toBeInTheDocument();
        });
    });
});
