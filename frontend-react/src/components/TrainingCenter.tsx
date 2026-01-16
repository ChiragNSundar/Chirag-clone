import { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Upload, MessageSquare, BookOpen,
    Lock, Plus, Trash2, CheckCircle, AlertCircle,
    RefreshCcw, PenLine, Instagram, Hash, Brain, Search, Link, FileText
} from 'lucide-react';
import { api } from '../services/api';

interface TrainingCenterProps {
    isAuthenticated: boolean;
    onAuthenticate: () => void;
}

type TabType = 'chats' | 'train_chat' | 'journal' | 'documents' | 'facts' | 'brain';

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

    if (!isAuthenticated) {
        return <TrainingAuth onSuccess={onAuthenticate} />;
    }

    const tabs = [
        { id: 'chats', label: 'Chat Uploads', icon: Upload },
        { id: 'train_chat', label: 'Train by Chatting', icon: MessageSquare },
        { id: 'journal', label: 'Journal', icon: PenLine },
        { id: 'documents', label: 'Documents', icon: BookOpen },
        { id: 'facts', label: 'Facts', icon: BookOpen },
        { id: 'brain', label: 'Brain Station', icon: Brain },
    ];

    const [showResetConfirm, setShowResetConfirm] = useState(false);

    const resetAllLearning = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/training/reset', { method: 'DELETE' });
            if (res.ok) {
                setMessage({ type: 'success', text: 'All learning data has been reset!' });
                setFacts([]);
            } else {
                setMessage({ type: 'error', text: 'Failed to reset' });
            }
        } catch {
            setMessage({ type: 'error', text: 'Connection error' });
        } finally {
            setShowResetConfirm(false);
        }
    };

    return (
        <div className="p-6 max-w-5xl mx-auto">
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-6 flex items-start justify-between"
            >
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <Lock size={24} className="text-primary" />
                        Training Center
                    </h1>
                    <p className="text-zinc-500">Teach your digital twin how to be you</p>
                </div>
                <button
                    onClick={() => setShowResetConfirm(true)}
                    className="px-4 py-2 bg-red-500/20 text-red-400 hover:bg-red-500/30 rounded-lg text-sm flex items-center gap-2"
                >
                    <Trash2 size={16} />
                    Reset All
                </button>
            </motion.div>

            {/* Reset Confirmation Modal */}
            <AnimatePresence>
                {showResetConfirm && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
                        onClick={() => setShowResetConfirm(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.9 }}
                            animate={{ scale: 1 }}
                            exit={{ scale: 0.9 }}
                            className="glass-panel p-6 max-w-sm mx-4"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <h3 className="text-lg font-bold text-red-400 mb-2">Reset All Learning?</h3>
                            <p className="text-sm text-zinc-400 mb-4">
                                This will permanently delete all training data, facts, quirks, and personality data. This cannot be undone.
                            </p>
                            <div className="flex gap-2">
                                <button
                                    onClick={() => setShowResetConfirm(false)}
                                    className="flex-1 py-2 bg-white/10 hover:bg-white/20 rounded-lg"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={resetAllLearning}
                                    className="flex-1 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg"
                                >
                                    Reset Everything
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

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

            {activeTab === 'train_chat' && (
                <TrainByChattingTab />
            )}

            {activeTab === 'documents' && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="glass-panel p-6 max-w-2xl"
                >
                    <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                        <BookOpen size={20} className="text-primary" />
                        Upload Documents
                    </h3>
                    <p className="text-sm text-zinc-400 mb-4">
                        Upload PDFs, text files, or any documents that reflect how you write and think.
                    </p>
                    <DocumentUpload />
                </motion.div>
            )}

            {activeTab === 'brain' && (
                <BrainStationTab />
            )}
        </div>
    );
};

