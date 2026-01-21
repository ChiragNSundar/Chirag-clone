import { useEffect, useState, useCallback } from 'react';
import ReactFlow, {
    Background,
    Controls,
    MiniMap,
    useNodesState,
    useEdgesState,
} from 'reactflow';
import type { Node, NodeMouseHandler } from 'reactflow';
import 'reactflow/dist/style.css';
import { api } from '../services/api';
import { motion, AnimatePresence } from 'framer-motion';
import { X, FileText, Database, Brain, Search } from 'lucide-react';

interface NodeData {
    label: string;
    type?: string;
    content?: string;
    metadata?: Record<string, unknown>;
}

interface DetailPanelProps {
    node: Node<NodeData> | null;
    onClose: () => void;
}

const DetailPanel = ({ node, onClose }: DetailPanelProps) => {
    if (!node) return null;

    const data = node.data;

    return (
        <motion.div
            initial={{ opacity: 0, x: 300 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 300 }}
            className="absolute top-0 right-0 w-80 h-full bg-zinc-900/95 backdrop-blur-xl border-l border-white/10 p-4 overflow-y-auto z-50"
        >
            <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-lg flex items-center gap-2">
                    {data.type === 'category' ? (
                        <Database size={18} className="text-purple-400" />
                    ) : (
                        <FileText size={18} className="text-blue-400" />
                    )}
                    Node Details
                </h3>
                <button
                    onClick={onClose}
                    className="p-1 hover:bg-white/10 rounded-lg transition-colors"
                >
                    <X size={18} />
                </button>
            </div>

            <div className="space-y-4">
                <div>
                    <label className="text-xs text-zinc-500 uppercase tracking-wide">Label</label>
                    <p className="text-sm font-medium mt-1">{data.label}</p>
                </div>

                {data.type && (
                    <div>
                        <label className="text-xs text-zinc-500 uppercase tracking-wide">Type</label>
                        <span className={`inline-block mt-1 px-2 py-0.5 rounded-full text-xs ${data.type === 'category'
                            ? 'bg-purple-500/20 text-purple-400'
                            : data.type === 'core'
                                ? 'bg-blue-500/20 text-blue-400'
                                : 'bg-zinc-500/20 text-zinc-400'
                            }`}>
                            {data.type}
                        </span>
                    </div>
                )}

                {data.content && (
                    <div>
                        <label className="text-xs text-zinc-500 uppercase tracking-wide">Content</label>
                        <p className="text-sm mt-1 p-3 bg-white/5 rounded-lg border border-white/10 max-h-48 overflow-y-auto">
                            {data.content}
                        </p>
                    </div>
                )}

                {data.metadata && Object.keys(data.metadata).length > 0 && (
                    <div>
                        <label className="text-xs text-zinc-500 uppercase tracking-wide">Metadata</label>
                        <div className="mt-1 space-y-1">
                            {Object.entries(data.metadata).map(([key, value]) => (
                                <div key={key} className="flex justify-between text-sm">
                                    <span className="text-zinc-400">{key}:</span>
                                    <span className="text-zinc-300">{String(value)}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </motion.div>
    );
};

// Custom node styles based on type
const getNodeStyle = (type: string) => {
    const baseStyle = {
        padding: '12px 16px',
        borderRadius: '12px',
        fontSize: '13px',
        fontWeight: 500,
        transition: 'all 0.2s ease',
        cursor: 'pointer',
    };

    switch (type) {
        case 'core':
            return {
                ...baseStyle,
                background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.3), rgba(139, 92, 246, 0.3))',
                border: '2px solid rgba(139, 92, 246, 0.5)',
                color: '#fff',
                boxShadow: '0 0 20px rgba(139, 92, 246, 0.3)',
            };
        case 'category':
            return {
                ...baseStyle,
                background: 'rgba(139, 92, 246, 0.15)',
                border: '1px solid rgba(139, 92, 246, 0.4)',
                color: '#a78bfa',
            };
        default:
            return {
                ...baseStyle,
                background: 'rgba(39, 39, 42, 0.9)',
                border: '1px solid rgba(63, 63, 70, 0.8)',
                color: '#e4e4e7',
            };
    }
};

export const MemoryGraph = () => {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [selectedNode, setSelectedNode] = useState<Node<NodeData> | null>(null);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const data = await api.getGraphData();

            const center = { x: 400, y: 300 };

            const transformedNodes = data.nodes.map((node, i: number) => {
                let pos = { x: center.x, y: center.y };
                const nodeType = node.type || 'leaf';

                if (nodeType === 'core') {
                    pos = { x: center.x, y: center.y };
                } else if (nodeType === 'category') {
                    const categoryCount = data.nodes.filter((n) => n.type === 'category').length;
                    const categoryIndex = data.nodes.filter((n, idx: number) => n.type === 'category' && idx < i).length;
                    const angle = (categoryIndex * 2 * Math.PI) / categoryCount;
                    pos = {
                        x: center.x + Math.cos(angle) * 200,
                        y: center.y + Math.sin(angle) * 200
                    };
                } else {
                    // Leaf nodes positioned around their parent category
                    const angle = Math.random() * 2 * Math.PI;
                    const distance = 100 + Math.random() * 150;
                    pos = {
                        x: center.x + Math.cos(angle) * (200 + distance),
                        y: center.y + Math.sin(angle) * distance
                    };
                }

                return {
                    id: node.id,
                    data: {
                        label: node.label,
                        type: nodeType,
                        content: node.content,
                        metadata: node.metadata
                    },
                    position: pos,
                    style: getNodeStyle(nodeType),
                };
            });

            const transformedEdges = data.edges.map((edge) => ({
                id: edge.id,
                source: edge.source,
                target: edge.target,
                type: 'smoothstep',
                animated: edge.animated !== false,
                style: {
                    stroke: 'rgba(139, 92, 246, 0.4)',
                    strokeWidth: 2
                }
            }));

            setNodes(transformedNodes);
            setEdges(transformedEdges);
        } catch (e) {
            console.error("Graph error", e);
        } finally {
            setLoading(false);
        }
    }, [setNodes, setEdges]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const onNodeClick: NodeMouseHandler = useCallback((_, node) => {
        setSelectedNode(node as Node<NodeData>);
    }, []);

    const filteredNodes = searchQuery
        ? nodes.filter(n =>
            n.data.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
            n.data.content?.toLowerCase().includes(searchQuery.toLowerCase())
        )
        : nodes;

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center">
                <div className="text-center">
                    <Brain className="w-12 h-12 mx-auto text-purple-400 animate-pulse" />
                    <p className="mt-2 text-zinc-400">Loading knowledge graph...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full w-full bg-background relative">
            {/* Search Bar */}
            <div className="absolute top-4 left-4 z-10">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={16} />
                    <input
                        type="text"
                        placeholder="Search nodes..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-10 pr-4 py-2 bg-zinc-900/90 backdrop-blur border border-white/10 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-purple-500 w-48"
                    />
                </div>
            </div>

            {/* Stats */}
            <div className="absolute top-4 right-4 z-10 flex gap-2">
                <span className="px-3 py-1.5 bg-zinc-900/90 backdrop-blur border border-white/10 rounded-lg text-xs text-zinc-400">
                    {nodes.length} nodes
                </span>
                <span className="px-3 py-1.5 bg-zinc-900/90 backdrop-blur border border-white/10 rounded-lg text-xs text-zinc-400">
                    {edges.length} connections
                </span>
            </div>

            <ReactFlow
                nodes={searchQuery ? filteredNodes : nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                fitView
                className="bg-background"
                proOptions={{ hideAttribution: true }}
            >
                <Background color="#3f3f46" gap={24} size={1} />
                <Controls
                    className="bg-zinc-900/90 border border-white/10 rounded-lg overflow-hidden"
                    
                />
                <MiniMap
                    className="bg-zinc-900/90 border border-white/10 rounded-lg"
                    nodeColor={(n) => {
                        if (n.data?.type === 'core') return '#8b5cf6';
                        if (n.data?.type === 'category') return '#6366f1';
                        return '#52525b';
                    }}
                    maskColor="rgba(0, 0, 0, 0.8)"
                />
            </ReactFlow>

            {/* Detail Panel */}
            <AnimatePresence>
                {selectedNode && (
                    <DetailPanel
                        node={selectedNode}
                        onClose={() => setSelectedNode(null)}
                    />
                )}
            </AnimatePresence>
        </div>
    );
};
