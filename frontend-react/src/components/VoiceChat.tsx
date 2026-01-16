import { useState, useRef, useCallback, useEffect } from 'react';
import { Mic, MicOff, Volume2, VolumeX, Loader2, Wifi, WifiOff } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import clsx from 'clsx';

interface VoiceChatProps {
    onTranscript: (text: string) => void;
    textToSpeak?: string;
    isEnabled?: boolean;
    onBotResponse?: (text: string) => void;
}

interface WebSocketMessage {
    type: string;
    text?: string;
    audio_base64?: string;
    format?: string;
    message?: string;
    session_id?: string;
    confidence?: number;
    mood?: Record<string, unknown>;
    is_user_speaking?: boolean;
    is_bot_speaking?: boolean;
}

/**
 * VoiceChat - Voice input/output component with real-time streaming support
 */
export function VoiceChat({ onTranscript, textToSpeak, isEnabled = true, onBotResponse }: VoiceChatProps) {
    const [isRecording, setIsRecording] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [voiceEnabled, setVoiceEnabled] = useState(true);
    const [isLiveMode, setIsLiveMode] = useState(false);
    const [isConnected, setIsConnected] = useState(false);
    const [voiceStatus, setVoiceStatus] = useState<{ tts_enabled: boolean, stt_enabled: boolean } | null>(null);

    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const audioChunksRef = useRef<Blob[]>([]);
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const websocketRef = useRef<WebSocket | null>(null);
    const streamRef = useRef<MediaStream | null>(null);

    // Check voice service status on mount
    useEffect(() => {
        fetch('/api/voice/status')
            .then(res => res.json())
            .then(setVoiceStatus)
            .catch(() => setVoiceStatus({ tts_enabled: false, stt_enabled: false }));
    }, []);

    // Auto-speak when textToSpeak changes (only in non-live mode)
    useEffect(() => {
        if (textToSpeak && voiceEnabled && voiceStatus?.tts_enabled && !isLiveMode) {
            speakText(textToSpeak);
        }
    }, [textToSpeak, voiceEnabled, voiceStatus?.tts_enabled, isLiveMode]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            disconnectWebSocket();
            if (streamRef.current) {
                streamRef.current.getTracks().forEach(track => track.stop());
            }
        };
    }, []);

    // Connect to WebSocket for live mode
    const connectWebSocket = useCallback(() => {
        if (websocketRef.current?.readyState === WebSocket.OPEN) return;

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.hostname}:8000/api/voice/stream`;

        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            setIsConnected(true);
            console.log('WebSocket connected for real-time voice');
        };

        ws.onmessage = (event) => {
            try {
                const data: WebSocketMessage = JSON.parse(event.data);
                handleWebSocketMessage(data);
            } catch (e) {
                console.error('WebSocket message parse error:', e);
            }
        };

        ws.onclose = () => {
            setIsConnected(false);
            setIsLiveMode(false);
            console.log('WebSocket disconnected');
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            setIsConnected(false);
        };

        websocketRef.current = ws;
    }, []);

    const disconnectWebSocket = useCallback(() => {
        if (websocketRef.current) {
            websocketRef.current.close();
            websocketRef.current = null;
        }
        setIsConnected(false);
    }, []);

    const handleWebSocketMessage = useCallback((data: WebSocketMessage) => {
        switch (data.type) {
            case 'connected':
                console.log('Session ID:', data.session_id);
                break;

            case 'transcript':
                if (data.text) {
                    onTranscript(data.text);
                }
                break;

            case 'response':
                setIsProcessing(false);
                if (data.text && onBotResponse) {
                    onBotResponse(data.text);
                }
                if (data.audio_base64 && voiceEnabled) {
                    playAudioFromBase64(data.audio_base64, data.format || 'mp3');
                }
                break;

            case 'interrupted':
                stopSpeaking();
                break;

            case 'error':
                console.error('WebSocket error:', data.message);
                setIsProcessing(false);
                break;

            case 'status':
                // Update UI based on status if needed
                break;
        }
    }, [onTranscript, onBotResponse, voiceEnabled]);

    const playAudioFromBase64 = (base64: string, format: string) => {
        setIsSpeaking(true);
        const audio = new Audio(`data:audio/${format};base64,${base64}`);
        audioRef.current = audio;

        audio.onended = () => {
            setIsSpeaking(false);
            // Notify server that playback finished
            if (websocketRef.current?.readyState === WebSocket.OPEN) {
                websocketRef.current.send(JSON.stringify({ type: 'bot_speech_complete' }));
            }
        };
        audio.onerror = () => setIsSpeaking(false);

        audio.play().catch(() => setIsSpeaking(false));
    };

    // Toggle live mode
    const toggleLiveMode = useCallback(() => {
        if (isLiveMode) {
            // Disable live mode
            disconnectWebSocket();
            if (isRecording) {
                stopRecording();
            }
            setIsLiveMode(false);
        } else {
            // Enable live mode
            connectWebSocket();
            setIsLiveMode(true);
        }
    }, [isLiveMode, isRecording, connectWebSocket, disconnectWebSocket]);

    // Start recording (works in both modes)
    const startRecording = useCallback(async () => {
        if (!voiceStatus?.stt_enabled) {
            console.warn('STT not enabled');
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            streamRef.current = stream;

            const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            mediaRecorderRef.current = mediaRecorder;
            audioChunksRef.current = [];

            if (isLiveMode && websocketRef.current?.readyState === WebSocket.OPEN) {
                // Live mode: stream chunks to WebSocket
                mediaRecorder.ondataavailable = async (event) => {
                    if (event.data.size > 0) {
                        const reader = new FileReader();
                        reader.onloadend = () => {
                            const base64 = (reader.result as string).split(',')[1];
                            if (websocketRef.current?.readyState === WebSocket.OPEN) {
                                websocketRef.current.send(JSON.stringify({
                                    type: 'audio',
                                    audio_base64: base64,
                                    format: 'webm'
                                }));
                            }
                        };
                        reader.readAsDataURL(event.data);
                    }
                };

                // Request data every 500ms for streaming
                mediaRecorder.start(500);
            } else {
                // Push-to-talk mode: collect all chunks
                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        audioChunksRef.current.push(event.data);
                    }
                };

                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                    await processAudio(audioBlob);
                    stream.getTracks().forEach(track => track.stop());
                };

                mediaRecorder.start();
            }

            setIsRecording(true);
        } catch (error) {
            console.error('Error accessing microphone:', error);
        }
    }, [voiceStatus, isLiveMode]);

    const stopRecording = useCallback(() => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);

            if (isLiveMode && websocketRef.current?.readyState === WebSocket.OPEN) {
                // Send end_turn signal in live mode
                setIsProcessing(true);
                websocketRef.current.send(JSON.stringify({ type: 'end_turn' }));

                // Stop the stream
                if (streamRef.current) {
                    streamRef.current.getTracks().forEach(track => track.stop());
                }
            }
        }
    }, [isRecording, isLiveMode]);

    const processAudio = async (audioBlob: Blob) => {
        setIsProcessing(true);

        try {
            const reader = new FileReader();
            const base64Promise = new Promise<string>((resolve) => {
                reader.onloadend = () => {
                    const base64 = (reader.result as string).split(',')[1];
                    resolve(base64);
                };
            });
            reader.readAsDataURL(audioBlob);
            const audioBase64 = await base64Promise;

            const response = await fetch('/api/voice/listen', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    audio_base64: audioBase64,
                    audio_format: 'webm'
                })
            });

            const result = await response.json();

            if (result.text) {
                onTranscript(result.text);
            }
        } catch (error) {
            console.error('Error processing audio:', error);
        } finally {
            setIsProcessing(false);
        }
    };

    const speakText = async (text: string) => {
        if (!voiceStatus?.tts_enabled) return;

        setIsSpeaking(true);

        try {
            const response = await fetch('/api/voice/speak', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text })
            });

            const result = await response.json();

            if (result.audio_base64) {
                const audio = new Audio(`data:audio/mp3;base64,${result.audio_base64}`);
                audioRef.current = audio;

                audio.onended = () => setIsSpeaking(false);
                audio.onerror = () => setIsSpeaking(false);

                await audio.play();
            } else {
                setIsSpeaking(false);
            }
        } catch (error) {
            console.error('Error playing audio:', error);
            setIsSpeaking(false);
        }
    };

    const stopSpeaking = () => {
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current = null;
        }
        setIsSpeaking(false);

        // Notify WebSocket if in live mode
        if (isLiveMode && websocketRef.current?.readyState === WebSocket.OPEN) {
            websocketRef.current.send(JSON.stringify({ type: 'interrupt' }));
        }
    };

    const interruptBot = useCallback(() => {
        stopSpeaking();
    }, []);

    if (!isEnabled) return null;

    return (
        <div className="flex items-center gap-2">
            {/* Live Mode Toggle */}
            <motion.button
                whileTap={{ scale: 0.95 }}
                onClick={toggleLiveMode}
                disabled={!voiceStatus?.stt_enabled || !voiceStatus?.tts_enabled}
                className={clsx(
                    "p-2.5 rounded-xl transition-all duration-200",
                    isLiveMode
                        ? isConnected
                            ? "bg-green-500 text-white"
                            : "bg-yellow-500 text-white animate-pulse"
                        : "bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white",
                    (!voiceStatus?.stt_enabled || !voiceStatus?.tts_enabled) && "opacity-50 cursor-not-allowed"
                )}
                title={isLiveMode ? (isConnected ? "Live mode ON" : "Connecting...") : "Enable live mode"}
            >
                {isLiveMode ? <Wifi size={20} /> : <WifiOff size={20} />}
            </motion.button>

            {/* Microphone Button */}
            <motion.button
                whileTap={{ scale: 0.95 }}
                onClick={isRecording ? stopRecording : startRecording}
                disabled={isProcessing || !voiceStatus?.stt_enabled}
                className={clsx(
                    "p-2.5 rounded-xl transition-all duration-200",
                    isRecording
                        ? "bg-red-500 text-white animate-pulse"
                        : "bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white",
                    (isProcessing || !voiceStatus?.stt_enabled) && "opacity-50 cursor-not-allowed"
                )}
                title={voiceStatus?.stt_enabled ? (isRecording ? "Stop recording" : "Start recording") : "STT not available"}
            >
                {isProcessing ? (
                    <Loader2 size={20} className="animate-spin" />
                ) : isRecording ? (
                    <MicOff size={20} />
                ) : (
                    <Mic size={20} />
                )}
            </motion.button>

            {/* Voice Output Toggle / Interrupt */}
            <motion.button
                whileTap={{ scale: 0.95 }}
                onClick={() => {
                    if (isSpeaking) {
                        interruptBot();
                    } else {
                        setVoiceEnabled(!voiceEnabled);
                    }
                }}
                disabled={!voiceStatus?.tts_enabled}
                className={clsx(
                    "p-2.5 rounded-xl transition-all duration-200",
                    isSpeaking
                        ? "bg-purple-500 text-white"
                        : voiceEnabled
                            ? "bg-purple-500/20 text-purple-400 border border-purple-500/30"
                            : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700",
                    !voiceStatus?.tts_enabled && "opacity-50 cursor-not-allowed"
                )}
                title={voiceStatus?.tts_enabled ? (isSpeaking ? "Click to interrupt" : voiceEnabled ? "Voice on" : "Voice off") : "TTS not available"}
            >
                {isSpeaking ? (
                    <Volume2 size={20} className="animate-pulse" />
                ) : voiceEnabled ? (
                    <Volume2 size={20} />
                ) : (
                    <VolumeX size={20} />
                )}
            </motion.button>

            {/* Recording/Live Indicator */}
            <AnimatePresence>
                {isRecording && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.8 }}
                        className={clsx(
                            "flex items-center gap-2 px-3 py-1 rounded-lg",
                            isLiveMode
                                ? "bg-green-500/10 border border-green-500/30"
                                : "bg-red-500/10 border border-red-500/30"
                        )}
                    >
                        <span className={clsx(
                            "w-2 h-2 rounded-full animate-pulse",
                            isLiveMode ? "bg-green-500" : "bg-red-500"
                        )} />
                        <span className={clsx(
                            "text-xs",
                            isLiveMode ? "text-green-400" : "text-red-400"
                        )}>
                            {isLiveMode ? "Live..." : "Recording..."}
                        </span>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Processing Indicator */}
            <AnimatePresence>
                {isProcessing && !isRecording && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.8 }}
                        className="flex items-center gap-2 px-3 py-1 bg-blue-500/10 border border-blue-500/30 rounded-lg"
                    >
                        <Loader2 size={12} className="animate-spin text-blue-400" />
                        <span className="text-xs text-blue-400">Processing...</span>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

/**
 * Waveform visualizer for voice activity
 */
export function VoiceWaveform({ isActive }: { isActive: boolean }) {
    return (
        <div className="flex items-center gap-0.5 h-4">
            {[...Array(5)].map((_, i) => (
                <motion.div
                    key={i}
                    className="w-1 bg-purple-400 rounded-full"
                    animate={{
                        height: isActive ? [4, 16, 8, 12, 4] : 4
                    }}
                    transition={{
                        duration: 0.5,
                        repeat: isActive ? Infinity : 0,
                        delay: i * 0.1
                    }}
                />
            ))}
        </div>
    );
}