// Train by Chatting component - Bot asks, you answer
const TrainByChattingTab = () => {
    const [prompt, setPrompt] = useState('');
    const [response, setResponse] = useState('');
    const [loading, setLoading] = useState(false);
    const [learned, setLearned] = useState(0);

    const fetchPrompt = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/training/chat/prompt');
            const data = await res.json();
            setPrompt(data.prompt);
            setResponse('');
        } catch (e) {
            console.error(e);
        }
    };

    const submitResponse = async () => {
        if (!response.trim() || !prompt) return;
        setLoading(true);
        try {
            const res = await fetch('http://localhost:8000/api/training/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bot_message: prompt, user_response: response })
            });
            if (res.ok) {
                setLearned(prev => prev + 1);
                fetchPrompt(); // Get next prompt
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    // Fetch initial prompt
    if (!prompt) fetchPrompt();

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="glass-panel p-6 max-w-2xl"
        >
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <MessageSquare size={20} className="text-primary" />
                Train by Chatting
            </h3>
            <p className="text-sm text-zinc-400 mb-4">
                I'll ask you something, and you respond how YOU would. I'll learn from your answers!
            </p>

            {learned > 0 && (
                <div className="mb-4 p-2 bg-green-500/20 text-green-400 rounded-lg text-sm text-center">
                    ✓ {learned} responses learned this session
                </div>
            )}

            <div className="space-y-4">
                <div className="p-4 bg-white/5 rounded-lg border border-white/10">
                    <p className="text-sm text-zinc-400 mb-1">Someone asks you:</p>
                    <p className="text-lg">{prompt || 'Loading...'}</p>
                </div>

                <div>
                    <label className="text-sm text-zinc-400 mb-1 block">Your response:</label>
                    <textarea
                        value={response}
                        onChange={(e) => setResponse(e.target.value)}
                        placeholder="How would you respond?"
                        className="w-full h-24 px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-primary resize-none"
                    />
                </div>

                <div className="flex gap-2">
                    <button
                        onClick={submitResponse}
                        disabled={loading || !response.trim()}
                        className="flex-1 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                        {loading ? <RefreshCcw className="animate-spin" size={16} /> : <CheckCircle size={16} />}
                        Submit & Learn
                    </button>
                    <button
                        onClick={fetchPrompt}
                        className="px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg"
                    >
                        <RefreshCcw size={16} />
                    </button>
                </div>
            </div>
        </motion.div>
    );
};

