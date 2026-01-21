import { useState, useEffect, createContext, useContext, type ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Moon, Sun, Monitor, Volume2, VolumeX, Bell, BellOff, Eye, EyeOff } from 'lucide-react';

// ============= Types =============

type Theme = 'dark' | 'light' | 'system';

interface Settings {
    theme: Theme;
    soundEnabled: boolean;
    notificationsEnabled: boolean;
    showThinking: boolean;
    showAvatar: boolean;
    reduceMotion: boolean;
}

interface SettingsContextValue {
    settings: Settings;
    updateSetting: <K extends keyof Settings>(key: K, value: Settings[K]) => void;
    resetSettings: () => void;
}

// ============= Defaults =============

const DEFAULT_SETTINGS: Settings = {
    theme: 'dark',
    soundEnabled: true,
    notificationsEnabled: true,
    showThinking: true,
    showAvatar: true,
    reduceMotion: false,
};

// ============= Context =============

const SettingsContext = createContext<SettingsContextValue | null>(null);

// eslint-disable-next-line react-refresh/only-export-components
export function useSettings() {
    const context = useContext(SettingsContext);
    if (!context) {
        throw new Error('useSettings must be used within a SettingsProvider');
    }
    return context;
}

// ============= Provider =============

export function SettingsProvider({ children }: { children: ReactNode }) {
    const [settings, setSettings] = useState<Settings>(() => {
        if (typeof window === 'undefined') return DEFAULT_SETTINGS;

        const saved = localStorage.getItem('chirag-clone-settings');
        if (saved) {
            try {
                return { ...DEFAULT_SETTINGS, ...JSON.parse(saved) };
            } catch {
                return DEFAULT_SETTINGS;
            }
        }
        return DEFAULT_SETTINGS;
    });

    // Persist settings
    useEffect(() => {
        localStorage.setItem('chirag-clone-settings', JSON.stringify(settings));
    }, [settings]);

    // Apply theme
    useEffect(() => {
        const root = document.documentElement;

        if (settings.theme === 'system') {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            root.classList.toggle('dark', prefersDark);
            root.classList.toggle('light', !prefersDark);
        } else {
            root.classList.toggle('dark', settings.theme === 'dark');
            root.classList.toggle('light', settings.theme === 'light');
        }
    }, [settings.theme]);

    // Apply reduce motion
    useEffect(() => {
        document.documentElement.classList.toggle('reduce-motion', settings.reduceMotion);
    }, [settings.reduceMotion]);

    const updateSetting = <K extends keyof Settings>(key: K, value: Settings[K]) => {
        setSettings(prev => ({ ...prev, [key]: value }));
    };

    const resetSettings = () => {
        setSettings(DEFAULT_SETTINGS);
    };

    return (
        <SettingsContext.Provider value={{ settings, updateSetting, resetSettings }}>
            {children}
        </SettingsContext.Provider>
    );
}

// ============= Settings Panel Component =============

interface SettingsPanelProps {
    isOpen: boolean;
    onClose: () => void;
}

