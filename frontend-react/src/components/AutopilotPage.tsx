import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
    Bot, Play, Pause, MessageSquare, Settings, Clock,
    CheckCircle, XCircle, RefreshCcw, Zap, Send
} from 'lucide-react';

interface BotStatus {
    configured: boolean;
    running: boolean;
    auto_reply_dms?: boolean;
    auto_reply_mentions?: boolean;
    auto_reply_enabled?: boolean;
    recent_replies?: number;
    error?: string;
}

interface ReplyLog {
    timestamp: string;
    platform: string;
    user: string;
    message: string;
    response: string;
}

const StatusBadge = ({ running, configured }: { running: boolean; configured: boolean }) => {
    if (!configured) {
        return (
            <span className="flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-zinc-500/20 text-zinc-400">
                <XCircle size={12} />
                Not Configured
            </span>
        );
    }
    return running ? (
        <span className="flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-green-500/20 text-green-400">
            <CheckCircle size={12} />
            Active
        </span>
    ) : (
        <span className="flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-yellow-500/20 text-yellow-400">
            <Pause size={12} />
            Stopped
        </span>
    );
};

const BotCard = ({
    title,
    icon,
    status,
    onStart,
    onStop,
    loading,
    children
}: {
    title: string;
    icon: React.ReactNode;
    status: BotStatus;
    onStart: () => void;
    onStop: () => void;
    loading: boolean;
    children?: React.ReactNode;
}) => (
    <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel p-6"
    >
        <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
                <div className="p-3 rounded-xl bg-primary/20 text-primary">
                    {icon}
                </div>
                <div>
                    <h3 className="font-semibold text-lg">{title}</h3>
                    <StatusBadge running={status.running} configured={status.configured} />
                </div>
            </div>
        </div>

        {status.error && (
            <div className="mb-4 p-3 rounded-lg bg-red-500/20 text-red-400 text-sm">
                {status.error}
            </div>
        )}

        {!status.configured && (
            <div className="mb-4 p-3 rounded-lg bg-zinc-500/20 text-zinc-400 text-sm">
                Set the bot token in your <code className="text-white">.env</code> file to enable.
            </div>
        )}

        {children}

        <div className="flex gap-2 mt-4">
            <button
                onClick={onStart}
                disabled={!status.configured || status.running || loading}
                className="flex-1 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
                {loading ? <RefreshCcw className="animate-spin" size={16} /> : <Play size={16} />}
                Start
            </button>
            <button
                onClick={onStop}
                disabled={!status.running || loading}
                className="flex-1 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
                <Pause size={16} />
                Stop
            </button>
        </div>

        {status.recent_replies !== undefined && status.recent_replies > 0 && (
            <p className="text-xs text-zinc-500 mt-3 text-center">
                {status.recent_replies} replies sent this session
            </p>
        )}
    </motion.div>
);

