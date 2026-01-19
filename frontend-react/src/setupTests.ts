import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock scrollIntoView
window.HTMLElement.prototype.scrollIntoView = vi.fn();

// Mock scrollTo
window.scrollTo = vi.fn();

// Mock ResizeObserver
class ResizeObserver {
    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();
}

global.ResizeObserver = ResizeObserver;
window.ResizeObserver = ResizeObserver;

// Mock IntersectionObserver
class IntersectionObserver {
    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();
    root = null;
    rootMargin = '';
    thresholds = [];
}

global.IntersectionObserver = IntersectionObserver as unknown as typeof global.IntersectionObserver;
window.IntersectionObserver = IntersectionObserver as unknown as typeof window.IntersectionObserver;

// Mock AudioContext for audio visualization tests
class MockAudioContext {
    createAnalyser = vi.fn(() => ({
        fftSize: 256,
        frequencyBinCount: 128,
        smoothingTimeConstant: 0.8,
        connect: vi.fn(),
        disconnect: vi.fn(),
        getByteFrequencyData: vi.fn((array: Uint8Array) => {
            for (let i = 0; i < array.length; i++) {
                array[i] = Math.floor(Math.random() * 256);
            }
        }),
    }));
    createMediaStreamSource = vi.fn(() => ({ connect: vi.fn() }));
    createMediaElementSource = vi.fn(() => ({ connect: vi.fn() }));
    destination = {};
}

window.AudioContext = MockAudioContext as unknown as typeof AudioContext;
(window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext = MockAudioContext as unknown as typeof AudioContext;

// Mock MediaRecorder
class MockMediaRecorder {
    start = vi.fn();
    stop = vi.fn();
    ondataavailable = vi.fn();
    onstop = vi.fn();
    state = 'inactive';
    static isTypeSupported = vi.fn(() => true);
}

window.MediaRecorder = MockMediaRecorder as unknown as typeof MediaRecorder;

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation(query => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
    })),
});

// Mock navigator.mediaDevices
Object.defineProperty(navigator, 'mediaDevices', {
    writable: true,
    value: {
        getUserMedia: vi.fn().mockResolvedValue({
            getTracks: () => [{ stop: vi.fn() }],
        }),
        enumerateDevices: vi.fn().mockResolvedValue([]),
    },
});

// Mock clipboard API
Object.assign(navigator, {
    clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
        readText: vi.fn().mockResolvedValue(''),
    },
});

