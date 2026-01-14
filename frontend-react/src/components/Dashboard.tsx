import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, Area, AreaChart
} from 'recharts';
import {
    Brain, MessageSquare, Zap, Smile, TrendingUp, Database,
    Activity, Users, FileText, Clock, Target, Award
} from 'lucide-react';

interface AnalyticsData {
    training: {
        total_examples: number;
        sources: Record<string, number>;
        recent_activity: any[];
    };
    personality: {
        facts_count: number;
        quirks_count: number;
        emoji_count: number;
        avg_message_length: number;
        tone_markers: Record<string, number>;
        common_phrases: string[];
        top_emojis: Record<string, number>;
    };
    learning_progress: {
        personality_score: number;
        data_sources_count: number;
    };
}

const CHART_COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899', '#84cc16'];

const StatCard = ({ icon: Icon, title, value, subtitle, color = 'primary', trend }: {
    icon: React.ElementType;
    title: string;
    value: string | number;
    subtitle?: string;
    color?: string;
    trend?: number;
}) => (
    <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel p-5"
    >
        <div className="flex items-start justify-between">
            <div className={`p-3 rounded-xl bg-${color === 'primary' ? 'primary' : color}/20`}>
                <Icon size={22} className={`text-${color === 'primary' ? 'primary' : color}`} />
            </div>
            {trend !== undefined && (
                <span className={`text-sm ${trend >= 0 ? 'text-green-400' : 'text-red-400'} flex items-center gap-1`}>
                    <TrendingUp size={14} className={trend < 0 ? 'rotate-180' : ''} />
                    {Math.abs(trend)}%
                </span>
            )}
        </div>
        <div className="mt-4">
            <p className="text-2xl font-bold">{value}</p>
            <p className="text-sm text-zinc-400">{title}</p>
            {subtitle && <p className="text-xs text-zinc-500 mt-1">{subtitle}</p>}
        </div>
    </motion.div>
);

const ProgressRing = ({ progress, size = 120, strokeWidth = 8 }: { progress: number; size?: number; strokeWidth?: number }) => {
    const radius = (size - strokeWidth) / 2;
    const circumference = radius * 2 * Math.PI;
    const offset = circumference - (progress / 100) * circumference;

    return (
        <div className="relative" style={{ width: size, height: size }}>
            <svg width={size} height={size} className="-rotate-90">
                <circle cx={size / 2} cy={size / 2} r={radius} strokeWidth={strokeWidth} stroke="#27272a" fill="none" />
                <circle
                    cx={size / 2} cy={size / 2} r={radius} strokeWidth={strokeWidth}
                    stroke="url(#gradient)" fill="none"
                    strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset}
                    className="transition-all duration-1000"
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
                <span className="text-xs text-zinc-400">Complete</span>
            </div>
        </div>
    );
};

