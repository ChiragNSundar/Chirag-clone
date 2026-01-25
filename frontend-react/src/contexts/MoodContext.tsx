import React, { createContext, useContext, useState, useEffect } from 'react';

type Mood = 'neutral' | 'happy' | 'thoughtful' | 'focused' | 'energetic';

interface MoodTheme {
    primary: string;
    secondary: string;
    accent: string;
    background: string;
}

const MOOD_THEMES: Record<Mood, MoodTheme> = {
    neutral: {
        primary: '#3b82f6', // blue-500
        secondary: '#64748b', // slate-500
        accent: '#8b5cf6', // violet-500
        background: '#18181b', // zinc-950
    },
    happy: {
        primary: '#f59e0b', // amber-500
        secondary: '#fcd34d', // amber-300
        accent: '#f43f5e', // rose-500
        background: '#1c1917', // stone-950
    },
    thoughtful: {
        primary: '#8b5cf6', // violet-500
        secondary: '#a78bfa', // violet-400
        accent: '#06b6d4', // cyan-500
        background: '#1e1b4b', // indigo-950
    },
    focused: {
        primary: '#10b981', // emerald-500
        secondary: '#34d399', // emerald-400
        accent: '#3b82f6', // blue-500
        background: '#022c22', // emerald-950
    },
    energetic: {
        primary: '#ef4444', // red-500
        secondary: '#f87171', // red-400
        accent: '#f59e0b', // amber-500
        background: '#450a0a', // red-950
    }
};

interface MoodContextType {
    currentMood: Mood;
    setMood: (mood: Mood) => void;
    theme: MoodTheme;
}

const MoodContext = createContext<MoodContextType | undefined>(undefined);

export const MoodProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [currentMood, setCurrentMood] = useState<Mood>('neutral');
    const [theme, setTheme] = useState<MoodTheme>(MOOD_THEMES.neutral);

    useEffect(() => {
        setTheme(MOOD_THEMES[currentMood]);

        // Update CSS variables for Tailwind or global styles
        const root = document.documentElement;
        const t = MOOD_THEMES[currentMood];

        root.style.setProperty('--color-primary', t.primary);
        root.style.setProperty('--color-secondary', t.secondary);
        root.style.setProperty('--color-accent', t.accent);
        // Note: Changing background typically affects body, handle carefully
    }, [currentMood]);

    return (
        <MoodContext.Provider value={{ currentMood, setMood: setCurrentMood, theme }}>
            {children}
        </MoodContext.Provider>
    );
};

export const useMood = () => {
    const context = useContext(MoodContext);
    if (!context) {
        throw new Error('useMood must be used within a MoodProvider');
    }
    return context;
};
