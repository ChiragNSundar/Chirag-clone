import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { VoiceChat } from '../VoiceChat';

// Mock Web API globals
const mockGetUserMedia = vi.fn();
Object.defineProperty(navigator, 'mediaDevices', {
    value: {
        getUserMedia: mockGetUserMedia
    }
});

// Mock Canvas
HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    fillRect: vi.fn(),
    clearRect: vi.fn(),
    getImageData: vi.fn(),
    putImageData: vi.fn(),
    createImageData: vi.fn(),
    setTransform: vi.fn(),
    drawImage: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    closePath: vi.fn(),
    stroke: vi.fn(),
    translate: vi.fn(),
    scale: vi.fn(),
    rotate: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    measureText: vi.fn(() => ({ width: 0 })),
    transform: vi.fn(),
    rect: vi.fn(),
    clip: vi.fn(),
})) as unknown as any;

// Mock MediaRecorder
const mockMediaRecorder = {
    start: vi.fn(),
    stop: vi.fn(),
    ondataavailable: vi.fn(),
    onstop: vi.fn(),
    state: 'inactive'
};
(global as unknown as { MediaRecorder: typeof MediaRecorder }).MediaRecorder = vi.fn(() => mockMediaRecorder) as unknown as typeof MediaRecorder;

// Mock Audio
const mockAudioPlay = vi.fn();
const mockAudioPause = vi.fn();
(global as unknown as { Audio: typeof Audio }).Audio = vi.fn(() => ({
    play: mockAudioPlay.mockResolvedValue(undefined),
    pause: mockAudioPause,
    onended: null,
    onerror: null
})) as unknown as typeof Audio;

// Mock WebSocket
const mockWebSocket = {
    send: vi.fn(),
    close: vi.fn(),
    readyState: 1, // OPEN
    onopen: null,
    onmessage: null,
    onclose: null,
    onerror: null
};
(global as unknown as { WebSocket: typeof WebSocket }).WebSocket = vi.fn(() => mockWebSocket) as unknown as typeof WebSocket;
(global as unknown as { WebSocket: { OPEN: number } }).WebSocket.OPEN = 1;

// Mock fetch
global.fetch = vi.fn();

describe('VoiceChat Component', () => {
    const mockOnTranscript = vi.fn();

    beforeEach(() => {
        vi.clearAllMocks();

        // Default fetch mock (voice status)
        (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
            json: () => Promise.resolve({ tts_enabled: true, stt_enabled: true })
        });

        // Mock stream
        mockGetUserMedia.mockResolvedValue({
            getTracks: () => [{ stop: vi.fn() }]
        });
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    describe('Rendering and Status', () => {
        it('renders control buttons', async () => {
            render(<VoiceChat onTranscript={mockOnTranscript} />);

            await waitFor(() => {
                expect(screen.getByTitle(/Start recording/i)).toBeInTheDocument();
                expect(screen.getByTitle(/Voice on/i)).toBeInTheDocument();
                expect(screen.getByTitle(/Enable live mode/i)).toBeInTheDocument();
            });
        });

        it('checks voice status on mount', async () => {
            render(<VoiceChat onTranscript={mockOnTranscript} />);
            expect(global.fetch).toHaveBeenCalledWith('/api/voice/status');
        });

        it('disables controls if status fetch fails', async () => {
            (global.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('Failed'));

            render(<VoiceChat onTranscript={mockOnTranscript} />);

            await waitFor(() => {
                const micButton = screen.getByTitle(/STT not available/i);
                expect(micButton).toBeDisabled();
            });
        });
    });

    describe('Recording Logic', () => {
        it('starts recording on click', async () => {
            render(<VoiceChat onTranscript={mockOnTranscript} />);

            await waitFor(() => {
                expect(screen.getByTitle(/Start recording/i)).toBeEnabled();
            });

            fireEvent.click(screen.getByTitle(/Start recording/i));

            await waitFor(() => {
                expect(mockGetUserMedia).toHaveBeenCalled();
                expect(mockMediaRecorder.start).toHaveBeenCalled();
            });

            // Check button state change
            expect(screen.getByTitle(/Stop recording/i)).toBeInTheDocument();
        });

        it('processes audio on stop recording', async () => {
            render(<VoiceChat onTranscript={mockOnTranscript} />);

            // Start
            await waitFor(() => expect(screen.getByTitle(/Start recording/i)).toBeEnabled());
            fireEvent.click(screen.getByTitle(/Start recording/i));
            await waitFor(() => expect(screen.getByTitle(/Stop recording/i)).toBeInTheDocument());

            // Stop
            fireEvent.click(screen.getByTitle(/Stop recording/i));

            expect(mockMediaRecorder.stop).toHaveBeenCalled();

            // Simulate media recorder ondataavailable and onstop
            // Note: In a real component tests, this might be tricky without fuller mock implementation,
            // but we're testing the function calls here.
        });
    });

    describe('Live Mode', () => {
        it('toggles live mode and connects websocket', async () => {
            render(<VoiceChat onTranscript={mockOnTranscript} />);

            await waitFor(() => expect(screen.getByTitle(/Enable live mode/i)).toBeEnabled());

            fireEvent.click(screen.getByTitle(/Enable live mode/i));

            expect(global.WebSocket).toHaveBeenCalled();
            // Should verify WS URL format
            expect(global.WebSocket).toHaveBeenCalledWith(expect.stringContaining('/api/voice/stream'));
        });
    });

    describe('TTS Output', () => {
        it('auto-speaks text when provided', async () => {
            render(<VoiceChat onTranscript={mockOnTranscript} textToSpeak="Hello world" />);

            await waitFor(() => {
                expect(global.fetch).toHaveBeenCalledWith('/api/voice/speak', expect.anything());
            });
        });

        it('does not speak if disabled', async () => {
            render(<VoiceChat onTranscript={mockOnTranscript} textToSpeak="Hello" isEnabled={false} />);
            expect(global.fetch).not.toHaveBeenCalledWith('/api/voice/speak', expect.anything());
        });
    });
});
