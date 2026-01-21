import { useState, useEffect, useRef, useMemo, useCallback, useSyncExternalStore } from 'react';

// ============= useDebounce =============

export function useDebounce<T>(value: T, delay: number): T {
    const [debouncedValue, setDebouncedValue] = useState(value);

    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedValue(value);
        }, delay);

        return () => clearTimeout(timer);
    }, [value, delay]);

    return debouncedValue;
}

// ============= useLocalStorage =============

export function useLocalStorage<T>(key: string, initialValue: T): [T, (value: T | ((val: T) => T)) => void] {
    const [storedValue, setStoredValue] = useState<T>(() => {
        if (typeof window === 'undefined') return initialValue;

        try {
            const item = window.localStorage.getItem(key);
            return item ? JSON.parse(item) : initialValue;
        } catch {
            return initialValue;
        }
    });

    const setValue = useCallback((value: T | ((val: T) => T)) => {
        setStoredValue(prev => {
            const valueToStore = value instanceof Function ? value(prev) : value;

            if (typeof window !== 'undefined') {
                window.localStorage.setItem(key, JSON.stringify(valueToStore));
            }

            return valueToStore;
        });
    }, [key]);

    return [storedValue, setValue];
}

// ============= usePrevious =============

export function usePrevious<T>(value: T): T | undefined {
    const ref = useRef<T>(undefined);

    useEffect(() => {
        ref.current = value;
    }, [value]);

    return ref.current;
}

// ============= useOnClickOutside =============

export function useOnClickOutside<T extends HTMLElement>(
    ref: React.RefObject<T>,
    handler: (event: MouseEvent | TouchEvent) => void
) {
    useEffect(() => {
        const listener = (event: MouseEvent | TouchEvent) => {
            if (!ref.current || ref.current.contains(event.target as Node)) {
                return;
            }
            handler(event);
        };

        document.addEventListener('mousedown', listener);
        document.addEventListener('touchstart', listener);

        return () => {
            document.removeEventListener('mousedown', listener);
            document.removeEventListener('touchstart', listener);
        };
    }, [ref, handler]);
}

// ============= useWindowSize =============

interface WindowSize {
    width: number;
    height: number;
}

