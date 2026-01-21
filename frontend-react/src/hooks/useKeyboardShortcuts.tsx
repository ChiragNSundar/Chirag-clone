import { formatShortcut, type ShortcutOptions } from './useKeyboardShortcuts';

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

// Re-export everything from the hooks file for backwards compatibility
// eslint-disable-next-line react-refresh/only-export-components
export * from './useKeyboardShortcuts';
