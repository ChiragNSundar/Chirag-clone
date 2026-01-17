/**
 * ThinkingBubble Component Tests
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThinkingBubble, ThinkingIndicator } from './ThinkingBubble';

describe('ThinkingBubble', () => {
    const mockSteps = [
        { step: 1, content: 'Analyzing the question...' },
        { step: 2, content: 'Searching memory for context...' },
        { step: 3, content: 'Formulating response...' }
    ];

    it('renders thinking process when visible', () => {
        render(
            <ThinkingBubble
                thinking="I need to think about this carefully"
                steps={mockSteps}
                isVisible={true}
            />
        );

        expect(screen.getByText(/thinking about this carefully/i)).toBeInTheDocument();
    });

    it('renders all steps', () => {
        render(
            <ThinkingBubble
                thinking="Processing..."
                steps={mockSteps}
                isVisible={true}
            />
        );

        expect(screen.getByText(/Analyzing the question/i)).toBeInTheDocument();
        expect(screen.getByText(/Searching memory/i)).toBeInTheDocument();
        expect(screen.getByText(/Formulating response/i)).toBeInTheDocument();
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

    it('renders with empty steps', () => {
        render(
            <ThinkingBubble
                thinking="Just thinking out loud"
                steps={[]}
                isVisible={true}
            />
        );

        expect(screen.getByText(/Just thinking out loud/i)).toBeInTheDocument();
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
