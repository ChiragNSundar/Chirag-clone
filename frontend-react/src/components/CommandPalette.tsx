import { useState, useCallback, useMemo, type ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, MessageSquare, Database, Brain, Settings, User, Zap } from 'lucide-react';
import { useKeyboardShortcut } from '../hooks/useKeyboardShortcuts';
import { useNavigate } from 'react-router-dom';
import { SettingsPanel } from './SettingsPanel';

interface CommandItem {
    id: string;
    title: string;
    description?: string;
    icon: ReactNode;
    action: () => void;
    keywords?: string[];
    category: 'navigation' | 'action' | 'settings';
}

export function CommandPalette() {
    const [isOpen, setIsOpen] = useState(false);
    const [query, setQuery] = useState('');
    const [showSettings, setShowSettings] = useState(false);
    const navigate = useNavigate();

    // Toggle with Cmd+K
    useKeyboardShortcut('k', () => setIsOpen(prev => !prev), { meta: true });

    // Close with Escape
    useKeyboardShortcut('Escape', () => setIsOpen(false), { preventDefault: false });

    const commands: CommandItem[] = useMemo(() => [
        // Navigation
        {
            id: 'nav-chat',
            title: 'Go to Chat',
            description: 'Open the chat interface',
            icon: <MessageSquare size={18} />,
            action: () => { navigate('/'); setIsOpen(false); },
            keywords: ['talk', 'conversation', 'message'],
            category: 'navigation'
        },
        {
            id: 'nav-dashboard',
            title: 'Go to Dashboard',
            description: 'View analytics and stats',
            icon: <Brain size={18} />,
            action: () => { navigate('/dashboard'); setIsOpen(false); },
            keywords: ['analytics', 'stats', 'metrics'],
            category: 'navigation'
        },
        {
            id: 'nav-training',
            title: 'Go to Training Center',
            description: 'Train your clone',
            icon: <Database size={18} />,
            action: () => { navigate('/training'); setIsOpen(false); },
            keywords: ['learn', 'teach', 'upload'],
            category: 'navigation'
        },
        {
            id: 'nav-profile',
            title: 'Go to Profile',
            description: 'View clone personality',
            icon: <User size={18} />,
            action: () => { navigate('/profile'); setIsOpen(false); },
            keywords: ['about', 'personality'],
            category: 'navigation'
        },
        {
            id: 'nav-autopilot',
            title: 'Go to Autopilot',
            description: 'Manage social integrations',
            icon: <Zap size={18} />,
            action: () => { navigate('/autopilot'); setIsOpen(false); },
            keywords: ['discord', 'telegram', 'bot'],
            category: 'navigation'
        },
        // Actions
        {
            id: 'action-new-chat',
            title: 'New Chat Session',
            description: 'Start a fresh conversation',
            icon: <MessageSquare size={18} />,
            action: () => { window.location.href = '/?new=1'; setIsOpen(false); },
            keywords: ['reset', 'clear'],
            category: 'action'
        },
        // Settings
        {
            id: 'settings-open',
            title: 'Open Settings',
            description: 'Configure your clone',
            icon: <Settings size={18} />,
            action: () => { setShowSettings(true); setIsOpen(false); },
            keywords: ['preferences', 'config'],
            category: 'settings'
        }
    ], [navigate]);

    const filteredCommands = useMemo(() => {
        if (!query.trim()) return commands;

        const q = query.toLowerCase();
        return commands.filter(cmd =>
            cmd.title.toLowerCase().includes(q) ||
            cmd.description?.toLowerCase().includes(q) ||
            cmd.keywords?.some(k => k.includes(q))
        );
    }, [commands, query]);

    const groupedCommands = useMemo(() => {
        const groups: Record<string, CommandItem[]> = {
            navigation: [],
            action: [],
            settings: []
        };
        filteredCommands.forEach(cmd => {
            groups[cmd.category].push(cmd);
        });
        return groups;
    }, [filteredCommands]);

    const handleSelect = useCallback((cmd: CommandItem) => {
        cmd.action();
    }, []);

    return (
        <>
            {isOpen && (
                <AnimatePresence>
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]"
                        onClick={() => setIsOpen(false)}
                    >
                        {/* Backdrop */}
                        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

                        {/* Palette */}
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95, y: -20 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.95, y: -20 }}
                            transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                            onClick={e => e.stopPropagation()}
                            className="relative w-full max-w-lg bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl overflow-hidden"
                        >
                            {/* Search Input */}
                            <div className="flex items-center gap-3 px-4 py-3 border-b border-zinc-800">
                                <Search size={20} className="text-zinc-500" />
                                <input
                                    type="text"
                                    autoFocus
                                    value={query}
                                    onChange={e => setQuery(e.target.value)}
                                    placeholder="Type a command or search..."
                                    className="flex-1 bg-transparent border-none outline-none text-white placeholder-zinc-500"
                                />
                                <kbd className="px-2 py-0.5 text-xs bg-zinc-800 border border-zinc-700 rounded text-zinc-400">
                                    ESC
                                </kbd>
                            </div>

                            {/* Commands List */}
                            <div className="max-h-80 overflow-y-auto py-2">
                                {filteredCommands.length === 0 ? (
                                    <div className="px-4 py-8 text-center text-zinc-500">
                                        No commands found
                                    </div>
                                ) : (
                                    <>
                                        {groupedCommands.navigation.length > 0 && (
                                            <CommandGroup title="Navigation" items={groupedCommands.navigation} onSelect={handleSelect} />
                                        )}
                                        {groupedCommands.action.length > 0 && (
                                            <CommandGroup title="Actions" items={groupedCommands.action} onSelect={handleSelect} />
                                        )}
                                        {groupedCommands.settings.length > 0 && (
                                            <CommandGroup title="Settings" items={groupedCommands.settings} onSelect={handleSelect} />
                                        )}
                                    </>
                                )}
                            </div>

                            {/* Footer */}
                            <div className="flex items-center gap-4 px-4 py-2 border-t border-zinc-800 text-xs text-zinc-500">
                                <span className="flex items-center gap-1">
                                    <kbd className="px-1.5 py-0.5 bg-zinc-800 rounded">↑↓</kbd> Navigate
                                </span>
                                <span className="flex items-center gap-1">
                                    <kbd className="px-1.5 py-0.5 bg-zinc-800 rounded">↵</kbd> Select
                                </span>
                                <span className="flex items-center gap-1">
                                    <kbd className="px-1.5 py-0.5 bg-zinc-800 rounded">⌘K</kbd> Toggle
                                </span>
                            </div>
                        </motion.div>
                    </motion.div>
                </AnimatePresence>
            )}

            {/* Settings Modal */}
            <SettingsPanel isOpen={showSettings} onClose={() => setShowSettings(false)} />
        </>
    );
}

function CommandGroup({
    title,
    items,
    onSelect
}: {
    title: string;
    items: CommandItem[];
    onSelect: (item: CommandItem) => void;
}) {
    return (
        <div className="mb-2">
            <div className="px-4 py-1 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                {title}
            </div>
            {items.map(item => (
                <button
                    key={item.id}
                    onClick={() => onSelect(item)}
                    className="w-full flex items-center gap-3 px-4 py-2 hover:bg-zinc-800 transition-colors text-left"
                >
                    <div className="text-zinc-400">{item.icon}</div>
                    <div className="flex-1 min-w-0">
                        <div className="text-sm text-white">{item.title}</div>
                        {item.description && (
                            <div className="text-xs text-zinc-500 truncate">{item.description}</div>
                        )}
                    </div>
                </button>
            ))}
        </div>
    );
}
