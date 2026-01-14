import { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Upload, MessageSquare, BookOpen,
    Lock, Plus, Trash2, CheckCircle, AlertCircle,
    RefreshCcw, PenLine, Instagram, Hash
} from 'lucide-react';
import { api } from '../services/api';

interface TrainingCenterProps {
    isAuthenticated: boolean;
    onAuthenticate: () => void;
}

type TabType = 'chats' | 'journal' | 'facts' | 'examples';

const UploadCard = ({
    title,
    icon: Icon,
    description,
    accept,
    fieldName,
    fieldLabel,
    endpoint
}: {
    title: string;
    icon: React.ElementType;
    description: string;
    accept: string;
    fieldName: string;
    fieldLabel: string;
    endpoint: string;
}) => {
    const [uploading, setUploading] = useState(false);
    const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);
    const [fieldValue, setFieldValue] = useState('');
    const fileRef = useRef<HTMLInputElement>(null);

    const handleUpload = async () => {
        const file = fileRef.current?.files?.[0];
        if (!file || !fieldValue.trim()) return;

        setUploading(true);
        setResult(null);

        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append(fieldName, fieldValue);

            const response = await fetch(`http://localhost:8000${endpoint}`, {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                setResult({ success: true, message: `Added ${data.training_examples_added} examples` });
                setFieldValue('');
                if (fileRef.current) fileRef.current.value = '';
            } else {
                setResult({ success: false, message: data.detail || 'Upload failed' });
            }
        } catch (e) {
            setResult({ success: false, message: 'Upload failed' });
        } finally {
            setUploading(false);
        }
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-panel p-6"
        >
            <div className="flex items-start gap-4 mb-4">
                <div className="p-3 rounded-xl bg-primary/20 text-primary">
                    <Icon size={24} />
                </div>
                <div>
                    <h3 className="font-semibold text-lg">{title}</h3>
                    <p className="text-sm text-zinc-400">{description}</p>
                </div>
            </div>

            <div className="space-y-3">
                <input
                    type="text"
                    placeholder={fieldLabel}
                    value={fieldValue}
                    onChange={(e) => setFieldValue(e.target.value)}
                    className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-primary"
                />
                <input
                    ref={fileRef}
                    type="file"
                    accept={accept}
                    className="w-full text-sm text-zinc-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-primary file:text-white hover:file:bg-primary/90 file:cursor-pointer"
                />
                <button
                    onClick={handleUpload}
                    disabled={uploading || !fieldValue.trim()}
                    className="w-full py-2 bg-primary hover:bg-primary/90 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                    {uploading ? <RefreshCcw className="animate-spin" size={16} /> : <Upload size={16} />}
                    {uploading ? 'Processing...' : 'Upload & Train'}
                </button>
            </div>

            <AnimatePresence>
                {result && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className={`mt-3 p-3 rounded-lg flex items-center gap-2 text-sm ${result.success ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                            }`}
                    >
                        {result.success ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
                        {result.message}
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
};

export const TrainingCenter = ({ isAuthenticated, onAuthenticate }: TrainingCenterProps) => {
    const [activeTab, setActiveTab] = useState<TabType>('chats');
    const [journalText, setJournalText] = useState('');
    const [factText, setFactText] = useState('');
    const [facts, setFacts] = useState<string[]>([]);
    const [exampleContext, setExampleContext] = useState('');
    const [exampleResponse, setExampleResponse] = useState('');
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

    const loadFacts = async () => {
        try {
            const data = await api.getFacts();
            setFacts(data.facts || []);
        } catch (e) {
            console.error(e);
        }
    };

    const addJournalEntry = async () => {
        if (!journalText.trim()) return;
        setLoading(true);
        try {
            await api.addJournalEntry(journalText);
            setMessage({ type: 'success', text: 'Thought saved!' });
            setJournalText('');
        } catch {
            setMessage({ type: 'error', text: 'Failed to save' });
        } finally {
            setLoading(false);
        }
    };

    const addFact = async () => {
        if (!factText.trim()) return;
        setLoading(true);
        try {
            const data = await api.addFact(factText);
            setFacts(data.facts || []);
            setFactText('');
            setMessage({ type: 'success', text: 'Fact added!' });
        } catch {
            setMessage({ type: 'error', text: 'Failed to add fact' });
        } finally {
            setLoading(false);
        }
    };

    const deleteFact = async (index: number) => {
        try {
            const data = await api.deleteFact(index);
            setFacts(data.facts || []);
        } catch (e) {
            console.error(e);
        }
    };

    const addExample = async () => {
        if (!exampleContext.trim() || !exampleResponse.trim()) return;
        setLoading(true);
        try {
            await api.addTrainingExample(exampleContext, exampleResponse);
            setMessage({ type: 'success', text: 'Example added!' });
            setExampleContext('');
            setExampleResponse('');
        } catch {
            setMessage({ type: 'error', text: 'Failed to add example' });
        } finally {
            setLoading(false);
        }
    };

    if (!isAuthenticated) {
        return <TrainingAuth onSuccess={onAuthenticate} />;
    }

    const tabs = [
        { id: 'chats', label: 'Chat Uploads', icon: Upload },
        { id: 'journal', label: 'Journal', icon: PenLine },
        { id: 'facts', label: 'Facts', icon: BookOpen },
        { id: 'examples', label: 'Examples', icon: MessageSquare },
    ];

    return (
        <div className="p-6 max-w-5xl mx-auto">
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-6"
            >
                <h1 className="text-2xl font-bold flex items-center gap-2">
                    <Lock size={24} className="text-primary" />
                    Training Center
                </h1>
                <p className="text-zinc-500">Teach your digital twin how to be you</p>
            </motion.div>

            {/* Tabs */}
            <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
                {tabs.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => {
                            setActiveTab(tab.id as TabType);
                            if (tab.id === 'facts') loadFacts();
                        }}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all whitespace-nowrap ${activeTab === tab.id
                            ? 'bg-primary text-white'
                            : 'bg-white/5 text-zinc-400 hover:bg-white/10'
                            }`}
                    >
                        <tab.icon size={16} />
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Message */}
            <AnimatePresence>
                {message && (
                    <motion.div
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className={`mb-4 p-3 rounded-lg flex items-center gap-2 ${message.type === 'success' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                            }`}
                    >
                        {message.type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
                        {message.text}
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Content */}
            {activeTab === 'chats' && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <UploadCard
                        title="WhatsApp"
                        icon={MessageSquare}
                        description="Export your WhatsApp chat and upload the .txt file"
                        accept=".txt"
                        fieldName="your_name"
                        fieldLabel="Your name in the chat"
                        endpoint="/api/training/upload/whatsapp"
                    />
                    <UploadCard
                        title="Instagram"
                        icon={Instagram}
                        description="Download your data from Instagram and upload the messages JSON"
                        accept=".json"
                        fieldName="your_username"
                        fieldLabel="Your Instagram username"
                        endpoint="/api/training/upload/instagram"
                    />
                    <UploadCard
                        title="Discord"
                        icon={Hash}
                        description="Use a Discord data exporter and upload the JSON"
                        accept=".json,.txt"
                        fieldName="your_username"
                        fieldLabel="Your Discord username"
                        endpoint="/api/training/upload/discord"
                    />
                </div>
            )}

            {activeTab === 'journal' && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="glass-panel p-6 max-w-2xl"
                >
                    <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                        <PenLine size={20} className="text-primary" />
                        Write Your Thoughts
                    </h3>
                    <p className="text-sm text-zinc-400 mb-4">
                        Share random thoughts, opinions, or daily reflections. This helps me understand how you think.
                    </p>
                    <textarea
                        value={journalText}
                        onChange={(e) => setJournalText(e.target.value)}
                        placeholder="What's on your mind? Write freely..."
                        className="w-full h-40 px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-primary resize-none"
                    />
                    <button
                        onClick={addJournalEntry}
                        disabled={loading || !journalText.trim()}
                        className="mt-4 px-6 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg disabled:opacity-50 flex items-center gap-2"
                    >
                        {loading ? <RefreshCcw className="animate-spin" size={16} /> : <Plus size={16} />}
                        Save Thought
                    </button>
                </motion.div>
            )}

            {activeTab === 'facts' && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="glass-panel p-6 max-w-2xl"
                >
                    <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                        <BookOpen size={20} className="text-primary" />
                        Personal Facts
                    </h3>
                    <div className="flex gap-2 mb-4">
                        <input
                            type="text"
                            value={factText}
                            onChange={(e) => setFactText(e.target.value)}
                            placeholder="Add a fact about yourself..."
                            className="flex-1 px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-primary"
                        />
                        <button
                            onClick={addFact}
                            disabled={loading || !factText.trim()}
                            className="px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg disabled:opacity-50"
                        >
                            <Plus size={20} />
                        </button>
                    </div>
                    <ul className="space-y-2">
                        {facts.map((fact, i) => (
                            <li key={i} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                                <span className="text-zinc-300">{fact}</span>
                                <button
                                    onClick={() => deleteFact(i)}
                                    className="text-red-400 hover:text-red-300"
                                >
                                    <Trash2 size={16} />
                                </button>
                            </li>
                        ))}
                        {facts.length === 0 && (
                            <p className="text-zinc-500 text-center py-4">No facts yet. Add some!</p>
                        )}
                    </ul>
                </motion.div>
            )}

            {activeTab === 'examples' && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="glass-panel p-6 max-w-2xl"
                >
                    <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                        <MessageSquare size={20} className="text-primary" />
                        Training Examples
                    </h3>
                    <p className="text-sm text-zinc-400 mb-4">
                        Provide example conversations showing how you'd respond to messages.
                    </p>
                    <div className="space-y-3">
                        <div>
                            <label className="text-sm text-zinc-400 mb-1 block">Someone says:</label>
                            <input
                                type="text"
                                value={exampleContext}
                                onChange={(e) => setExampleContext(e.target.value)}
                                placeholder="e.g. 'Hey, what's up?'"
                                className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-primary"
                            />
                        </div>
                        <div>
                            <label className="text-sm text-zinc-400 mb-1 block">You respond:</label>
                            <input
                                type="text"
                                value={exampleResponse}
                                onChange={(e) => setExampleResponse(e.target.value)}
                                placeholder="e.g. 'Not much, just chilling. You?'"
                                className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-primary"
                            />
                        </div>
                        <button
                            onClick={addExample}
                            disabled={loading || !exampleContext.trim() || !exampleResponse.trim()}
                            className="w-full py-2 bg-primary hover:bg-primary/90 text-white rounded-lg disabled:opacity-50 flex items-center justify-center gap-2"
                        >
                            {loading ? <RefreshCcw className="animate-spin" size={16} /> : <Plus size={16} />}
                            Add Example
                        </button>
                    </div>
                </motion.div>
            )}
        </div>
    );
};

const TrainingAuth = ({ onSuccess }: { onSuccess: () => void }) => {
    const [pin, setPin] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            const formData = new FormData();
            formData.append('pin', pin);

            const response = await fetch('http://localhost:8000/api/training/auth', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                onSuccess();
            } else {
                setError('Invalid PIN');
            }
        } catch {
            setError('Connection error');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="h-full flex items-center justify-center">
            <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="glass-panel p-8 w-full max-w-sm"
            >
                <div className="text-center mb-6">
                    <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-primary/20 flex items-center justify-center">
                        <Lock size={32} className="text-primary" />
                    </div>
                    <h2 className="text-xl font-bold">Training Center</h2>
                    <p className="text-sm text-zinc-500 mt-1">Enter PIN to access</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <input
                        type="password"
                        value={pin}
                        onChange={(e) => setPin(e.target.value)}
                        placeholder="Enter PIN"
                        className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white text-center text-2xl tracking-widest placeholder-zinc-500 focus:outline-none focus:border-primary"
                        maxLength={8}
                    />
                    {error && (
                        <p className="text-red-400 text-sm text-center">{error}</p>
                    )}
                    <button
                        type="submit"
                        disabled={loading || !pin}
                        className="w-full py-3 bg-primary hover:bg-primary/90 text-white rounded-lg disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                        {loading ? <RefreshCcw className="animate-spin" size={16} /> : <Lock size={16} />}
                        Unlock
                    </button>
                </form>
                <p className="text-xs text-zinc-600 text-center mt-4">Default PIN: 1234</p>
            </motion.div>
        </div>
    );
};
