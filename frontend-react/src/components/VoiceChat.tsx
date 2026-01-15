import { useState, useRef, useCallback, useEffect } from 'react';
import { Mic, MicOff, Volume2, VolumeX, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import clsx from 'clsx';

interface VoiceChatProps {
    onTranscript: (text: string) => void;
    textToSpeak?: string;
    isEnabled?: boolean;
}

/**
 * VoiceChat - Voice input/output component with mic and speaker controls
 */
export function VoiceChat({ onTranscript, textToSpeak, isEnabled = true }: VoiceChatProps) {
    const [isRecording, setIsRecording] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [voiceEnabled, setVoiceEnabled] = useState(true);
    const [voiceStatus, setVoiceStatus] = useState<{ tts_enabled: boolean, stt_enabled: boolean } | null>(null);

    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const audioChunksRef = useRef<Blob[]>([]);
    const audioRef = useRef<HTMLAudioElement | null>(null);

    // Check voice service status on mount
    useEffect(() => {
        fetch('/api/voice/status')
            .then(res => res.json())
            .then(setVoiceStatus)
            .catch(() => setVoiceStatus({ tts_enabled: false, stt_enabled: false }));
    }, []);

    // Auto-speak when textToSpeak changes
    useEffect(() => {
        if (textToSpeak && voiceEnabled && voiceStatus?.tts_enabled) {
            speakText(textToSpeak);
        }
    }, [textToSpeak]);

    const startRecording = useCallback(async () => {
        if (!voiceStatus?.stt_enabled) {
            console.warn('STT not enabled');
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

            mediaRecorderRef.current = mediaRecorder;
            audioChunksRef.current = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunksRef.current.push(event.data);
                }
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                await processAudio(audioBlob);

                // Stop all tracks
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();
            setIsRecording(true);
        } catch (error) {
            console.error('Error accessing microphone:', error);
        }
    }, [voiceStatus]);

    const stopRecording = useCallback(() => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);
        }
    }, [isRecording]);

    const processAudio = async (audioBlob: Blob) => {
        setIsProcessing(true);

        try {
            // Convert blob to base64
            const reader = new FileReader();
            const base64Promise = new Promise<string>((resolve) => {
                reader.onloadend = () => {
                    const base64 = (reader.result as string).split(',')[1];
                    resolve(base64);
                };
            });
            reader.readAsDataURL(audioBlob);
            const audioBase64 = await base64Promise;

            // Send to STT endpoint
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
    };

    if (!isEnabled) return null;

    return (
        <div className="flex items-center gap-2">
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

            {/* Voice Output Toggle */}
            <motion.button
                whileTap={{ scale: 0.95 }}
                onClick={() => {
                    if (isSpeaking) {
                        stopSpeaking();
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
                title={voiceStatus?.tts_enabled ? (voiceEnabled ? "Voice on" : "Voice off") : "TTS not available"}
            >
                {isSpeaking ? (
                    <Volume2 size={20} className="animate-pulse" />
                ) : voiceEnabled ? (
                    <Volume2 size={20} />
                ) : (
                    <VolumeX size={20} />
                )}
            </motion.button>

            {/* Recording Indicator */}
            <AnimatePresence>
                {isRecording && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.8 }}
                        className="flex items-center gap-2 px-3 py-1 bg-red-500/10 border border-red-500/30 rounded-lg"
                    >
                        <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                        <span className="text-xs text-red-400">Recording...</span>
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