// Document Upload component
const DocumentUpload = () => {
    const [uploading, setUploading] = useState(false);
    const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);
    const fileRef = useRef<HTMLInputElement>(null);

    const handleUpload = async () => {
        const file = fileRef.current?.files?.[0];
        if (!file) return;

        setUploading(true);
        setResult(null);

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('http://localhost:8000/api/training/upload/document', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                setResult({ success: true, message: `Processed ${data.characters_processed} characters` });
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
        <div className="space-y-4">
            <input
                ref={fileRef}
                type="file"
                accept=".pdf,.txt,.md,.doc,.docx"
                className="w-full text-sm text-zinc-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-primary file:text-white hover:file:bg-primary/90 file:cursor-pointer"
            />
            <button
                onClick={handleUpload}
                disabled={uploading}
                className="w-full py-2 bg-primary hover:bg-primary/90 text-white rounded-lg disabled:opacity-50 flex items-center justify-center gap-2"
            >
                {uploading ? <RefreshCcw className="animate-spin" size={16} /> : <Upload size={16} />}
                {uploading ? 'Processing...' : 'Upload & Learn'}
            </button>

            <AnimatePresence>
                {result && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className={`p-3 rounded-lg flex items-center gap-2 text-sm ${result.success ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                            }`}
                    >
                        {result.success ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
                        {result.message}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

// Brain Station - Knowledge management with drag-and-drop
const BrainStationTab = () => {
    const [documents, setDocuments] = useState<Array<{
        id: string;
        title: string;
        filename: string;
        doc_type: string;
        category: string;
        chunk_count: number;
        char_count: number;
        added_at: string;
    }>>([]);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState<Array<{
        content: string;
        filename: string;
        relevance: number;
    }>>([]);
    const [urlInput, setUrlInput] = useState('');
    const [textInput, setTextInput] = useState('');
    const [stats, setStats] = useState<{
        total_documents: number;
        total_chunks: number;
        total_characters: number;
    } | null>(null);
    const [dragActive, setDragActive] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Load documents and stats on mount
    const loadData = async () => {
        setLoading(true);
        try {
            const [docsRes, statsRes] = await Promise.all([
                fetch('http://localhost:8000/api/knowledge/documents'),
                fetch('http://localhost:8000/api/knowledge/stats')
            ]);
            const docs = await docsRes.json();
            const statsData = await statsRes.json();
            setDocuments(docs.documents || []);
            setStats(statsData);
        } catch (e) {
            console.error('Failed to load knowledge data:', e);
        } finally {
            setLoading(false);
        }
    };

    useState(() => { loadData(); });

    const handleDrag = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setDragActive(true);
        } else if (e.type === "dragleave") {
            setDragActive(false);
        }
    };

    const handleDrop = async (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);

        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            await uploadFile(e.dataTransfer.files[0]);
        }
    };

    const uploadFile = async (file: File) => {
        setUploading(true);
        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('category', 'general');

            const response = await fetch('http://localhost:8000/api/knowledge/upload', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();

            if (result.success) {
                await loadData();
            }
        } catch (e) {
            console.error('Upload error:', e);
        } finally {
            setUploading(false);
        }
    };

    const deleteDocument = async (docId: string) => {
        try {
            await fetch(`http://localhost:8000/api/knowledge/document/${docId}`, {
                method: 'DELETE'
            });
            await loadData();
        } catch (e) {
            console.error('Delete error:', e);
        }
    };

    const searchKnowledge = async () => {
        if (!searchQuery.trim()) return;
        setLoading(true);
        try {
            const response = await fetch('http://localhost:8000/api/knowledge/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: searchQuery, n_results: 5 })
            });
            const result = await response.json();
            setSearchResults(result.results || []);
        } catch (e) {
            console.error('Search error:', e);
        } finally {
            setLoading(false);
        }
    };

    const addFromUrl = async () => {
        if (!urlInput.trim()) return;
        setUploading(true);
        try {
            const response = await fetch('http://localhost:8000/api/knowledge/url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: urlInput })
            });
            if (response.ok) {
                setUrlInput('');
                await loadData();
            }
        } catch (e) {
            console.error('URL add error:', e);
        } finally {
            setUploading(false);
        }
    };

    const addFromText = async () => {
        if (!textInput.trim()) return;
        setUploading(true);
        try {
            const response = await fetch('http://localhost:8000/api/knowledge/text', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: textInput, title: 'Quick Note' })
            });
            if (response.ok) {
                setTextInput('');
                await loadData();
            }
        } catch (e) {
            console.error('Text add error:', e);
        } finally {
            setUploading(false);
        }
    };

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-6"
        >
            {/* Stats Header */}
            <div className="glass-panel p-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-3 rounded-xl bg-purple-500/20 text-purple-400">
                            <Brain size={24} />
                        </div>
                        <div>
                            <h3 className="font-semibold text-lg">Brain Station</h3>
                            <p className="text-sm text-zinc-400">Manage your twin's knowledge base</p>
                        </div>
                    </div>
                    {stats && (
                        <div className="flex gap-4 text-sm text-zinc-400">
                            <span>{stats.total_documents} docs</span>
                            <span>{stats.total_chunks} chunks</span>
                            <span>{(stats.total_characters / 1000).toFixed(1)}K chars</span>
                        </div>
                    )}
                </div>
            </div>

            {/* Drop Zone */}
            <div
                className={`glass-panel p-8 border-2 border-dashed transition-all ${dragActive ? 'border-purple-500 bg-purple-500/10' : 'border-white/10'
                    }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
            >
                <div className="text-center">
                    <FileText size={48} className="mx-auto mb-4 text-zinc-500" />
                    <p className="text-zinc-400 mb-2">
                        {uploading ? 'Uploading...' : 'Drop PDFs, TXT, or MD files here'}
                    </p>
                    <button
                        onClick={() => fileInputRef.current?.click()}
                        disabled={uploading}
                        className="text-primary hover:underline text-sm"
                    >
                        or click to browse
                    </button>
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf,.txt,.md"
                        className="hidden"
                        onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])}
                    />
                </div>
            </div>

            {/* Quick Add */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* URL Input */}
                <div className="glass-panel p-4">
                    <div className="flex items-center gap-2 mb-2">
                        <Link size={16} className="text-zinc-400" />
                        <span className="text-sm text-zinc-400">Add from URL</span>
                    </div>
                    <div className="flex gap-2">
                        <input
                            type="url"
                            value={urlInput}
                            onChange={(e) => setUrlInput(e.target.value)}
                            placeholder="https://example.com/article"
                            className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-primary"
                        />
                        <button
                            onClick={addFromUrl}
                            disabled={uploading || !urlInput.trim()}
                            className="px-3 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg disabled:opacity-50"
                        >
                            <Plus size={16} />
                        </button>
                    </div>
                </div>

                {/* Quick Text */}
                <div className="glass-panel p-4">
                    <div className="flex items-center gap-2 mb-2">
                        <FileText size={16} className="text-zinc-400" />
                        <span className="text-sm text-zinc-400">Quick text note</span>
                    </div>
                    <div className="flex gap-2">
                        <input
                            type="text"
                            value={textInput}
                            onChange={(e) => setTextInput(e.target.value)}
                            placeholder="Add a quick piece of knowledge..."
                            className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-primary"
                        />
                        <button
                            onClick={addFromText}
                            disabled={uploading || !textInput.trim()}
                            className="px-3 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg disabled:opacity-50"
                        >
                            <Plus size={16} />
                        </button>
                    </div>
                </div>
            </div>

            {/* Search */}
            <div className="glass-panel p-4">
                <div className="flex items-center gap-2 mb-3">
                    <Search size={16} className="text-zinc-400" />
                    <span className="text-sm text-zinc-400">Search Knowledge</span>
                </div>
                <div className="flex gap-2">
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && searchKnowledge()}
                        placeholder="Ask your knowledge base..."
                        className="flex-1 px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-primary"
                    />
                    <button
                        onClick={searchKnowledge}
                        disabled={loading || !searchQuery.trim()}
                        className="px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg disabled:opacity-50"
                    >
                        Search
                    </button>
                </div>

                {/* Search Results */}
                {searchResults.length > 0 && (
                    <div className="mt-4 space-y-2">
                        {searchResults.map((result, i) => (
                            <div key={i} className="p-3 bg-white/5 rounded-lg">
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-xs text-zinc-500">{result.filename}</span>
                                    <span className="text-xs text-purple-400">
                                        {(result.relevance * 100).toFixed(0)}% match
                                    </span>
                                </div>
                                <p className="text-sm text-zinc-300">{result.content}</p>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Document List */}
            <div className="glass-panel p-4">
                <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                    <BookOpen size={16} className="text-zinc-400" />
                    Indexed Documents ({documents.length})
                </h4>
                {documents.length === 0 ? (
                    <p className="text-sm text-zinc-500 text-center py-4">
                        No documents yet. Drop files above to get started!
                    </p>
                ) : (
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                        {documents.map((doc) => (
                            <div key={doc.id} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                                <div>
                                    <p className="text-sm font-medium">{doc.title || doc.filename}</p>
                                    <p className="text-xs text-zinc-500">
                                        {doc.chunk_count} chunks • {(doc.char_count / 1000).toFixed(1)}K chars • {doc.doc_type}
                                    </p>
                                </div>
                                <button
                                    onClick={() => deleteDocument(doc.id)}
                                    className="p-2 text-red-400 hover:bg-red-500/20 rounded-lg"
                                >
                                    <Trash2 size={16} />
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </motion.div>
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