export const Dashboard = () => {
    const [data, setData] = useState<AnalyticsData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await fetch('http://localhost:8000/api/analytics/detailed');
                const result = await res.json();
                setData(result);
            } catch (e) {
                console.error('Failed to fetch analytics:', e);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    // Prepare chart data
    const sourceChartData = data ? Object.entries(data.training.sources).map(([name, value]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        value
    })) : [];

    const emojiChartData = data ? Object.entries(data.personality.top_emojis).map(([emoji, count]) => ({
        emoji,
        count
    })) : [];

    const metricsData = [
        { name: 'Facts', value: data?.personality.facts_count || 0 },
        { name: 'Quirks', value: data?.personality.quirks_count || 0 },
        { name: 'Emojis', value: data?.personality.emoji_count || 0 },
        { name: 'Examples', value: data?.training.total_examples || 0 },
    ];

    const learningProgressData = [
        { name: 'Week 1', value: 10 },
        { name: 'Week 2', value: 25 },
        { name: 'Week 3', value: 45 },
        { name: 'Week 4', value: data?.learning_progress.personality_score || 0 },
    ];

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center">
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="text-center"
                >
                    <Brain className="w-16 h-16 mx-auto text-primary animate-pulse" />
                    <p className="mt-4 text-zinc-400">Loading analytics...</p>
                </motion.div>
            </div>
        );
    }

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto">
            {/* Header */}
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
            >
                <h1 className="text-2xl font-bold flex items-center gap-2">
                    <Activity className="text-primary" />
                    Analytics Dashboard
                </h1>
                <p className="text-zinc-400">Your Digital Twin's learning progress and personality insights</p>
            </motion.div>

            {/* Key Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard
                    icon={Database}
                    title="Training Examples"
                    value={data?.training.total_examples || 0}
                    subtitle="Total data points"
                    color="primary"
                />
                <StatCard
                    icon={FileText}
                    title="Personal Facts"
                    value={data?.personality.facts_count || 0}
                    subtitle="Stored knowledge"
                    color="green"
                />
                <StatCard
                    icon={Zap}
                    title="Unique Quirks"
                    value={data?.personality.quirks_count || 0}
                    subtitle="Communication patterns"
                    color="purple"
                />
                <StatCard
                    icon={Smile}
                    title="Emoji Patterns"
                    value={data?.personality.emoji_count || 0}
                    subtitle="Expression styles"
                    color="yellow"
                />
            </div>

            {/* Main Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Personality Completion */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="glass-panel p-6"
                >
                    <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                        <Target size={20} className="text-primary" />
                        Personality Completion
                    </h3>
                    <div className="flex flex-col items-center">
                        <ProgressRing progress={data?.learning_progress.personality_score || 0} size={160} />
                        <p className="mt-4 text-sm text-zinc-400 text-center">
                            {data?.learning_progress.personality_score || 0 < 30 ? 'Just getting started! Upload more data.' :
                                data?.learning_progress.personality_score || 0 < 70 ? 'Making good progress on learning you.' :
                                    'Excellent! Your clone knows you well.'}
                        </p>
                    </div>
                </motion.div>

                {/* Data Sources Pie Chart */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="glass-panel p-6"
                >
                    <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                        <Users size={20} className="text-primary" />
                        Data Sources Distribution
                    </h3>
                    {sourceChartData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={200}>
                            <PieChart>
                                <Pie
                                    data={sourceChartData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={50}
                                    outerRadius={80}
                                    paddingAngle={5}
                                    dataKey="value"
                                    label={({ name }) => name}
                                >
                                    {sourceChartData.map((_, i) => (
                                        <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                                    ))}
                                </Pie>
                                <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #27272a', borderRadius: '8px' }} />
                            </PieChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="h-48 flex items-center justify-center text-zinc-500">
                            No data sources yet. Start training!
                        </div>
                    )}
                </motion.div>

                {/* Learning Progress Area Chart */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="glass-panel p-6"
                >
                    <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                        <TrendingUp size={20} className="text-primary" />
                        Learning Progress
                    </h3>
                    <ResponsiveContainer width="100%" height={200}>
                        <AreaChart data={learningProgressData}>
                            <defs>
                                <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8} />
                                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                            <XAxis dataKey="name" stroke="#71717a" fontSize={12} />
                            <YAxis stroke="#71717a" fontSize={12} />
                            <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #27272a', borderRadius: '8px' }} />
                            <Area type="monotone" dataKey="value" stroke="#3b82f6" fillOpacity={1} fill="url(#colorValue)" />
                        </AreaChart>
                    </ResponsiveContainer>
                </motion.div>
            </div>

            {/* Bottom Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Metrics Bar Chart */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="glass-panel p-6"
                >
                    <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                        <Award size={20} className="text-primary" />
                        Knowledge Metrics
                    </h3>
                    <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={metricsData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                            <XAxis dataKey="name" stroke="#71717a" fontSize={12} />
                            <YAxis stroke="#71717a" fontSize={12} />
                            <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #27272a', borderRadius: '8px' }} />
                            <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                                {metricsData.map((_, i) => (
                                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </motion.div>

                {/* Top Emojis */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="glass-panel p-6"
                >
                    <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                        <Smile size={20} className="text-primary" />
                        Top Emoji Patterns
                    </h3>
                    {emojiChartData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={250}>
                            <BarChart data={emojiChartData} layout="vertical">
                                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                                <XAxis type="number" stroke="#71717a" fontSize={12} />
                                <YAxis dataKey="emoji" type="category" stroke="#71717a" fontSize={18} width={40} />
                                <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #27272a', borderRadius: '8px' }} />
                                <Bar dataKey="count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="h-64 flex items-center justify-center text-zinc-500 flex-col gap-2">
                            <Smile size={40} className="opacity-30" />
                            <p>No emoji patterns detected yet</p>
                        </div>
                    )}
                </motion.div>
            </div>

            {/* Common Phrases */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="glass-panel p-6"
            >
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                    <MessageSquare size={20} className="text-primary" />
                    Your Signature Phrases
                </h3>
                <div className="flex flex-wrap gap-2">
                    {(data?.personality.common_phrases || []).length > 0 ? (
                        data?.personality.common_phrases.map((phrase, i) => (
                            <span
                                key={i}
                                className="px-3 py-1.5 rounded-full text-sm"
                                style={{
                                    background: `${CHART_COLORS[i % CHART_COLORS.length]}20`,
                                    color: CHART_COLORS[i % CHART_COLORS.length],
                                    border: `1px solid ${CHART_COLORS[i % CHART_COLORS.length]}40`
                                }}
                            >
                                "{phrase}"
                            </span>
                        ))
                    ) : (
                        <p className="text-zinc-500">No phrases detected yet. Chat or upload more data!</p>
                    )}
                </div>
            </motion.div>

            {/* Quick Stats Footer */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="glass-panel p-4 flex items-center justify-between"
            >
                <div className="flex items-center gap-4">
                    <Clock size={16} className="text-zinc-500" />
                    <span className="text-sm text-zinc-400">
                        Avg message length: <span className="text-white font-medium">{data?.personality.avg_message_length || 0} characters</span>
                    </span>
                </div>
                <div className="flex items-center gap-4">
                    <Brain size={16} className="text-zinc-500" />
                    <span className="text-sm text-zinc-400">
                        Data sources: <span className="text-white font-medium">{data?.learning_progress.data_sources_count || 0} platforms</span>
                    </span>
                </div>
            </motion.div>
        </div>
    );
};
