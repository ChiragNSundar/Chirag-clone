const API_BASE = 'http://localhost:8000/api';

export interface ThinkingStep {
    step: number;
    content: string;
}

export interface ThinkingData {
    thinking: string;
    steps: ThinkingStep[];
    has_thinking: boolean;
}

export interface ChatResponse {
    response: string;
    session_id: string;
    confidence: number;
    mood?: {
        mood: string;
        emoji: string;
        prompt: string;
    };
    thinking?: ThinkingData;
    emotion?: {
        emotion: string;
        emoji: string;
        intensity: number;
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
    },

    async addJournalEntry(content: string): Promise<{ success: boolean }> {
        const res = await fetch(`${API_BASE}/training/journal`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        });
        if (!res.ok) throw new Error('Failed to add journal entry');
        return res.json();
    },

    async addFact(fact: string): Promise<{ success: boolean; facts: string[] }> {
        const res = await fetch(`${API_BASE}/training/fact`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fact })
        });
        if (!res.ok) throw new Error('Failed to add fact');
        return res.json();
    },

    async getFacts(): Promise<{ facts: string[] }> {
        const res = await fetch(`${API_BASE}/training/facts`);
        if (!res.ok) throw new Error('Failed to get facts');
        return res.json();
    },

    async deleteFact(index: number): Promise<{ success: boolean; facts: string[] }> {
        const res = await fetch(`${API_BASE}/training/facts/${index}`, {
            method: 'DELETE'
        });
        if (!res.ok) throw new Error('Failed to delete fact');
        return res.json();
    },

    async addTrainingExample(context: string, response: string): Promise<{ success: boolean }> {
        const res = await fetch(`${API_BASE}/training/example`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ context, response })
        });
        if (!res.ok) throw new Error('Failed to add example');
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