export function useWindowSize(): WindowSize {
    const [size, setSize] = useState<WindowSize>({
        width: typeof window !== 'undefined' ? window.innerWidth : 0,
        height: typeof window !== 'undefined' ? window.innerHeight : 0,
    });

    useEffect(() => {
        const handleResize = () => {
            setSize({
                width: window.innerWidth,
                height: window.innerHeight,
            });
        };

        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    return size;
}

// ============= useMediaQuery =============

export function useMediaQuery(query: string): boolean {
    const getSnapshot = () => {
        if (typeof window === 'undefined') return false;
        return window.matchMedia(query).matches;
    };

    const getServerSnapshot = () => false;

    const subscribe = (callback: () => void) => {
        if (typeof window === 'undefined') return () => { };
        const media = window.matchMedia(query);
        media.addEventListener('change', callback);
        return () => media.removeEventListener('change', callback);
    };

    // useSyncExternalStore is the recommended way to subscribe to external stores
    // It avoids the need for setState in useEffect
    const matches = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
    return matches;
}

// Common breakpoints
export const useIsMobile = () => useMediaQuery('(max-width: 768px)');
export const useIsTablet = () => useMediaQuery('(min-width: 769px) and (max-width: 1024px)');
export const useIsDesktop = () => useMediaQuery('(min-width: 1025px)');
export const usePrefersDarkMode = () => useMediaQuery('(prefers-color-scheme: dark)');
export const usePrefersReducedMotion = () => useMediaQuery('(prefers-reduced-motion: reduce)');

// ============= useIntersectionObserver =============

interface UseIntersectionObserverOptions {
    threshold?: number | number[];
    root?: Element | null;
    rootMargin?: string;
    freezeOnceVisible?: boolean;
}

export function useIntersectionObserver(
    ref: React.RefObject<Element>,
    options: UseIntersectionObserverOptions = {}
): boolean {
    const { threshold = 0, root = null, rootMargin = '0px', freezeOnceVisible = false } = options;
    const [isVisible, setIsVisible] = useState(false);

    useEffect(() => {
        const node = ref.current;
        if (!node) return;

        if (freezeOnceVisible && isVisible) return;

        const observer = new IntersectionObserver(
            ([entry]) => {
                setIsVisible(entry.isIntersecting);
            },
            { threshold, root, rootMargin }
        );

        observer.observe(node);

        return () => observer.disconnect();
    }, [ref, threshold, root, rootMargin, freezeOnceVisible, isVisible]);

    return isVisible;
}

// ============= useVirtualScroll =============

interface UseVirtualScrollOptions {
    itemCount: number;
    itemHeight: number;
    overscan?: number;
}

interface VirtualScrollResult {
    virtualItems: { index: number; start: number }[];
    totalHeight: number;
    containerProps: {
        onScroll: (e: React.UIEvent<HTMLDivElement>) => void;
        style: React.CSSProperties;
    };
    wrapperProps: {
        style: React.CSSProperties;
    };
}

export function useVirtualScroll({
    itemCount,
    itemHeight,
    overscan = 3
}: UseVirtualScrollOptions): VirtualScrollResult {
    const [scrollTop, setScrollTop] = useState(0);
    const [containerHeight, setContainerHeight] = useState(0);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (containerRef.current) {
            setContainerHeight(containerRef.current.clientHeight);
        }
    }, []);

    const virtualItems = useMemo(() => {
        const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
        const endIndex = Math.min(
            itemCount - 1,
            Math.ceil((scrollTop + containerHeight) / itemHeight) + overscan
        );

        const items: { index: number; start: number }[] = [];
        for (let i = startIndex; i <= endIndex; i++) {
            items.push({
                index: i,
                start: i * itemHeight
            });
        }

        return items;
    }, [scrollTop, containerHeight, itemCount, itemHeight, overscan]);

    const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
        setScrollTop(e.currentTarget.scrollTop);
    }, []);

    return {
        virtualItems,
        totalHeight: itemCount * itemHeight,
        containerProps: {
            onScroll: handleScroll,
            style: { overflow: 'auto', height: '100%' }
        },
        wrapperProps: {
            style: {
                height: itemCount * itemHeight,
                position: 'relative' as const
            }
        }
    };
}

// ============= useCopyToClipboard =============

export function useCopyToClipboard(): [boolean, (text: string) => Promise<boolean>] {
    const [copied, setCopied] = useState(false);

    const copy = useCallback(async (text: string): Promise<boolean> => {
        try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
            return true;
        } catch {
            setCopied(false);
            return false;
        }
    }, []);

    return [copied, copy];
}

// ============= useAsync =============

interface AsyncState<T> {
    data: T | null;
    loading: boolean;
    error: Error | null;
}

export function useAsync<T>(
    asyncFunction: () => Promise<T>,
    immediate: boolean = true
): AsyncState<T> & { execute: () => Promise<void> } {
    const [state, setState] = useState<AsyncState<T>>({
        data: null,
        loading: immediate,
        error: null
    });

    const mountedRef = useRef(true);
    const hasRun = useRef(false);

    const execute = useCallback(async () => {
        setState(prev => ({ ...prev, loading: true, error: null }));
        try {
            const data = await asyncFunction();
            if (mountedRef.current) {
                setState({ data, loading: false, error: null });
            }
        } catch (error) {
            if (mountedRef.current) {
                setState({ data: null, loading: false, error: error as Error });
            }
        }
    }, [asyncFunction]);

    useEffect(() => {
        mountedRef.current = true;
        if (immediate && !hasRun.current) {
            hasRun.current = true;
            // Schedule execution asynchronously to avoid synchronous setState in effect
            queueMicrotask(() => {
                if (mountedRef.current) {
                    execute();
                }
            });
        }
        return () => {
            mountedRef.current = false;
        };
    }, [immediate, execute]);

    return { ...state, execute };
}
