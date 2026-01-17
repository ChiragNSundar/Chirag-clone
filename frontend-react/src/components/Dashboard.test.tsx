/**
 * Dashboard.test.tsx - Tests for Dashboard component
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { Dashboard } from './Dashboard';

// Mock the fetch API
const mockAnalyticsData = {
    training: {
        total_examples: 150,
        sources: {
            whatsapp: 80,
            discord: 50,
            manual: 20
        },
        recent_activity: []
    },
    personality: {
        facts_count: 25,
        quirks_count: 12,
        emoji_count: 8,
        avg_message_length: 45,
        tone_markers: { casual: 0.7, sarcastic: 0.3 },
        common_phrases: ['honestly', 'tbh', 'lowkey'],
        top_emojis: { '😂': 15, '🔥': 10, '👀': 8 }
    },
    learning_progress: {
        personality_score: 65,
        data_sources_count: 3
    }
};

describe('Dashboard', () => {
    beforeEach(() => {
        vi.resetAllMocks();
    });

    it('shows loading state initially', () => {
        // Mock fetch to never resolve (stay loading)
        global.fetch = vi.fn().mockImplementation(() => new Promise(() => { }));

        render(<Dashboard />);

        expect(screen.getByText(/loading analytics/i)).toBeInTheDocument();
    });

    it('renders analytics data after loading', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            json: () => Promise.resolve(mockAnalyticsData)
        });

        render(<Dashboard />);

        await waitFor(() => {
            expect(screen.getByText('Analytics Dashboard')).toBeInTheDocument();
        });

        // Check stat cards are rendered
        expect(screen.getByText('Training Examples')).toBeInTheDocument();
        expect(screen.getByText('150')).toBeInTheDocument();
        expect(screen.getByText('Personal Facts')).toBeInTheDocument();
        expect(screen.getByText('25')).toBeInTheDocument();
    });

    it('displays personality completion percentage', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            json: () => Promise.resolve(mockAnalyticsData)
        });

        render(<Dashboard />);

        await waitFor(() => {
            expect(screen.getByText('65%')).toBeInTheDocument();
        });
    });

    it('shows common phrases', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            json: () => Promise.resolve(mockAnalyticsData)
        });

        render(<Dashboard />);

        await waitFor(() => {
            expect(screen.getByText('"honestly"')).toBeInTheDocument();
            expect(screen.getByText('"tbh"')).toBeInTheDocument();
        });
    });

    it('handles fetch error gracefully', async () => {
        global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

        render(<Dashboard />);

        // Should show loading initially, then handle error (component still renders)
        await waitFor(() => {
            // The Dashboard component logs the error but still renders with null data
            expect(screen.queryByText(/loading analytics/i)).not.toBeInTheDocument();
        });
    });
});
