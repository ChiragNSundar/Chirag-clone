const API_BASE = 'http://localhost:8000/api';

export interface ChatResponse {
    response: string;
    session_id: string;
    confidence: number;
    mood?: {
        mood: string;
        emoji: string;
        prompt: string;
    };
}

export interface GraphNode {
    id: string;
    label: string;
    type: 'root' | 'category' | 'leaf';
    data: { label: string };
}

export interface GraphEdge {
    id: string;
    source: string;
    target: string;
}

export interface GraphData {
    nodes: GraphNode[];
    edges: GraphEdge[];
}

export const api = {
    async sendMessage(message: string, sessionId: string, trainingMode: boolean = false): Promise<ChatResponse> {
        const res = await fetch(`${API_BASE}/chat/message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                session_id: sessionId,
                training_mode: trainingMode
            })
        });

        if (!res.ok) throw new Error('Failed to send message');
        return res.json();
    },

    async sendFeedback(context: string, botResponse?: string, correctResponse?: string, accepted: boolean = false): Promise<void> {
        await fetch(`${API_BASE}/training/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                context,
                bot_response: botResponse,
                correct_response: correctResponse,
                accepted
            })
        });
    },

    async getGraphData(): Promise<GraphData> {
        const res = await fetch(`${API_BASE}/visualization/graph`);
        if (!res.ok) throw new Error('Failed to fetch graph data');
        return res.json();
    },

    async getProfile(): Promise<ProfileData> {
        const res = await fetch(`${API_BASE}/profile`);
        if (!res.ok) throw new Error('Failed to fetch profile');
        return res.json();
    },

    async getDashboardStats(): Promise<DashboardStats> {
        const res = await fetch(`${API_BASE}/dashboard/stats`);
        if (!res.ok) throw new Error('Failed to fetch dashboard stats');
        return res.json();
    }
};

export interface ProfileData {
    name: string;
    summary: string;
    facts: string[];
    quirks: string[];
    emojis: Record<string, number>;
    tone_markers: Record<string, number>;
    avg_message_length: number;
    training_examples: number;
    common_phrases: string[];
}

export interface DashboardStats {
    total_training_examples: number;
    facts_count: number;
    quirks_count: number;
    emoji_count: number;
    sources: Record<string, number>;
    personality_completion: number;
}