export function SettingsPanel({ isOpen, onClose }: SettingsPanelProps) {
    const { settings, updateSetting, resetSettings } = useSettings();

    return (
        <AnimatePresence>
            {isOpen && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 z-50 flex items-center justify-center"
                    onClick={onClose}
                >
                    {/* Backdrop */}
                    <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

                    {/* Panel */}
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        onClick={e => e.stopPropagation()}
                        className="relative w-full max-w-md bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl overflow-hidden"
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
                            <h2 className="text-lg font-semibold text-white">Settings</h2>
                            <button
                                onClick={onClose}
                                className="p-1 hover:bg-zinc-800 rounded-lg transition-colors"
                            >
                                <X size={20} className="text-zinc-400" />
                            </button>
                        </div>

                        {/* Settings List */}
                        <div className="p-6 space-y-6">
                            {/* Theme */}
                            <SettingGroup title="Appearance">
                                <SettingRow
                                    label="Theme"
                                    description="Choose your preferred color scheme"
                                >
                                    <ThemeToggle
                                        value={settings.theme}
                                        onChange={v => updateSetting('theme', v)}
                                    />
                                </SettingRow>
                                <SettingToggle
                                    label="Reduce Motion"
                                    description="Minimize animations"
                                    value={settings.reduceMotion}
                                    onChange={v => updateSetting('reduceMotion', v)}
                                />
                            </SettingGroup>

                            {/* Chat */}
                            <SettingGroup title="Chat">
                                <SettingToggle
                                    label="Show Thinking Process"
                                    description="Display AI reasoning steps"
                                    value={settings.showThinking}
                                    onChange={v => updateSetting('showThinking', v)}
                                    icon={<Eye size={18} />}
                                    offIcon={<EyeOff size={18} />}
                                />
                                <SettingToggle
                                    label="Show 3D Avatar"
                                    description="Display animated avatar"
                                    value={settings.showAvatar}
                                    onChange={v => updateSetting('showAvatar', v)}
                                />
                            </SettingGroup>

                            {/* Notifications */}
                            <SettingGroup title="Notifications">
                                <SettingToggle
                                    label="Sound Effects"
                                    description="Play sounds for messages"
                                    value={settings.soundEnabled}
                                    onChange={v => updateSetting('soundEnabled', v)}
                                    icon={<Volume2 size={18} />}
                                    offIcon={<VolumeX size={18} />}
                                />
                                <SettingToggle
                                    label="Desktop Notifications"
                                    description="Show browser notifications"
                                    value={settings.notificationsEnabled}
                                    onChange={v => updateSetting('notificationsEnabled', v)}
                                    icon={<Bell size={18} />}
                                    offIcon={<BellOff size={18} />}
                                />
                            </SettingGroup>
                        </div>

                        {/* Footer */}
                        <div className="px-6 py-4 border-t border-zinc-800 flex justify-end">
                            <button
                                onClick={resetSettings}
                                className="px-4 py-2 text-sm text-zinc-400 hover:text-white transition-colors"
                            >
                                Reset to defaults
                            </button>
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}

// ============= Sub-components =============

function SettingGroup({ title, children }: { title: string; children: ReactNode }) {
    return (
        <div>
            <h3 className="text-sm font-medium text-zinc-400 mb-3">{title}</h3>
            <div className="space-y-3">{children}</div>
        </div>
    );
}

function SettingRow({ label, description, children }: { label: string; description?: string; children: ReactNode }) {
    return (
        <div className="flex items-center justify-between gap-4">
            <div>
                <div className="text-sm text-white">{label}</div>
                {description && <div className="text-xs text-zinc-500">{description}</div>}
            </div>
            {children}
        </div>
    );
}

function SettingToggle({
    label,
    description,
    value,
    onChange,
    icon,
    offIcon
}: {
    label: string;
    description?: string;
    value: boolean;
    onChange: (value: boolean) => void;
    icon?: ReactNode;
    offIcon?: ReactNode;
}) {
    return (
        <SettingRow label={label} description={description}>
            <button
                onClick={() => onChange(!value)}
                className={`relative w-12 h-6 rounded-full transition-colors ${value ? 'bg-primary' : 'bg-zinc-700'
                    }`}
            >
                <motion.div
                    layout
                    className="absolute top-1 left-1 w-4 h-4 bg-white rounded-full flex items-center justify-center"
                    animate={{ x: value ? 24 : 0 }}
                    transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                >
                    {value ? (
                        icon && <span className="text-primary scale-75">{icon}</span>
                    ) : (
                        offIcon && <span className="text-zinc-500 scale-75">{offIcon}</span>
                    )}
                </motion.div>
            </button>
        </SettingRow>
    );
}

function ThemeToggle({ value, onChange }: { value: Theme; onChange: (theme: Theme) => void }) {
    const options: { value: Theme; icon: ReactNode; label: string }[] = [
        { value: 'light', icon: <Sun size={16} />, label: 'Light' },
        { value: 'dark', icon: <Moon size={16} />, label: 'Dark' },
        { value: 'system', icon: <Monitor size={16} />, label: 'System' },
    ];

    return (
        <div className="flex bg-zinc-800 rounded-lg p-1">
            {options.map(option => (
                <button
                    key={option.value}
                    onClick={() => onChange(option.value)}
                    className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${value === option.value
                            ? 'bg-zinc-700 text-white'
                            : 'text-zinc-400 hover:text-white'
                        }`}
                    title={option.label}
                >
                    {option.icon}
                </button>
            ))}
        </div>
    );
}
