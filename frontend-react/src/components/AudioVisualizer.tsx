import { useRef, useEffect, useState } from 'react';
import { motion } from 'framer-motion';

interface AudioVisualizerProps {
    isActive: boolean;
    audioStream?: MediaStream | null;
    audioElement?: HTMLAudioElement | null;
    mode: 'input' | 'output';
    variant?: 'bars' | 'orb' | 'wave';
}

/**
 * AudioVisualizer - Real-time frequency visualization using Web Audio API
 * Supports microphone input and audio playback visualization
 */
export function AudioVisualizer({
    isActive,
    audioStream,
    audioElement,
    mode,
    variant = 'bars'
}: AudioVisualizerProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const animationRef = useRef<number>(0);
    const audioContextRef = useRef<AudioContext | null>(null);
    const [avgFrequency, setAvgFrequency] = useState(0);

    useEffect(() => {
        if (!isActive) {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }
            return;
        }

        const setupAudio = async () => {
            try {
                // Create or reuse audio context
                if (!audioContextRef.current) {
                    audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
                }
                const audioContext = audioContextRef.current;

                // Create analyser
                const analyser = audioContext.createAnalyser();
                analyser.fftSize = 256;
                analyser.smoothingTimeConstant = 0.8;
                analyserRef.current = analyser;

                // Connect source based on mode
                if (mode === 'input' && audioStream) {
                    const source = audioContext.createMediaStreamSource(audioStream);
                    source.connect(analyser);
                } else if (mode === 'output' && audioElement) {
                    const source = audioContext.createMediaElementSource(audioElement);
                    source.connect(analyser);
                    analyser.connect(audioContext.destination);
                }

                // Start visualization
                visualize();
            } catch (error) {
                console.error('Audio visualization error:', error);
            }
        };

        const visualize = () => {
            if (!analyserRef.current || !canvasRef.current) return;

            const analyser = analyserRef.current;
            const canvas = canvasRef.current;
            const ctx = canvas.getContext('2d');
            if (!ctx) return;

            const bufferLength = analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);

            const draw = () => {
                animationRef.current = requestAnimationFrame(draw);

                analyser.getByteFrequencyData(dataArray);

                // Calculate average for orb intensity
                const avg = dataArray.reduce((a, b) => a + b, 0) / bufferLength;
                setAvgFrequency(avg);

                // Clear canvas
                ctx.clearRect(0, 0, canvas.width, canvas.height);

                if (variant === 'bars') {
                    drawBars(ctx, dataArray, canvas.width, canvas.height);
                } else if (variant === 'wave') {
                    drawWave(ctx, dataArray, canvas.width, canvas.height);
                }
            };

            draw();
        };

        setupAudio();

        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }
        };
    }, [isActive, audioStream, audioElement, mode, variant]);

    const drawBars = (ctx: CanvasRenderingContext2D, dataArray: Uint8Array, width: number, height: number) => {
        const barCount = 32;
        const barWidth = width / barCount;
        const step = Math.floor(dataArray.length / barCount);

        for (let i = 0; i < barCount; i++) {
            const value = dataArray[i * step];
            const barHeight = (value / 255) * height;

            // Gradient from purple to blue
            const hue = 260 + (i / barCount) * 40;
            ctx.fillStyle = `hsla(${hue}, 80%, 60%, 0.8)`;

            const x = i * barWidth;
            const y = height - barHeight;

            // Draw rounded bar
            ctx.beginPath();
            ctx.roundRect(x + 1, y, barWidth - 2, barHeight, 2);
            ctx.fill();
        }
    };

    const drawWave = (ctx: CanvasRenderingContext2D, dataArray: Uint8Array, width: number, height: number) => {
        ctx.beginPath();
        ctx.strokeStyle = 'rgba(139, 92, 246, 0.8)';
        ctx.lineWidth = 2;

        const sliceWidth = width / dataArray.length;
        let x = 0;

        for (let i = 0; i < dataArray.length; i++) {
            const v = dataArray[i] / 128.0;
            const y = (v * height) / 2;

            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }

            x += sliceWidth;
        }

        ctx.lineTo(width, height / 2);
        ctx.stroke();
    };

    if (variant === 'orb') {
        const intensity = avgFrequency / 255;
        const scale = 1 + intensity * 0.3;
        const glowSize = 20 + intensity * 30;

        return (
            <motion.div
                className="relative flex items-center justify-center"
                animate={{
                    scale: isActive ? scale : 1,
                }}
                transition={{ duration: 0.1 }}
            >
                {/* Outer glow */}
                <div
                    className="absolute rounded-full bg-purple-500/20 blur-xl"
                    style={{
                        width: glowSize * 2,
                        height: glowSize * 2,
                        opacity: isActive ? 0.6 + intensity * 0.4 : 0.2,
                    }}
                />
                {/* Inner orb */}
                <motion.div
                    className="relative w-12 h-12 rounded-full"
                    style={{
                        background: isActive
                            ? `radial-gradient(circle at 30% 30%, rgba(167, 139, 250, 0.9), rgba(139, 92, 246, 0.8), rgba(109, 40, 217, 0.9))`
                            : 'radial-gradient(circle at 30% 30%, rgba(82, 82, 91, 0.9), rgba(63, 63, 70, 0.8))',
                        boxShadow: isActive
                            ? `0 0 ${glowSize}px rgba(139, 92, 246, ${0.4 + intensity * 0.4})`
                            : 'none',
                    }}
                    animate={{
                        scale: isActive ? [1, 1 + intensity * 0.1, 1] : 1,
                    }}
                    transition={{
                        duration: 0.2,
                        repeat: isActive ? Infinity : 0,
                    }}
                />
            </motion.div>
        );
    }

    return (
        <canvas
            ref={canvasRef}
            width={variant === 'bars' ? 160 : 200}
            height={40}
            className="rounded-lg"
            style={{
                opacity: isActive ? 1 : 0.3,
            }}
        />
    );
}

/**
 * Simple waveform bars (CSS-only, no audio analysis)
 * Use when you don't have access to the audio stream
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
