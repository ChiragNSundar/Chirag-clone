
import React, { useState, useRef, useEffect } from 'react';
import { Mic, Square, Upload, Play, Trash2, StopCircle, RefreshCw } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface ClonedVoice {
    voice_id: string;
    name: string;
    category: string;
    labels?: Record<string, string>;
}

export const VoiceStudio = () => {
    const [recording, setRecording] = useState(false);
    const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
    const [audioUrl, setAudioUrl] = useState<string | null>(null);
    const [voiceName, setVoiceName] = useState('');
    const [description, setDescription] = useState('');
    const [loading, setLoading] = useState(false);
    const [clonedVoices, setClonedVoices] = useState<ClonedVoice[]>([]);
    const [activeTab, setActiveTab] = useState<'create' | 'list'>('create');

    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const chunksRef = useRef<Blob[]>([]);

    useEffect(() => {
        if (activeTab === 'list') {
            fetchVoices();
        }
    }, [activeTab]);

    const getTrainingPin = () => sessionStorage.getItem('training_pin') || '';

    const fetchVoices = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/voice/cloned', {
                headers: { 'X-Training-PIN': getTrainingPin() }
            });
            const data = await res.json();
            // Filter only cloned voices or show all
            if (Array.isArray(data)) {
                setClonedVoices(data.filter((v: ClonedVoice) => v.category === 'cloned'));
            }
        } catch (e) {
            console.error(e);
        }
    };

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream);
            mediaRecorderRef.current = mediaRecorder;
            chunksRef.current = [];

            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) chunksRef.current.push(e.data);
            };

            mediaRecorder.onstop = () => {
                const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
                setAudioBlob(blob);
                setAudioUrl(URL.createObjectURL(blob));
            };

            mediaRecorder.start();
            setRecording(true);
        } catch (e) {
            alert('Could not access microphone');
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && recording) {
            mediaRecorderRef.current.stop();
            setRecording(false);
            mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
        }
    };

    const handleClone = async () => {
        if (!audioBlob || !voiceName) return;
        setLoading(true);

        const formData = new FormData();
        formData.append('name', voiceName);
        formData.append('description', description || 'Cloned in Voice Studio');

        // Append the recorded file
        const file = new File([audioBlob], 'recording.webm', { type: 'audio/webm' });
        formData.append('files', file);

        try {
            const res = await fetch('http://localhost:8000/api/voice/clone', {
                method: 'POST',
                headers: { 'X-Training-PIN': getTrainingPin() },
                body: formData
            });

            if (res.ok) {
                const data = await res.json();
                alert(`Voice cloned successfully! ID: ${data.voice_id}`);
                setAudioBlob(null);
                setAudioUrl(null);
                setVoiceName('');
                setActiveTab('list');
            } else {
                const error = await res.json();
                alert(`Error: ${error.detail}`);
            }
        } catch (e) {
            alert('Failed to clone voice');
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Are you sure you want to delete this voice?')) return;
        try {
            await fetch(`http://localhost:8000/api/voice/${id}`, {
                method: 'DELETE',
                headers: { 'X-Training-PIN': getTrainingPin() }
            });
            fetchVoices();
        } catch (e) {
            console.error(e);
        }
    };

    return (
        <div className="h-full flex flex-col p-6 space-y-6 overflow-y-auto">
            <div className="flex justify-between items-center">
                <h2 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                    Voice Cloning Studio
                </h2>
                <div className="flex bg-white/5 rounded-lg p-1">
                    <button
                        onClick={() => setActiveTab('create')}
                        className={`px-4 py-2 rounded-md text-sm transition-all ${activeTab === 'create' ? 'bg-primary text-white' : 'hover:bg-white/10'
                            }`}
                    >
                        Create Voice
                    </button>
                    <button
                        onClick={() => setActiveTab('list')}
                        className={`px-4 py-2 rounded-md text-sm transition-all ${activeTab === 'list' ? 'bg-primary text-white' : 'hover:bg-white/10'
                            }`}
                    >
                        My Voices
                    </button>
                </div>
            </div>

            {activeTab === 'create' ? (
                <div className="flex flex-col space-y-6 max-w-2xl mx-auto w-full">
                    <div className="glass-panel p-6 space-y-4">
                        <label className="block text-sm font-medium text-zinc-400">Voice Name</label>
                        <input
                            type="text"
                            value={voiceName}
                            onChange={(e) => setVoiceName(e.target.value)}
                            className="w-full bg-black/20 border border-white/10 rounded px-4 py-2 focus:outline-none focus:border-primary"
                            placeholder="e.g. My Clone"
                        />

                        <label className="block text-sm font-medium text-zinc-400">Description</label>
                        <textarea
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            className="w-full bg-black/20 border border-white/10 rounded px-4 py-2 focus:outline-none focus:border-primary h-20"
                            placeholder="Optional description..."
                        />
                    </div>

                    <div className="glass-panel p-8 flex flex-col items-center justify-center space-y-6 min-h-[300px]">
                        {audioUrl ? (
                            <div className="w-full flex flex-col items-center space-y-4">
                                <div className="text-emerald-400 font-medium flex items-center gap-2">
                                    <Mic size={20} /> Recording Captured
                                </div>
                                <audio src={audioUrl} controls className="w-full" />
                                <button
                                    onClick={() => { setAudioUrl(null); setAudioBlob(null); }}
                                    className="text-sm text-red-400 hover:text-red-300 underline"
                                >
                                    Discard and Record Again
                                </button>
                            </div>
                        ) : (
                            <div className="relative">
                                <motion.div
                                    animate={recording ? { scale: [1, 1.2, 1], opacity: [0.5, 0.2, 0.5] } : {}}
                                    transition={{ repeat: Infinity, duration: 2 }}
                                    className="absolute inset-0 bg-red-500 rounded-full blur-xl"
                                />
                                <button
                                    onClick={recording ? stopRecording : startRecording}
                                    className={`relative z-10 w-24 h-24 rounded-full flex items-center justify-center transition-all ${recording ? 'bg-red-500 hover:bg-red-600' : 'bg-primary hover:bg-primary/80'
                                        }`}
                                >
                                    {recording ? <Square size={32} /> : <Mic size={32} />}
                                </button>
                            </div>
                        )}

                        <p className="text-sm text-zinc-500">
                            {recording ? 'Recording... Tap to stop' : 'Tap to record (min 1 minute recommended)'}
                        </p>
                    </div>

                    <div className="flex justify-end">
                        <button
                            onClick={handleClone}
                            disabled={!audioBlob || !voiceName || loading}
                            className={`flex items-center gap-2 px-6 py-3 rounded-lg font-bold transition-all ${!audioBlob || !voiceName || loading
                                ? 'bg-zinc-700 text-zinc-500 cursor-not-allowed'
                                : 'bg-gradient-to-r from-purple-600 to-pink-600 hover:scale-105'
                                }`}
                        >
                            {loading ? <RefreshCw className="animate-spin" /> : <Upload size={20} />}
                            {loading ? 'Cloning Voice...' : 'Clone Voice Now'}
                        </button>
                    </div>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {clonedVoices.length === 0 ? (
                        <div className="col-span-full text-center py-20 text-zinc-500">
                            No cloned voices found. Create one to get started!
                        </div>
                    ) : (
                        clonedVoices.map(voice => (
                            <motion.div
                                key={voice.voice_id}
                                layout
                                className="glass-panel p-4 flex flex-col justify-between group"
                            >
                                <div>
                                    <div className="flex justify-between items-start mb-2">
                                        <h3 className="font-bold text-lg">{voice.name}</h3>
                                        <span className="text-xs bg-purple-500/20 text-purple-300 px-2 py-1 rounded">
                                            {voice.category}
                                        </span>
                                    </div>
                                    <p className="text-xs text-zinc-500 font-mono break-all">{voice.voice_id}</p>
                                </div>
                                <div className="mt-4 flex justify-end">
                                    <button
                                        onClick={() => handleDelete(voice.voice_id)}
                                        className="p-2 text-zinc-500 hover:text-red-400 transition-colors"
                                        title="Delete Voice"
                                    >
                                        <Trash2 size={18} />
                                    </button>
                                </div>
                            </motion.div>
                        ))
                    )}
                </div>
            )}
        </div>
    );
};
