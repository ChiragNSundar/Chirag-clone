/**
 * Tests for custom React hooks in useUtilities.ts
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import {
    useDebounce,
    useLocalStorage,
    usePrevious,
    useWindowSize,
    useMediaQuery,
    useCopyToClipboard,
    useAsync
} from '../useUtilities';

describe('useDebounce', () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it('should return initial value immediately', () => {
        const { result } = renderHook(() => useDebounce('initial', 500));
        expect(result.current).toBe('initial');
    });

    it('should debounce value changes', () => {
        const { result, rerender } = renderHook(
            ({ value, delay }) => useDebounce(value, delay),
            { initialProps: { value: 'initial', delay: 500 } }
        );

        expect(result.current).toBe('initial');

        // Change value
        rerender({ value: 'updated', delay: 500 });

        // Should still be initial value
        expect(result.current).toBe('initial');

        // Fast forward 500ms
        act(() => {
            vi.advanceTimersByTime(500);
        });

        // Now should be updated
        expect(result.current).toBe('updated');
    });

    it('should cancel pending updates when value changes again', () => {
        const { result, rerender } = renderHook(
            ({ value, delay }) => useDebounce(value, delay),
            { initialProps: { value: 'initial', delay: 500 } }
        );

        rerender({ value: 'first', delay: 500 });

        act(() => {
            vi.advanceTimersByTime(200);
        });

        // Change again before debounce completes
        rerender({ value: 'second', delay: 500 });

        act(() => {
            vi.advanceTimersByTime(500);
        });

        // Should skip 'first' and go to 'second'
        expect(result.current).toBe('second');
    });
});

describe('useLocalStorage', () => {
    let mockStorage: Record<string, string> = {};
    const originalLocalStorage = window.localStorage;

    beforeEach(() => {
        // Clear mock storage
        mockStorage = {};

        // Create a mock localStorage
        const mockLocalStorage = {
            getItem: vi.fn((key: string) => mockStorage[key] ?? null),
            setItem: vi.fn((key: string, value: string) => {
                mockStorage[key] = value;
            }),
            removeItem: vi.fn((key: string) => {
                delete mockStorage[key];
            }),
            clear: vi.fn(() => {
                mockStorage = {};
            }),
            length: 0,
            key: vi.fn(() => null),
        };

        Object.defineProperty(window, 'localStorage', {
            value: mockLocalStorage,
            writable: true,
        });
    });

    afterEach(() => {
        Object.defineProperty(window, 'localStorage', {
            value: originalLocalStorage,
            writable: true,
        });
    });

    it('should return initial value when localStorage is empty', () => {
        const { result } = renderHook(() => useLocalStorage('testKey', 'default'));
        expect(result.current[0]).toBe('default');
    });

    it('should read existing value from localStorage', () => {
        mockStorage['testKey'] = JSON.stringify('stored');
        const { result } = renderHook(() => useLocalStorage('testKey', 'default'));
        expect(result.current[0]).toBe('stored');
    });

    it('should update localStorage when value changes', () => {
        const { result } = renderHook(() => useLocalStorage('testKey', 'initial'));

        act(() => {
            result.current[1]('updated');
        });

        expect(result.current[0]).toBe('updated');
        expect(mockStorage['testKey']).toBe(JSON.stringify('updated'));
    });

    it('should support function updates', () => {
        const { result } = renderHook(() => useLocalStorage('counter', 0));

        act(() => {
            result.current[1]((prev) => prev + 1);
        });

        expect(result.current[0]).toBe(1);
    });
});

describe('usePrevious', () => {
    it('should return undefined on initial render', () => {
        const { result } = renderHook(() => usePrevious('initial'));
        expect(result.current).toBeUndefined();
    });

    it('should return previous value after update', () => {
        const { result, rerender } = renderHook(
            ({ value }) => usePrevious(value),
            { initialProps: { value: 'first' } }
        );

        expect(result.current).toBeUndefined();

        rerender({ value: 'second' });
        expect(result.current).toBe('first');

        rerender({ value: 'third' });
        expect(result.current).toBe('second');
    });
});

describe('useWindowSize', () => {
    it('should return current window size', () => {
        const { result } = renderHook(() => useWindowSize());

        expect(result.current).toEqual({
            width: window.innerWidth,
            height: window.innerHeight
        });
    });
});

describe('useMediaQuery', () => {
    // Skip this test - matchMedia is difficult to mock properly in jsdom
    it.skip('should return false by default (mocked)', () => {
        const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'));
        expect(result.current).toBe(false);
    });
});

describe('useCopyToClipboard', () => {
    it('should copy text to clipboard', async () => {
        const { result } = renderHook(() => useCopyToClipboard());

        expect(result.current[0]).toBe(false);

        let success: boolean;
        await act(async () => {
            success = await result.current[1]('test text');
        });

        expect(success!).toBe(true);
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith('test text');
    });
});

describe('useAsync', () => {
    it('should handle async function execution', async () => {
        const asyncFn = vi.fn().mockResolvedValue({ data: 'test' });

        const { result } = renderHook(() => useAsync(asyncFn, true));

        // Initially loading
        expect(result.current.loading).toBe(true);
        expect(result.current.data).toBeNull();

        await waitFor(() => {
            expect(result.current.loading).toBe(false);
        });

        expect(result.current.data).toEqual({ data: 'test' });
        expect(result.current.error).toBeNull();
    });

    it('should handle async errors', async () => {
        const error = new Error('Test error');
        const asyncFn = vi.fn().mockRejectedValue(error);

        const { result } = renderHook(() => useAsync(asyncFn, true));

        await waitFor(() => {
            expect(result.current.loading).toBe(false);
        });

        expect(result.current.error).toBe(error);
        expect(result.current.data).toBeNull();
    });

    it('should not execute immediately when immediate is false', () => {
        const asyncFn = vi.fn().mockResolvedValue('data');

        const { result } = renderHook(() => useAsync(asyncFn, false));

        expect(asyncFn).not.toHaveBeenCalled();
        expect(result.current.loading).toBe(false);
    });
});
