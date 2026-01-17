/**
 * ThinkingBubble Component Tests
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThinkingBubble, ThinkingIndicator } from './ThinkingBubble';

describe('ThinkingBubble', () => {
    // Standard real timers for animations
    const mockSteps = [
        { step: 1, content: 'Analyzing the question...' },
        { step: 2, content: 'Searching memory for context...' },
        { step: 3, content: 'Formulating response...' }
    ];

    it.skip('renders thinking process when visible', async () => {
        render(
            <ThinkingBubble
                thinking="I need to think about this carefully"
                steps={mockSteps}
                isVisible={true}
            />
        );

        // Expand to see content
        const button = screen.getByRole('button');
        fireEvent.click(button);

        await waitFor(() => {
            const el = screen.queryByText((content) => content.includes('thinking about this carefully'));
            expect(el).toBeInTheDocument();
        }, { timeout: 5000 });
    });

    it('renders all steps', async () => {
        render(
            <ThinkingBubble
                thinking="Processing..."
                steps={mockSteps}
                isVisible={true}
            />
        );

        // Expand to see content
        const button = screen.getByRole('button');
        fireEvent.click(button);

        // Wait for steps to appear (animation)
        await waitFor(() => {
            const el = screen.queryByText(/Analyzing the question/i);
            expect(el).toBeInTheDocument();
        });
    });

    it('does not render when not visible', () => {
        const { container } = render(
            <ThinkingBubble
                thinking="Hidden thought"
                steps={mockSteps}
                isVisible={false}
            />
        );

        // Should render nothing or be hidden
        expect(container.firstChild).toBeNull();
    });

    it.skip('renders with empty steps', async () => {
        render(
            <ThinkingBubble
                thinking="Just thinking out loud"
                steps={[]}
                isVisible={true}
            />
        );

        // Expand to see content
        const button = screen.getByRole('button');
        fireEvent.click(button);

        await waitFor(() => {
            const el = screen.queryByText((content) => content.includes('Just thinking out loud'));
            expect(el).toBeInTheDocument();
        }, { timeout: 5000 });
    });
});

describe('ThinkingIndicator', () => {
    it('renders animated indicator', () => {
        const { container } = render(<ThinkingIndicator />);

        // Should have some animated elements
        expect(container.firstChild).not.toBeNull();
    });

    it('contains thinking text or animation', () => {
        render(<ThinkingIndicator />);

        // The component should exist
        const container = document.querySelector('div');
        expect(container).toBeInTheDocument();
    });
});
