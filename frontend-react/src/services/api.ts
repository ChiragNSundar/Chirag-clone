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
    type: 'root' | 'category' | 'leaf' | 'core';
    data: { label: string };
    content?: string;
    metadata?: Record<string, unknown>;
}

export interface GraphEdge {
    id: string;
    source: string;
    target: string;
    animated?: boolean;
}

export interface GraphData {
    nodes: GraphNode[];
    edges: GraphEdge[];
}

// ============= Knowledge Types =============

export interface KnowledgeDocument {
    id: string;
    title: string;
    category: string;
    source: string;
    created_at: string;
    chunks_count: number;
}

export interface KnowledgeStats {
    total_documents: number;
    total_chunks: number;
    categories: Record<string, number>;
}

export interface KnowledgeQueryResult {
    id: string;
    content: string;
    document_id: string;
    score: number;
    metadata: Record<string, unknown>;
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
    },

    async resetLearning(): Promise<{ success: boolean }> {
        const res = await fetch(`${API_BASE}/training/reset`, { method: 'DELETE' });
        return res.json();
    },

    async getTrainingPrompt(): Promise<{ prompt: string }> {
        const res = await fetch(`${API_BASE}/training/chat/prompt`);
        if (!res.ok) throw new Error('Failed to get prompt');
        return res.json();
    },

    async submitTrainingResponse(botMessage: string, userResponse: string): Promise<{ success: boolean }> {
        const res = await fetch(`${API_BASE}/training/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bot_message: botMessage, user_response: userResponse })
        });
        if (!res.ok) throw new Error('Failed to submit response');
        return res.json();
    },

    // ============= Knowledge API =============

    async getKnowledgeDocuments(): Promise<{ documents: KnowledgeDocument[] }> {
        const res = await fetch(`${API_BASE}/knowledge/documents`);
        return res.json();
    },

    async getKnowledgeStats(): Promise<KnowledgeStats> {
        const res = await fetch(`${API_BASE}/knowledge/stats`);
        return res.json();
    },

    async uploadKnowledgeFile(file: File, category: string = 'general'): Promise<{ success: boolean; message: string }> {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('category', category);

        const res = await fetch(`${API_BASE}/knowledge/upload`, {
            method: 'POST',
            body: formData
        });
        return res.json();
    },

    async deleteKnowledgeDocument(docId: string): Promise<{ success: boolean }> {
        const res = await fetch(`${API_BASE}/knowledge/document/${docId}`, {
            method: 'DELETE'
        });
        return res.json();
    },

    async queryKnowledge(query: string, nResults: number = 5): Promise<{ results: KnowledgeQueryResult[] }> {
        const res = await fetch(`${API_BASE}/knowledge/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, n_results: nResults })
        });
        return res.json();
    },

    async addKnowledgeUrl(url: string): Promise<{ success: boolean }> {
        const res = await fetch(`${API_BASE}/knowledge/url`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        if (!res.ok) throw new Error('Failed to add URL');
        return res.json();
    },

    async addKnowledgeText(content: string, title: string): Promise<{ success: boolean }> {
        const res = await fetch(`${API_BASE}/knowledge/text`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content, title })
        });
        if (!res.ok) throw new Error('Failed to add text');
        return res.json();
    },

    // ============= Deep Research API =============

    async deepResearch(query: string, maxDepth: number = 3): Promise<DeepResearchResult> {
        const res = await fetch(`${API_BASE}/research/deep`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, max_depth: maxDepth })
        });
        if (!res.ok) throw new Error('Research failed');
        return res.json();
    },

    async getResearchStatus(): Promise<{ available: boolean; features: string[] }> {
        const res = await fetch(`${API_BASE}/research/status`);
        if (!res.ok) return { available: false, features: [] };
        return res.json();
    },

    // ============= Rewind Memory API =============

    async queryRewind(question: string, timeRangeMinutes?: number): Promise<RewindQueryResult> {
        const res = await fetch(`${API_BASE}/rewind/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, time_range_minutes: timeRangeMinutes })
        });
        if (!res.ok) throw new Error('Rewind query failed');
        return res.json();
    },

    async getRewindStatus(): Promise<RewindStatus> {
        const res = await fetch(`${API_BASE}/rewind/status`);
        if (!res.ok) return { enabled: false, paused: true, frame_count: 0 };
        return res.json();
    },

    async getRewindTimeline(limit: number = 20): Promise<{ timeline: RewindTimelineEntry[] }> {
        const res = await fetch(`${API_BASE}/rewind/timeline?limit=${limit}`);
        if (!res.ok) return { timeline: [] };
        return res.json();
    },

    async pauseRewind(): Promise<{ success: boolean }> {
        const res = await fetch(`${API_BASE}/rewind/pause`, { method: 'POST' });
        return res.json();
    },

    async resumeRewind(): Promise<{ success: boolean }> {
        const res = await fetch(`${API_BASE}/rewind/resume`, { method: 'POST' });
        return res.json();
    },

    async clearRewind(): Promise<{ success: boolean; frames_cleared: number }> {
        const res = await fetch(`${API_BASE}/rewind/clear`, { method: 'DELETE' });
        return res.json();
    },

    // ============= Voice API =============

    async getVoiceStatus(): Promise<VoiceStatus> {
        const res = await fetch(`${API_BASE}/voice/status`);
        if (!res.ok) return { tts_available: false, stt_available: false };
        return res.json();
    },

    // ============= Health API =============

    async getHealth(detailed: boolean = false): Promise<HealthStatus> {
        const res = await fetch(`${API_BASE}/health?detailed=${detailed}`);
        return res.json();
    },

    async validatePin(pin: string): Promise<boolean> {
        const formData = new FormData();
        formData.append('pin', pin);

        const res = await fetch(`${API_BASE}/training/auth`, {
            method: 'POST',
            body: formData
        });

        return res.ok;
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

// ============= Deep Research Types =============

export interface DeepResearchSource {
    url: string;
    title: string;
    content_preview: string;
    relevance_score: number;
}

export interface DeepResearchResult {
    success: boolean;
    query: string;
    answer: string;
    sources: DeepResearchSource[];
    follow_up_queries: string[];
    total_sources_checked: number;
    research_time_seconds: number;
}

// ============= Rewind Types =============

export interface RewindStatus {
    enabled: boolean;
    paused: boolean;
    frame_count: number;
    max_frames?: number;
    buffer_minutes?: number;
    oldest_frame?: string;
    newest_frame?: string;
}

export interface RewindTimelineEntry {
    timestamp: string;
    age_minutes: number;
    window_name: string;
    analyzed: boolean;
    preview: string;
}

export interface RewindQueryResult {
    success: boolean;
    answer?: string;
    error?: string;
    frames_analyzed?: number;
    time_range?: {
        oldest: string | null;
        newest: string | null;
    };
}

// ============= Voice Types =============

export interface VoiceStatus {
    tts_available: boolean;
    stt_available: boolean;
    local_tts_available?: boolean;
    local_stt_available?: boolean;
    voice_id?: string;
}

// ============= Health Types =============

export interface HealthStatus {
    status: 'healthy' | 'degraded' | 'unhealthy';
    version: string;
    timestamp: number;
    services?: Record<string, { healthy: boolean; message?: string }>;
}

