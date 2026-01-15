import { useState } from 'react';
import { ChevronDown, ChevronUp, Brain, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface ThinkingStep {
    step: number;
    content: string;
}

interface ThinkingBubbleProps {
    thinking: string;
    steps: ThinkingStep[];
    isVisible?: boolean;
}

/**
 * ThinkingBubble - Displays the AI's inner monologue/reasoning process
 * Shows a collapsible view of the thinking steps before a response
 */
export function ThinkingBubble({ thinking, steps, isVisible = true }: ThinkingBubbleProps) {
    const [isExpanded, setIsExpanded] = useState(false);

    if (!isVisible || (!thinking && steps.length === 0)) {
        return null;
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="mb-3"
        >
            <div className="bg-gradient-to-r from-purple-500/10 to-indigo-500/10 border border-purple-500/20 rounded-xl overflow-hidden">
                {/* Header - Always visible */}
                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-purple-500/5 transition-colors"
                >
                    <div className="flex items-center gap-2">
                        <div className="relative">
                            <Brain size={16} className="text-purple-400" />
                            <Sparkles size={8} className="absolute -top-1 -right-1 text-yellow-400" />
                        </div>
                        <span className="text-sm font-medium text-purple-300">
                            Thinking Process
                        </span>
                        <span className="text-xs text-zinc-500">
                            ({steps.length} step{steps.length !== 1 ? 's' : ''})
                        </span>
                    </div>
                    {isExpanded ? (
                        <ChevronUp size={16} className="text-zinc-400" />
                    ) : (
                        <ChevronDown size={16} className="text-zinc-400" />
                    )}
                </button>

                {/* Expandable Content */}
                <AnimatePresence>
                    {isExpanded && (
                        <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                        >
                            <div className="px-4 pb-4 space-y-3">
                                {/* Inner Monologue */}
                                {thinking && (
                                    <div className="text-sm text-zinc-400 italic border-l-2 border-purple-500/30 pl-3">
                                        "{thinking}"
                                    </div>
                                )}

                                {/* Reasoning Steps */}
                                {steps.length > 0 && (
                                    <div className="space-y-2">
                                        {steps.map((step, index) => (
                                            <motion.div
                                                key={step.step || index}
                                                initial={{ opacity: 0, x: -10 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                transition={{ delay: index * 0.1 }}
                                                className="flex gap-3"
                                            >
                                                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-purple-500/20 flex items-center justify-center">
                                                    <span className="text-xs font-bold text-purple-400">
                                                        {step.step || index + 1}
                                                    </span>
                                                </div>
                                                <p className="text-sm text-zinc-300 pt-0.5">
                                                    {step.content}
                                                </p>
                                            </motion.div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </motion.div>
    );
}

/**
 * ThinkingIndicator - Shows animated dots while AI is thinking
 */
export function ThinkingIndicator() {
    return (
        <div className="flex items-center gap-2 px-4 py-2">
            <Brain size={16} className="text-purple-400 animate-pulse" />
            <span className="text-sm text-zinc-400">Thinking</span>
            <div className="flex gap-1">
                {[0, 1, 2].map((i) => (
                    <motion.span
                        key={i}
                        className="w-1.5 h-1.5 bg-purple-400 rounded-full"
                        animate={{
                            y: [0, -4, 0],
                            opacity: [0.5, 1, 0.5]
                        }}
                        transition={{
                            duration: 0.6,
                            repeat: Infinity,
                            delay: i * 0.15
                        }}
                    />
                ))}
            </div>
        </div>
    );
}
