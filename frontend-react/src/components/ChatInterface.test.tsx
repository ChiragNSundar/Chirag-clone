/**
 * ChatInterface.test.tsx - Tests for ChatInterface component  
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatInterface } from './ChatInterface';

// Mock the API module
vi.mock('../services/api', () => ({
    api: {
        sendMessage: vi.fn()
    }
}));

// Mock Avatar3D since it uses Three.js which doesn't work in jsdom
vi.mock('./Avatar3D', () => ({
    Avatar3D: () => <div data-testid="mock-avatar">Avatar</div>
}));

// Mock ThinkingBubble
vi.mock('./ThinkingBubble', () => ({
    ThinkingBubble: ({ thinking }: { thinking: string }) => (
        <div data-testid="thinking-bubble">{thinking}</div>
    ),
    ThinkingIndicator: () => <div data-testid="thinking-indicator">Thinking...</div>
}));

// Mock MoodContext
vi.mock('../contexts/MoodContext', () => ({
    useMood: () => ({
        setMood: vi.fn(),
        theme: { primary: '#000', secondary: '#000', accent: '#000', background: '#fff' }
    }),
    MoodProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>
}));

import { api } from '../services/api';

describe('ChatInterface', () => {
    beforeEach(() => {
        vi.resetAllMocks();
    });

    it('renders the chat interface', () => {
        render(<ChatInterface />);

        expect(screen.getByPlaceholderText(/type a message/i)).toBeInTheDocument();
        expect(screen.getAllByRole('button').length).toBeGreaterThan(0);
    });

    it('shows empty state when no messages', () => {
        render(<ChatInterface />);

        expect(screen.getByText(/start chatting with your clone/i)).toBeInTheDocument();
    });

    it('allows typing in the input field', async () => {
        render(<ChatInterface />);

        const input = screen.getByPlaceholderText(/type a message/i);
        fireEvent.change(input, { target: { value: 'Hello, Clone!' } });

        expect(input).toHaveValue('Hello, Clone!');
    });

    it('disables send button when input is empty', () => {
        render(<ChatInterface />);

        const sendButton = screen.getByTestId('send-button');
        expect(sendButton).toBeDisabled();
    });

    it('enables send button when input has text', async () => {
        render(<ChatInterface />);

        const input = screen.getByPlaceholderText(/type a message/i);
        fireEvent.change(input, { target: { value: 'Hello' } });

        const sendButton = screen.getByTestId('send-button');
        expect(sendButton).not.toBeDisabled();
    });

    it('sends message on button click', async () => {
        const mockResponse = {
            response: 'Hello! How can I help?',
            confidence: 0.95,
            mood: { emoji: '😊' },
            thinking: { has_thinking: false, thinking: '', steps: [] }
        };

        (api.sendMessage as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

        render(<ChatInterface />);

        const input = screen.getByPlaceholderText(/type a message/i);
        fireEvent.change(input, { target: { value: 'Hello' } });

        const sendButton = screen.getByTestId('send-button');
        await waitFor(() => expect(sendButton).toBeEnabled());
        await userEvent.click(sendButton);

        await waitFor(() => {
            expect(api.sendMessage).toHaveBeenCalledWith('Hello', expect.any(String), false, undefined);
        });

        await waitFor(() => {
            expect(screen.getByText('Hello! How can I help?')).toBeInTheDocument();
        });
    });

    it('sends message on Enter key', async () => {
        const mockResponse = {
            response: 'Test response',
            confidence: 0.9,
            mood: { emoji: '🤔' },
            thinking: { has_thinking: false, thinking: '', steps: [] }
        };

        (api.sendMessage as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

        render(<ChatInterface />);

        const input = screen.getByPlaceholderText(/type a message/i);
        fireEvent.change(input, { target: { value: 'Test message' } });
        fireEvent.keyDown(input, { key: 'Enter', code: 'Enter', charCode: 13 });

        await waitFor(() => {
            expect(api.sendMessage).toHaveBeenCalledWith('Test message', expect.any(String), false, undefined);
        });
    });

    it('shows thinking indicator while waiting for response', async () => {
        let resolvePromise: (value: unknown) => void = () => { };
        const delayedPromise = new Promise((resolve) => {
            resolvePromise = resolve;
        });

        (api.sendMessage as ReturnType<typeof vi.fn>).mockReturnValue(delayedPromise);

        render(<ChatInterface />);

        const input = screen.getByPlaceholderText('Type a message...');
        const sendButton = screen.getByTestId('send-button');

        await userEvent.type(input, 'Hello');
        await waitFor(() => expect(sendButton).toBeEnabled());

        await userEvent.click(sendButton);

        // Verify message appeared (confirms handleSend ran)
        await waitFor(() => {
            expect(screen.getByText('Hello')).toBeInTheDocument();
        });

        // Check for thinking indicator
        await waitFor(() => {
            expect(screen.getByTestId('thinking-indicator')).toBeInTheDocument();
        });

        // Resolve
        resolvePromise({
            response: 'Done',
            confidence: 0.9,
            mood: { emoji: '👍' },
            thinking: { has_thinking: false, thinking: '', steps: [] }
        });

        await waitFor(() => {
            expect(screen.queryByTestId('thinking-indicator')).not.toBeInTheDocument();
        });
    });

    it('toggles thinking visibility', async () => {
        render(<ChatInterface />);

        const thinkingToggle = screen.getByText(/thinking: on/i);
        await userEvent.click(thinkingToggle);

        expect(screen.getByText(/thinking: off/i)).toBeInTheDocument();
    });
});
