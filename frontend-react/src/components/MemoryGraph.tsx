import { useEffect } from 'react';
import ReactFlow, {
    Background,
    Controls,
    useNodesState,
    useEdgesState
} from 'reactflow';
import 'reactflow/dist/style.css';
import { api } from '../services/api';

export const MemoryGraph = () => {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const data = await api.getGraphData();

                const center = { x: 400, y: 300 };

                const transformedNodes = data.nodes.map((node, i) => {
                    let pos = { x: center.x, y: center.y };

                    if (node.type === 'category') {
                        const angle = (i * 2 * Math.PI) / 3;
                        pos = {
                            x: center.x + Math.cos(angle) * 150,
                            y: center.y + Math.sin(angle) * 150
                        };
                    } else if (node.type === 'leaf') {
                        pos = {
                            x: center.x + (Math.random() - 0.5) * 600,
                            y: center.y + (Math.random() - 0.5) * 600
                        };
                    }

                    return {
                        id: node.id,
                        data: { label: node.label },
                        position: pos,
                        style: {
                            background: '#18181b',
                            color: '#fff',
                            border: '1px solid #3f3f46',
                            padding: '10px',
                            borderRadius: '8px',
                            width: 150,
                            fontSize: '12px'
                        }
                    };
                });

                const transformedEdges = data.edges.map(edge => ({
                    id: edge.id,
                    source: edge.source,
                    target: edge.target,
                    type: 'default',
                    animated: true,
                    style: { stroke: '#52525b' }
                }));

                setNodes(transformedNodes);
                setEdges(transformedEdges);
            } catch (e) {
                console.error("Graph error", e);
            }
        };

        fetchData();
    }, [setNodes, setEdges]);

    return (
        <div className="h-full w-full bg-background">
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                fitView
                className="bg-background"
            >
                <Background color="#27272a" gap={20} />
                <Controls className="bg-surface border-white/10 fill-white" />
            </ReactFlow>
        </div>
    );
};
