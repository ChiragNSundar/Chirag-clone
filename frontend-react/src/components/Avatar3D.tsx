/**
 * Avatar3D Component - 3D avatar with lip-sync capability
 * Uses Three.js via React Three Fiber and Ready Player Me GLB models
 */
import { useRef, useEffect, useState, useCallback, Suspense, Component, type ReactNode } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, useGLTF, useAnimations, Html } from '@react-three/drei';
import * as THREE from 'three';
import { Settings, Maximize2, Minimize2 } from 'lucide-react';

// Phoneme to viseme mapping for lip-sync
const PHONEME_VISEME_MAP: Record<string, string> = {
    'a': 'viseme_aa',
    'e': 'viseme_E',
    'i': 'viseme_I',
    'o': 'viseme_O',
    'u': 'viseme_U',
    'b': 'viseme_PP',
    'm': 'viseme_PP',
    'p': 'viseme_PP',
    'f': 'viseme_FF',
    'v': 'viseme_FF',
    's': 'viseme_SS',
    'z': 'viseme_SS',
    't': 'viseme_TH',
    'th': 'viseme_TH',
    'd': 'viseme_DD',
    'n': 'viseme_nn',
    'l': 'viseme_nn',
    'r': 'viseme_RR',
    'k': 'viseme_kk',
    'g': 'viseme_kk',
    'ch': 'viseme_CH',
    'sh': 'viseme_CH',
    'silence': 'viseme_sil',
};

// All viseme morph target names for Ready Player Me avatars
const VISEME_NAMES = [
    'viseme_sil', 'viseme_PP', 'viseme_FF', 'viseme_TH',
    'viseme_DD', 'viseme_kk', 'viseme_CH', 'viseme_SS',
    'viseme_nn', 'viseme_RR', 'viseme_aa', 'viseme_E',
    'viseme_I', 'viseme_O', 'viseme_U'
];

interface AvatarModelProps {
    url: string;
    speaking: boolean;
    text: string;
    onLoadComplete?: () => void;
}

/**
 * Simple text-to-viseme timing generator
 * Creates animation keyframes from text for lip-sync
 */
function textToVisemes(text: string): { viseme: string; duration: number }[] {
    const visemes: { viseme: string; duration: number }[] = [];
    const words = text.toLowerCase().split(/\s+/);

    for (const word of words) {
        const chars = word.split('');
        for (let i = 0; i < chars.length; i++) {
            const char = chars[i];
            // Check for digraphs
            const digraph = char + (chars[i + 1] || '');

            if (PHONEME_VISEME_MAP[digraph]) {
                visemes.push({ viseme: PHONEME_VISEME_MAP[digraph], duration: 80 });
                i++; // Skip next character
            } else if (PHONEME_VISEME_MAP[char]) {
                visemes.push({ viseme: PHONEME_VISEME_MAP[char], duration: 60 });
            }
        }
        // Add silence between words
        visemes.push({ viseme: 'viseme_sil', duration: 100 });
    }

    return visemes;
}

/**
 * Avatar Model Component - Loads and animates the 3D model
 */
function AvatarModel({ url, speaking, text, onLoadComplete }: AvatarModelProps) {
    const group = useRef<THREE.Group>(null);
    const { scene, animations } = useGLTF(url);
    const { actions } = useAnimations(animations, group);

    const [visemeQueue, setVisemeQueue] = useState<{ viseme: string; duration: number }[]>([]);
    const [currentVisemeIndex, setCurrentVisemeIndex] = useState(0);
    const visemeStartTime = useRef(0);
    const meshRef = useRef<THREE.SkinnedMesh | null>(null);

    // Find the head mesh with morph targets
    useEffect(() => {
        scene.traverse((child) => {
            if (child instanceof THREE.SkinnedMesh && child.morphTargetDictionary) {
                meshRef.current = child;
            }
        });
        onLoadComplete?.();
    }, [scene, onLoadComplete]);

    // Generate viseme queue when text changes and speaking
    useEffect(() => {
        if (speaking && text) {
            const visemes = textToVisemes(text);
            setVisemeQueue(visemes);
            setCurrentVisemeIndex(0);
            visemeStartTime.current = 0;
        } else {
            setVisemeQueue([]);
            setCurrentVisemeIndex(0);
        }
    }, [speaking, text]);

    // Play idle animation if available
    useEffect(() => {
        const idleAction = actions['Idle'] || actions['idle'] || Object.values(actions)[0];
        if (idleAction) {
            idleAction.play();
        }
    }, [actions]);

    // Animate visemes
    useFrame((_, delta) => {
        if (!meshRef.current || !speaking || visemeQueue.length === 0) {
            // Reset all visemes when not speaking
            if (meshRef.current?.morphTargetInfluences && meshRef.current?.morphTargetDictionary) {
                VISEME_NAMES.forEach(name => {
                    const index = meshRef.current!.morphTargetDictionary![name];
                    if (index !== undefined && meshRef.current!.morphTargetInfluences) {
                        const current = meshRef.current!.morphTargetInfluences[index] || 0;
                        meshRef.current!.morphTargetInfluences[index] = Math.max(0, current - delta * 5);
                    }
                });
            }
            return;
        }

        if (currentVisemeIndex >= visemeQueue.length) {
            return;
        }

        const currentViseme = visemeQueue[currentVisemeIndex];
        visemeStartTime.current += delta * 1000;

        // Animate morph targets
        const mesh = meshRef.current;
        if (mesh.morphTargetInfluences && mesh.morphTargetDictionary) {
            VISEME_NAMES.forEach(name => {
                const index = mesh.morphTargetDictionary![name];
                if (index !== undefined) {
                    const isActive = name === currentViseme.viseme;
                    const target = isActive ? 0.8 : 0;
                    const current = mesh.morphTargetInfluences![index] || 0;
                    mesh.morphTargetInfluences![index] = THREE.MathUtils.lerp(current, target, delta * 10);
                }
            });
        }

        // Move to next viseme
        if (visemeStartTime.current >= currentViseme.duration) {
            visemeStartTime.current = 0;
            setCurrentVisemeIndex(prev => prev + 1);
        }
    });

    return (
        <group ref={group} position={[0, -1.5, 0]} scale={1.5}>
            <primitive object={scene} />
        </group>
    );
}

