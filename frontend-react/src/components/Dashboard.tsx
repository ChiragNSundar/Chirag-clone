import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
    MessageSquare,
    Brain,
    Smile,
    Zap,
    TrendingUp,
    RefreshCcw
} from 'lucide-react';
import { api, type DashboardStats } from '../services/api';
import clsx from 'clsx';

const StatCard = ({
    icon: Icon,
    label,
    value,
    color,
    delay = 0
}: {
    icon: React.ElementType;
    label: string;
    value: string | number;
    color: string;
    delay?: number;
}) => (
    <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay, duration: 0.5 }}
        className="glass-panel p-6 hover:scale-[1.02] transition-transform cursor-default"
    >
        <div className="flex items-start justify-between">
            <div>
                <p className="text-zinc-400 text-sm mb-1">{label}</p>
                <p className="text-3xl font-bold">{value}</p>
            </div>
            <div className={clsx("p-3 rounded-xl", color)}>
                <Icon size={24} />
            </div>
        </div>
    </motion.div>
);

const ProgressRing = ({ progress, size = 120 }: { progress: number; size?: number }) => {
    const strokeWidth = 8;
    const radius = (size - strokeWidth) / 2;
    const circumference = radius * 2 * Math.PI;
    const offset = circumference - (progress / 100) * circumference;

    return (
        <div className="relative" style={{ width: size, height: size }}>
            <svg width={size} height={size} className="-rotate-90">
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    strokeWidth={strokeWidth}
                    stroke="rgba(255,255,255,0.1)"
                    fill="none"
                />
                <motion.circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    strokeWidth={strokeWidth}
                    stroke="url(#gradient)"
                    fill="none"
                    strokeLinecap="round"
                    initial={{ strokeDashoffset: circumference }}
                    animate={{ strokeDashoffset: offset }}
                    transition={{ duration: 1.5, ease: "easeOut" }}
                    style={{ strokeDasharray: circumference }}
                />
                <defs>
                    <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="#3b82f6" />
                        <stop offset="100%" stopColor="#8b5cf6" />
                    </linearGradient>
                </defs>
            </svg>
            <div className="absolute inset-0 flex items-center justify-center flex-col">
                <span className="text-2xl font-bold">{progress}%</span>
                <span className="text-xs text-zinc-500">Complete</span>
            </div>
        </div>
    );
};

export const Dashboard = () => {
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchStats = async () => {
        setLoading(true);
        try {
            const data = await api.getDashboardStats();
            setStats(data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchStats();
    }, []);

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center">
                <RefreshCcw className="animate-spin text-primary" size={32} />
            </div>
        );
    }

    return (
        <div className="p-6 max-w-6xl mx-auto space-y-6">
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center justify-between"
            >
                <div>
                    <h1 className="text-2xl font-bold">Dashboard</h1>
                    <p className="text-zinc-500">Overview of your Digital Twin's learning progress</p>
                </div>
                <button
                    onClick={fetchStats}
                    className="p-2 rounded-lg bg-white/5 hover:bg-white/10 transition-colors"
                >
                    <RefreshCcw size={20} />
                </button>
            </motion.div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                    icon={MessageSquare}
                    label="Training Examples"
                    value={stats?.total_training_examples || 0}
                    color="bg-blue-500/20 text-blue-400"
                    delay={0.1}
                />
                <StatCard
                    icon={Brain}
                    label="Facts Learned"
                    value={stats?.facts_count || 0}
                    color="bg-purple-500/20 text-purple-400"
                    delay={0.2}
                />
                <StatCard
                    icon={Zap}
                    label="Quirks Detected"
                    value={stats?.quirks_count || 0}
                    color="bg-amber-500/20 text-amber-400"
                    delay={0.3}
                />
                <StatCard
                    icon={Smile}
                    label="Unique Emojis"
                    value={stats?.emoji_count || 0}
                    color="bg-green-500/20 text-green-400"
                    delay={0.4}
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.5 }}
                    className="glass-panel p-6 flex flex-col items-center justify-center lg:col-span-1"
                >
                    <h3 className="text-lg font-semibold mb-4">Personality Completion</h3>
                    <ProgressRing progress={stats?.personality_completion || 0} />
                    <p className="text-sm text-zinc-400 mt-4 text-center">
                        Upload more chats or add facts to improve accuracy
                    </p>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.6 }}
                    className="glass-panel p-6 lg:col-span-2"
                >
                    <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                        <TrendingUp size={20} className="text-primary" />
                        Data Sources
                    </h3>
                    <div className="space-y-3">
                        {stats?.sources && Object.keys(stats.sources).length > 0 ? (
                            Object.entries(stats.sources).map(([source, count]) => (
                                <div key={source} className="flex items-center justify-between">
                                    <span className="capitalize text-zinc-300">{source.replace('_', ' ')}</span>
                                    <div className="flex items-center gap-3">
                                        <div className="w-32 h-2 bg-white/10 rounded-full overflow-hidden">
                                            <motion.div
                                                initial={{ width: 0 }}
                                                animate={{ width: `${Math.min(100, (count / (stats?.total_training_examples || 1)) * 100)}%` }}
                                                transition={{ duration: 1 }}
                                                className="h-full bg-gradient-to-r from-primary to-accent"
                                            />
                                        </div>
                                        <span className="text-sm text-zinc-500 w-8">{count}</span>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <p className="text-zinc-500 text-sm">No data sources yet. Start by uploading chats!</p>
                        )}
                    </div>
                </motion.div>
            </div>
        </div>
    );
};
