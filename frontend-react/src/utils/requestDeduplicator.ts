/**
 * Request deduplication utility
 * Prevents duplicate API requests for the same resource
 */

type PendingRequest<T> = Promise<T>;

class RequestDeduplicator {
    private pendingRequests: Map<string, PendingRequest<unknown>> = new Map();
    private cache: Map<string, { data: unknown; timestamp: number }> = new Map();
    private cacheTTL: number;

    constructor(cacheTTL: number = 5000) {
        this.cacheTTL = cacheTTL;
    }

    /**
     * Deduplicate requests by key
     * If a request with the same key is in-flight, return that promise
     * If cached data exists and is fresh, return cached data
     */
    async dedupe<T>(key: string, fetcher: () => Promise<T>, ttl?: number): Promise<T> {
        const effectiveTTL = ttl ?? this.cacheTTL;

        // Check cache first
        const cached = this.cache.get(key);
        if (cached && Date.now() - cached.timestamp < effectiveTTL) {
            return cached.data as T;
        }

        // Check for pending request
        const pending = this.pendingRequests.get(key);
        if (pending) {
            return pending as Promise<T>;
        }

        // Create new request
        const request = fetcher()
            .then((data) => {
                // Cache the result
                this.cache.set(key, { data, timestamp: Date.now() });
                return data;
            })
            .finally(() => {
                // Remove from pending
                this.pendingRequests.delete(key);
            });

        this.pendingRequests.set(key, request);
        return request;
    }

    /**
     * Invalidate cache for a key or pattern
     */
    invalidate(keyOrPattern: string | RegExp): void {
        if (typeof keyOrPattern === 'string') {
            this.cache.delete(keyOrPattern);
        } else {
            for (const key of this.cache.keys()) {
                if (keyOrPattern.test(key)) {
                    this.cache.delete(key);
                }
            }
        }
    }

    /**
     * Clear all cache
     */
    clear(): void {
        this.cache.clear();
        this.pendingRequests.clear();
    }

    /**
     * Get cache stats
     */
    getStats() {
        return {
            cacheSize: this.cache.size,
            pendingRequests: this.pendingRequests.size
        };
    }
}

// Singleton instance
export const requestDeduplicator = new RequestDeduplicator();

/**
 * Hook for deduped data fetching
 */
import { useState, useEffect, useCallback } from 'react';

interface UseDedupedFetchOptions<T> {
    key: string;
    fetcher: () => Promise<T>;
    ttl?: number;
    enabled?: boolean;
}

interface UseDedupedFetchResult<T> {
    data: T | null;
    loading: boolean;
    error: Error | null;
    refetch: () => Promise<void>;
}

export function useDedupedFetch<T>({
    key,
    fetcher,
    ttl,
    enabled = true
}: UseDedupedFetchOptions<T>): UseDedupedFetchResult<T> {
    const [data, setData] = useState<T | null>(null);
    const [loading, setLoading] = useState(enabled);
    const [error, setError] = useState<Error | null>(null);

    const fetchData = useCallback(async () => {
        if (!enabled) return;

        setLoading(true);
        setError(null);

        try {
            const result = await requestDeduplicator.dedupe(key, fetcher, ttl);
            setData(result);
        } catch (err) {
            setError(err instanceof Error ? err : new Error('Unknown error'));
        } finally {
            setLoading(false);
        }
    }, [key, fetcher, ttl, enabled]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const refetch = useCallback(async () => {
        requestDeduplicator.invalidate(key);
        await fetchData();
    }, [key, fetchData]);

    return { data, loading, error, refetch };
}

/**
 * Debounce utility for search inputs
 */
export function debounce<T extends (...args: Parameters<T>) => ReturnType<T>>(
    fn: T,
    delay: number
): (...args: Parameters<T>) => void {
    let timeoutId: ReturnType<typeof setTimeout>;

    return (...args: Parameters<T>) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn(...args), delay);
    };
}

/**
 * Throttle utility for frequent events
 */
export function throttle<T extends (...args: Parameters<T>) => ReturnType<T>>(
    fn: T,
    limit: number
): (...args: Parameters<T>) => void {
    let inThrottle = false;

    return (...args: Parameters<T>) => {
        if (!inThrottle) {
            fn(...args);
            inThrottle = true;
            setTimeout(() => (inThrottle = false), limit);
        }
    };
}