interface Avatar3DProps {
    speaking?: boolean;
    text?: string;
    avatarUrl?: string;
    visible?: boolean;
    onToggleVisibility?: () => void;
}

// Inner Error Boundary for the 3D Model
class AvatarErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
    state = { hasError: false };
    static getDerivedStateFromError() { return { hasError: true }; }
    componentDidCatch(error: any) { console.error("Avatar 3D Error:", error); }
    render() {
        if (this.state.hasError) return (
            <Html center>
                <div className="flex items-center justify-center w-32 text-red-400 text-xs text-center p-2 bg-black/50 rounded backdrop-blur-sm">
                    Failed to load 3D Model
                </div>
            </Html>
        );
        return this.props.children;
    }
}

/**
 * Main Avatar3D Component
 */
export function Avatar3D({
    speaking = false,
    text = '',
    avatarUrl = 'https://models.readyplayer.me/658be9e8fc8be93dc963db81.glb',
    visible = true
}: Avatar3DProps) {
    const [isLoading, setIsLoading] = useState(true);
    const [isExpanded, setIsExpanded] = useState(false);
    const [showSettings, setShowSettings] = useState(false);
    const [customAvatarUrl, setCustomAvatarUrl] = useState(avatarUrl);

    useEffect(() => {
        setCustomAvatarUrl(avatarUrl);
    }, [avatarUrl]);

    const handleLoadComplete = useCallback(() => {
        setIsLoading(false);
    }, []);

    if (!visible) {
        return null;
    }

    return (
        <div className={`relative bg-gradient-to-b from-zinc-900/50 to-zinc-900/80 backdrop-blur-lg rounded-2xl border border-white/10 overflow-hidden transition-all duration-300 ${isExpanded ? 'w-96 h-96' : 'w-48 h-48'}`}>
            {/* Loading Overlay */}
            {isLoading && (
                <div className="absolute inset-0 z-10 flex items-center justify-center bg-zinc-900/80">
                    <div className="flex flex-col items-center gap-2 text-zinc-400">
                        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                        <span className="text-xs">Loading Avatar...</span>
                    </div>
                </div>
            )}

            {/* Controls */}
            <div className="absolute top-2 right-2 z-20 flex gap-1">
                <button
                    onClick={() => setShowSettings(!showSettings)}
                    className="p-1.5 bg-zinc-800/80 hover:bg-zinc-700 rounded-lg text-zinc-400 hover:text-white transition-colors"
                    title="Settings"
                >
                    <Settings size={14} />
                </button>
                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="p-1.5 bg-zinc-800/80 hover:bg-zinc-700 rounded-lg text-zinc-400 hover:text-white transition-colors"
                    title={isExpanded ? 'Minimize' : 'Expand'}
                >
                    {isExpanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
                </button>
            </div>

            {/* Speaking Indicator */}
            {speaking && (
                <div className="absolute top-2 left-2 z-20 flex items-center gap-1.5 px-2 py-1 bg-green-500/20 border border-green-500/30 rounded-full">
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    <span className="text-xs text-green-400">Speaking</span>
                </div>
            )}

            {/* Settings Panel */}
            {showSettings && (
                <div className="absolute inset-x-2 bottom-2 z-20 p-3 bg-zinc-900/95 border border-white/10 rounded-xl">
                    <label className="block text-xs text-zinc-400 mb-1">Avatar URL</label>
                    <input
                        type="text"
                        value={customAvatarUrl}
                        onChange={(e) => setCustomAvatarUrl(e.target.value)}
                        className="w-full px-2 py-1 text-xs bg-zinc-800 border border-white/10 rounded text-white"
                        placeholder="Ready Player Me URL"
                    />
                    <p className="mt-2 text-[10px] text-zinc-500">
                        Get your avatar at readyplayer.me
                    </p>
                </div>
            )}

            {/* 3D Canvas */}
            <Canvas
                camera={{ position: [0, 0, 2.5], fov: 35 }}
                style={{ background: 'transparent' }}
            >
                <ambientLight intensity={0.6} />
                <directionalLight position={[5, 5, 5]} intensity={0.8} />
                <directionalLight position={[-5, 3, -5]} intensity={0.4} />

                <AvatarErrorBoundary>
                    <Suspense fallback={null}>
                        <AvatarModel
                            url={customAvatarUrl}
                            speaking={speaking}
                            text={text}
                            onLoadComplete={handleLoadComplete}
                        />
                    </Suspense>
                </AvatarErrorBoundary>

                <OrbitControls
                    enableZoom={false}
                    enablePan={false}
                    minPolarAngle={Math.PI / 3}
                    maxPolarAngle={Math.PI / 2}
                    target={[0, 0, 0]}
                />
            </Canvas>
        </div>
    );
}

export default Avatar3D;


