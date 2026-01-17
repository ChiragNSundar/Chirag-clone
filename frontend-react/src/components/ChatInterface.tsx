import { useState, useRef, useEffect } from 'react';
import { Send, User, Bot, ThumbsUp, ThumbsDown, Eye, EyeOff, Brain } from 'lucide-react';
import { api } from '../services/api';
import clsx from 'clsx';
import { Avatar3D } from './Avatar3D';
import { ThinkingBubble, ThinkingIndicator } from './ThinkingBubble';

interface ThinkingStep {
    step: number;
    content: string;
}

interface ThinkingData {
    thinking: string;
    steps: ThinkingStep[];
    has_thinking: boolean;
}

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    confidence?: number;
    mood?: any;
    thinking?: ThinkingData;
}

export const ChatInterface = () => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isThinking, setIsThinking] = useState(false);
    const [sessionId] = useState(() => 'session_' + Math.random().toString(36).substr(2, 9));
    const [showThinking, setShowThinking] = useState(true);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Avatar state
    const [showAvatar, setShowAvatar] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [currentSpeechText, setCurrentSpeechText] = useState('');

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = async () => {
        if (!input.trim() || isLoading) return;

        const userMsg: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: input,
            timestamp: new Date()
        };

        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setIsLoading(true);
        setIsThinking(true);

        try {
            const response = await api.sendMessage(userMsg.content, sessionId);

            setIsThinking(false);

            const botMsg: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: response.response,
                timestamp: new Date(),
                confidence: response.confidence,
                mood: response.mood,
                thinking: response.thinking
            };

            setMessages(prev => [...prev, botMsg]);

            // Trigger avatar lip-sync animation
            setCurrentSpeechText(response.response);
            setIsSpeaking(true);

            // Calculate approximate speaking duration (60ms per character)
            const speakingDuration = Math.min(response.response.length * 60, 10000);
            setTimeout(() => {
                setIsSpeaking(false);
            }, speakingDuration);
        } catch (error) {
            console.error(error);
            setIsThinking(false);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex h-full max-w-6xl mx-auto p-4 gap-4">
            {/* Avatar Panel */}
            <div className="flex flex-col items-center gap-2">
                <Avatar3D
                    speaking={isSpeaking}
                    text={currentSpeechText}
                    visible={showAvatar}
                />
                <button
                    onClick={() => setShowAvatar(!showAvatar)}
                    className="flex items-center gap-2 px-3 py-1.5 text-xs bg-zinc-800/50 hover:bg-zinc-700 border border-white/10 rounded-lg text-zinc-400 hover:text-white transition-colors"
                >
                    {showAvatar ? <EyeOff size={14} /> : <Eye size={14} />}
                    {showAvatar ? 'Hide Avatar' : 'Show Avatar'}
                </button>
            </div>

            {/* Chat Panel */}
            <div className="flex-1 flex flex-col gap-4">
                {/* Thinking Toggle */}
                <div className="flex justify-end">
                    <button
                        onClick={() => setShowThinking(!showThinking)}
                        className={clsx(
                            "flex items-center gap-2 px-3 py-1.5 text-xs rounded-lg transition-colors",
                            showThinking
                                ? "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                                : "bg-zinc-800/50 text-zinc-400 border border-white/10"
                        )}
                    >
                        <Brain size={14} />
                        {showThinking ? 'Thinking: On' : 'Thinking: Off'}
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto space-y-4 pr-2">
                    {messages.length === 0 && (
                        <div className="h-full flex flex-col items-center justify-center text-zinc-500 opacity-50">
                            <Bot size={48} className="mb-4" />
                            <p>Start chatting with your Clone!</p>
                        </div>
                    )}

                    {messages.map((msg) => (
                        <div key={msg.id}>
                            {/* Show thinking bubble before assistant message */}
                            {msg.role === 'assistant' && msg.thinking?.has_thinking && (
                                <ThinkingBubble
                                    thinking={msg.thinking.thinking}
                                    steps={msg.thinking.steps}
                                    isVisible={showThinking}
                                />
                            )}

                            <div
                                className={clsx(
                                    "flex gap-3 max-w-[80%]",
                                    msg.role === 'user' ? "ml-auto flex-row-reverse" : ""
                                )}
                            >
                                <div className={clsx(
                                    "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
                                    msg.role === 'user' ? "bg-primary" : "bg-accent"
                                )}>
                                    {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                                </div>

                                <div className={clsx(
                                    "p-3 rounded-2xl text-sm leading-relaxed",
                                    msg.role === 'user'
                                        ? "bg-primary text-white rounded-tr-none"
                                        : "bg-surface border border-white/10 rounded-tl-none"
                                )}>
                                    <p>{msg.content}</p>

                                    {msg.role === 'assistant' && (
                                        <div className="mt-2 pt-2 border-t border-white/5 flex items-center justify-between text-xs text-zinc-500 gap-4">
                                            <span>{msg.mood?.emoji} {msg.confidence && Math.round(msg.confidence * 100)}%</span>
                                            <div className="flex gap-2">
                                                <button className="hover:text-green-400"><ThumbsUp size={12} /></button>
                                                <button className="hover:text-red-400"><ThumbsDown size={12} /></button>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}

                    {isThinking && (
                        <div className="flex gap-3">
                            <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center">
                                <Bot size={16} />
                            </div>
                            <div className="bg-surface rounded-2xl rounded-tl-none border border-white/10">
                                <ThinkingIndicator />
                            </div>
                        </div>
                    )}

                    {isLoading && !isThinking && (
                        <div className="flex gap-3">
                            <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center">
                                <Bot size={16} />
                            </div>
                            <div className="bg-surface p-3 rounded-2xl rounded-tl-none border border-white/10 flex items-center gap-1">
                                <span className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce"></span>
                                <span className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce delay-75"></span>
                                <span className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce delay-150"></span>
                            </div>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>

                <div className="bg-surface/50 backdrop-blur-md border border-white/10 rounded-xl p-2 flex gap-2">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                        placeholder="Type a message..."
                        className="flex-1 bg-transparent border-none outline-none px-4 text-white placeholder-zinc-500"
                    />
                    <button
                        onClick={handleSend}
                        disabled={!input.trim() || isLoading}
                        className="p-2 bg-primary hover:bg-primary/90 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <Send size={20} />
                    </button>
                </div>
            </div>
        </div>
    );
};
