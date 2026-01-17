import { useEffect, useRef } from 'react';

type KeyHandler = (event: KeyboardEvent) => void;

interface ShortcutOptions {
    ctrl?: boolean;
    shift?: boolean;
    alt?: boolean;
    meta?: boolean; // Cmd on Mac
    preventDefault?: boolean;
}

interface Shortcut extends ShortcutOptions {
    key: string;
    handler: KeyHandler;
    description?: string;
}

/**
 * Hook for registering keyboard shortcuts
 */
export function useKeyboardShortcut(
    key: string,
    handler: KeyHandler,
    options: ShortcutOptions = {}
) {
    const { ctrl, shift, alt, meta, preventDefault = true } = options;
    const handlerRef = useRef(handler);

    // Keep handler ref updated
    useEffect(() => {
        handlerRef.current = handler;
    }, [handler]);

    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            // Check modifiers
            if (ctrl && !event.ctrlKey) return;
            if (shift && !event.shiftKey) return;
            if (alt && !event.altKey) return;
            if (meta && !event.metaKey) return;

            // Check key (case-insensitive)
            if (event.key.toLowerCase() !== key.toLowerCase()) return;

            // Don't trigger in inputs unless specifically allowed
            const target = event.target as HTMLElement;
            if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
                // Allow escape in inputs
                if (key.toLowerCase() !== 'escape') return;
            }

            if (preventDefault) {
                event.preventDefault();
            }

            handlerRef.current(event);
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [key, ctrl, shift, alt, meta, preventDefault]);
}

/**
 * Hook for registering multiple shortcuts
 */
export function useKeyboardShortcuts(shortcuts: Shortcut[]) {
    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            for (const shortcut of shortcuts) {
                const { key, handler, ctrl, shift, alt, meta, preventDefault = true } = shortcut;

                // Check modifiers
                if (ctrl && !event.ctrlKey) continue;
                if (shift && !event.shiftKey) continue;
                if (alt && !event.altKey) continue;
                if (meta && !event.metaKey) continue;

                // Check key
                if (event.key.toLowerCase() !== key.toLowerCase()) continue;

                // Don't trigger in inputs
                const target = event.target as HTMLElement;
                if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
                    if (key.toLowerCase() !== 'escape') continue;
                }

                if (preventDefault) {
                    event.preventDefault();
                }

                handler(event);
                break;
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [shortcuts]);
}

/**
 * Common shortcuts for the app
 */
export const COMMON_SHORTCUTS = {
    // Navigation
    COMMAND_PALETTE: { key: 'k', meta: true, description: 'Open command palette' },
    SEARCH: { key: '/', description: 'Focus search' },

    // Actions
    NEW_CHAT: { key: 'n', meta: true, description: 'New chat' },
    TOGGLE_SIDEBAR: { key: 'b', meta: true, description: 'Toggle sidebar' },

    // Editing
    SEND_MESSAGE: { key: 'Enter', description: 'Send message' },
    CANCEL: { key: 'Escape', description: 'Cancel / Close' },

    // Voice
    PUSH_TO_TALK: { key: ' ', shift: true, description: 'Push to talk (hold)' },
};

/**
 * Display shortcut in UI (platform-aware)
 */
export function formatShortcut(shortcut: ShortcutOptions & { key: string }): string {
    const isMac = navigator.platform.toLowerCase().includes('mac');
    const parts: string[] = [];

    if (shortcut.meta) parts.push(isMac ? '⌘' : 'Ctrl');
    if (shortcut.ctrl) parts.push(isMac ? '⌃' : 'Ctrl');
    if (shortcut.alt) parts.push(isMac ? '⌥' : 'Alt');
    if (shortcut.shift) parts.push(isMac ? '⇧' : 'Shift');

    // Format special keys
    let keyDisplay = shortcut.key;
    switch (shortcut.key.toLowerCase()) {
        case 'enter': keyDisplay = '↵'; break;
        case 'escape': keyDisplay = 'Esc'; break;
        case 'arrowup': keyDisplay = '↑'; break;
        case 'arrowdown': keyDisplay = '↓'; break;
        case 'arrowleft': keyDisplay = '←'; break;
        case 'arrowright': keyDisplay = '→'; break;
        case ' ': keyDisplay = 'Space'; break;
    }

    parts.push(keyDisplay.toUpperCase());
    return parts.join(isMac ? '' : '+');
}

/**
 * Keyboard shortcut badge component
 */
export function ShortcutBadge({ shortcut }: { shortcut: ShortcutOptions & { key: string } }) {
    return (
        <kbd className="px-1.5 py-0.5 text-xs font-mono bg-zinc-800 border border-zinc-700 rounded text-zinc-400">
            {formatShortcut(shortcut)}
        </kbd>
    );
}
