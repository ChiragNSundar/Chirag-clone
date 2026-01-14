import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
    Sparkles,
    BarChart3,
    MessageCircle,
    RefreshCcw,
    BookOpen
} from 'lucide-react';
import { api, type ProfileData } from '../services/api';

const ToneBar = ({ name, value }: { name: string; value: number }) => (
    <div className="space-y-1">
        <div className="flex justify-between text-sm">
            <span className="capitalize text-zinc-300">{name}</span>
            <span className="text-zinc-500">{Math.round(value * 100)}%</span>
        </div>
        <div className="h-2 bg-white/10 rounded-full overflow-hidden">
            <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${value * 100}%` }}
                transition={{ duration: 1, delay: 0.2 }}
                className="h-full bg-gradient-to-r from-primary to-accent"
            />
        </div>
    </div>
);

const Section = ({
    title,
    icon: Icon,
    children,
    delay = 0
}: {
    title: string;
    icon: React.ElementType;
    children: React.ReactNode;
    delay?: number;
}) => (
    <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay }}
        className="glass-panel p-6"
    >
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Icon size={20} className="text-primary" />
            {title}
        </h3>
        {children}
    </motion.div>
);

export const ProfilePage = () => {
    const [profile, setProfile] = useState<ProfileData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchProfile = async () => {
            try {
                const data = await api.getProfile();
                setProfile(data);
            } catch (e) {
                console.error(e);
            } finally {
                setLoading(false);
            }
        };
        fetchProfile();
    }, []);

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center">
                <RefreshCcw className="animate-spin text-primary" size={32} />
            </div>
        );
    }

    return (
        <div className="p-6 max-w-5xl mx-auto space-y-6">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="glass-panel p-8 relative overflow-hidden"
            >
                <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-accent/10" />
                <div className="relative z-10 flex items-start gap-6">
                    <div className="w-20 h-20 rounded-full bg-gradient-to-tr from-primary to-accent flex items-center justify-center text-4xl shrink-0">
                        {profile?.name?.charAt(0) || '?'}
                    </div>
                    <div className="flex-1">
                        <h1 className="text-3xl font-bold mb-2">{profile?.name || 'Unknown'}</h1>
                        <p className="text-zinc-300 leading-relaxed max-w-2xl">
                            {profile?.summary || 'No summary available yet. Train more to generate a personality profile!'}
                        </p>
                        <div className="mt-4 flex flex-wrap gap-2">
                            <span className="px-3 py-1 bg-white/10 rounded-full text-sm text-zinc-300">
                                {profile?.training_examples || 0} training examples
                            </span>
                            <span className="px-3 py-1 bg-white/10 rounded-full text-sm text-zinc-300">
                                {profile?.facts?.length || 0} facts
                            </span>
                            <span className="px-3 py-1 bg-white/10 rounded-full text-sm text-zinc-300">
                                Avg. {Math.round(profile?.avg_message_length || 0)} chars/message
                            </span>
                        </div>
                    </div>
                </div>
            </motion.div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Section title="Communication Style" icon={BarChart3} delay={0.1}>
                    <div className="space-y-4">
                        {profile?.tone_markers && Object.entries(profile.tone_markers).map(([name, value]) => (
                            <ToneBar key={name} name={name} value={value} />
                        ))}
                    </div>
                </Section>

                <Section title="Signature Quirks" icon={Sparkles} delay={0.2}>
                    <div className="flex flex-wrap gap-2">
                        {profile?.quirks?.length ? (
                            profile.quirks.map((quirk, i) => (
                                <motion.span
                                    key={i}
                                    initial={{ opacity: 0, scale: 0 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    transition={{ delay: 0.3 + i * 0.05 }}
                                    className="px-3 py-1.5 bg-primary/20 text-primary border border-primary/30 rounded-full text-sm"
                                >
                                    "{quirk}"
                                </motion.span>
                            ))
                        ) : (
                            <p className="text-zinc-500">No quirks detected yet.</p>
                        )}
                    </div>
                </Section>

                <Section title="Favorite Emojis" icon={MessageCircle} delay={0.3}>
                    <div className="flex flex-wrap gap-3">
                        {profile?.emojis && Object.keys(profile.emojis).length ? (
                            Object.entries(profile.emojis).slice(0, 15).map(([emoji, count], i) => (
                                <motion.div
                                    key={i}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.4 + i * 0.03 }}
                                    className="flex flex-col items-center p-2 bg-white/5 rounded-lg hover:bg-white/10 transition-colors"
                                >
                                    <span className="text-2xl">{emoji}</span>
                                    <span className="text-xs text-zinc-500 mt-1">×{count}</span>
                                </motion.div>
                            ))
                        ) : (
                            <p className="text-zinc-500">No emoji patterns detected yet.</p>
                        )}
                    </div>
                </Section>

                <Section title="Known Facts" icon={BookOpen} delay={0.4}>
                    {profile?.facts?.length ? (
                        <ul className="space-y-2">
                            {profile.facts.map((fact, i) => (
                                <motion.li
                                    key={i}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.5 + i * 0.05 }}
                                    className="flex items-start gap-2 text-zinc-300"
                                >
                                    <span className="text-primary mt-1">•</span>
                                    {fact}
                                </motion.li>
                            ))}
                        </ul>
                    ) : (
                        <p className="text-zinc-500">No facts added yet. Add some in the training section!</p>
                    )}
                </Section>
            </div>
        </div>
    );
};