export const AutopilotPage = () => {
    const [discordStatus, setDiscordStatus] = useState<BotStatus>({ configured: false, running: false });
    const [telegramStatus, setTelegramStatus] = useState<BotStatus>({ configured: false, running: false });
    const [logs, setLogs] = useState<ReplyLog[]>([]);
    const [loading, setLoading] = useState<string | null>(null);

    const fetchStatus = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/autopilot/status');
            const data = await res.json();
            setDiscordStatus(data.discord);
            setTelegramStatus(data.telegram);
        } catch (e) {
            console.error('Failed to fetch status:', e);
        }
    };

    const fetchLogs = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/autopilot/logs');
            const data = await res.json();
            setLogs(data.logs || []);
        } catch (e) {
            console.error('Failed to fetch logs:', e);
        }
    };

    useEffect(() => {
        fetchStatus();
        fetchLogs();
        const interval = setInterval(() => {
            fetchStatus();
            fetchLogs();
        }, 10000);
        return () => clearInterval(interval);
    }, []);

    const startDiscord = async () => {
        setLoading('discord-start');
        try {
            await fetch('http://localhost:8000/api/autopilot/discord/start', { method: 'POST' });
            await fetchStatus();
        } finally {
            setLoading(null);
        }
    };

    const stopDiscord = async () => {
        setLoading('discord-stop');
        try {
            await fetch('http://localhost:8000/api/autopilot/discord/stop', { method: 'POST' });
            await fetchStatus();
        } finally {
            setLoading(null);
        }
    };

    const startTelegram = async () => {
        setLoading('telegram-start');
        try {
            await fetch('http://localhost:8000/api/autopilot/telegram/start', { method: 'POST' });
            await fetchStatus();
        } finally {
            setLoading(null);
        }
    };

    const stopTelegram = async () => {
        setLoading('telegram-stop');
        try {
            await fetch('http://localhost:8000/api/autopilot/telegram/stop', { method: 'POST' });
            await fetchStatus();
        } finally {
            setLoading(null);
        }
    };

    return (
        <div className="p-6 max-w-5xl mx-auto space-y-6">
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
            >
                <h1 className="text-2xl font-bold flex items-center gap-2">
                    <Bot className="text-primary" />
                    Autopilot
                </h1>
                <p className="text-zinc-400">Let your digital twin respond on your behalf</p>
            </motion.div>

            {/* Bot Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <BotCard
                    title="Discord"
                    icon={<MessageSquare size={24} />}
                    status={discordStatus}
                    onStart={startDiscord}
                    onStop={stopDiscord}
                    loading={loading?.startsWith('discord') || false}
                >
                    <div className="space-y-2 text-sm">
                        <div className="flex items-center justify-between p-2 rounded bg-white/5">
                            <span className="text-zinc-400">Auto-reply to DMs</span>
                            <span className={discordStatus.auto_reply_dms ? 'text-green-400' : 'text-zinc-500'}>
                                {discordStatus.auto_reply_dms ? 'ON' : 'OFF'}
                            </span>
                        </div>
                        <div className="flex items-center justify-between p-2 rounded bg-white/5">
                            <span className="text-zinc-400">Auto-reply to mentions</span>
                            <span className={discordStatus.auto_reply_mentions ? 'text-green-400' : 'text-zinc-500'}>
                                {discordStatus.auto_reply_mentions ? 'ON' : 'OFF'}
                            </span>
                        </div>
                    </div>
                </BotCard>

                <BotCard
                    title="Telegram"
                    icon={<Send size={24} />}
                    status={telegramStatus}
                    onStart={startTelegram}
                    onStop={stopTelegram}
                    loading={loading?.startsWith('telegram') || false}
                >
                    <div className="space-y-2 text-sm">
                        <div className="flex items-center justify-between p-2 rounded bg-white/5">
                            <span className="text-zinc-400">Auto-reply enabled</span>
                            <span className={telegramStatus.auto_reply_enabled ? 'text-green-400' : 'text-zinc-500'}>
                                {telegramStatus.auto_reply_enabled ? 'ON' : 'OFF'}
                            </span>
                        </div>
                    </div>
                </BotCard>
            </div>

            {/* Setup Instructions */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="glass-panel p-6"
            >
                <h3 className="font-semibold mb-4 flex items-center gap-2">
                    <Settings size={20} className="text-primary" />
                    Setup Instructions
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm">
                    <div>
                        <h4 className="font-medium text-blue-400 mb-2">Discord Bot</h4>
                        <ol className="list-decimal list-inside space-y-1 text-zinc-400">
                            <li>Create bot at <a href="https://discord.com/developers" target="_blank" className="text-primary hover:underline">Discord Developer Portal</a></li>
                            <li>Enable Message Content Intent</li>
                            <li>Copy the bot token</li>
                            <li>Add <code className="text-white">DISCORD_BOT_TOKEN=your_token</code> to .env</li>
                            <li>Invite bot to your server</li>
                        </ol>
                    </div>
                    <div>
                        <h4 className="font-medium text-blue-400 mb-2">Telegram Bot</h4>
                        <ol className="list-decimal list-inside space-y-1 text-zinc-400">
                            <li>Message <a href="https://t.me/BotFather" target="_blank" className="text-primary hover:underline">@BotFather</a></li>
                            <li>Create a new bot with /newbot</li>
                            <li>Copy the bot token</li>
                            <li>Add <code className="text-white">TELEGRAM_BOT_TOKEN=your_token</code> to .env</li>
                            <li>Start a chat with your bot</li>
                        </ol>
                    </div>
                </div>
            </motion.div>

            {/* Reply Logs */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="glass-panel p-6"
            >
                <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold flex items-center gap-2">
                        <Clock size={20} className="text-primary" />
                        Recent Replies
                    </h3>
                    <button
                        onClick={fetchLogs}
                        className="p-2 hover:bg-white/10 rounded-lg"
                    >
                        <RefreshCcw size={16} />
                    </button>
                </div>

                {logs.length > 0 ? (
                    <div className="space-y-2 max-h-72 overflow-y-auto">
                        {logs.map((log, i) => (
                            <div key={i} className="p-3 rounded-lg bg-white/5 text-sm">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className={`px-2 py-0.5 rounded text-xs ${log.platform === 'discord' ? 'bg-blue-500/20 text-blue-400' : 'bg-sky-500/20 text-sky-400'
                                        }`}>
                                        {log.platform}
                                    </span>
                                    <span className="text-zinc-400">{log.user}</span>
                                    <span className="text-zinc-600 text-xs ml-auto">
                                        {new Date(log.timestamp).toLocaleTimeString()}
                                    </span>
                                </div>
                                <p className="text-zinc-300">"{log.message}"</p>
                                <p className="text-primary mt-1">→ {log.response}</p>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-center py-8 text-zinc-500">
                        <Zap size={32} className="mx-auto mb-2 opacity-30" />
                        <p>No replies yet. Start a bot to see activity!</p>
                    </div>
                )}
            </motion.div>
        </div>
    );
};
