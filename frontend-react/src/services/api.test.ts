/**
 * API Service Tests
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { api } from './api';

describe('API Service', () => {
    beforeEach(() => {
        vi.resetAllMocks();
        global.fetch = vi.fn();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    describe('sendMessage', () => {
        it('sends a chat message successfully', async () => {
            const mockResponse = {
                response: 'Hello!',
                session_id: 'test-session',
                confidence: 0.95,
                mood: { mood: 'happy', emoji: '😊', prompt: '' }
            };

            (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(mockResponse)
            });

            const result = await api.sendMessage('Hi', 'test-session');

            expect(global.fetch).toHaveBeenCalledWith(
                'http://localhost:8000/api/chat/message',
                expect.objectContaining({
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: 'Hi',
                        session_id: 'test-session',
                        training_mode: false
                    })
                })
            );
            expect(result).toEqual(mockResponse);
        });

        it('throws error on failed request', async () => {
            (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: false,
                status: 500
            });

            await expect(api.sendMessage('Hi', 'session')).rejects.toThrow('Failed to send message');
        });
    });

    describe('getProfile', () => {
        it('fetches profile data', async () => {
            const mockProfile = {
                name: 'Chirag',
                summary: 'Test summary',
                facts: ['Fact 1'],
                quirks: ['Quirk 1']
            };

            (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(mockProfile)
            });

            const result = await api.getProfile();

            expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/api/profile');
            expect(result.name).toBe('Chirag');
        });
    });

    describe('getDashboardStats', () => {
        it('fetches dashboard stats', async () => {
            const mockStats = {
                total_training_examples: 100,
                facts_count: 25,
                quirks_count: 10.
            };

            (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(mockStats)
            });

            const result = await api.getDashboardStats();

            expect(result.total_training_examples).toBe(100);
        });
    });

    describe('addFact', () => {
        it('adds a fact successfully', async () => {
            (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ success: true, facts: ['New fact'] })
            });

            const result = await api.addFact('New fact');

            expect(global.fetch).toHaveBeenCalledWith(
                'http://localhost:8000/api/training/fact',
                expect.objectContaining({
                    method: 'POST',
                    body: JSON.stringify({ fact: 'New fact' })
                })
            );
            expect(result.success).toBe(true);
        });
    });

    describe('deleteFact', () => {
        it('deletes a fact by index', async () => {
            (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ success: true, facts: [] })
            });

            const result = await api.deleteFact(0);

            expect(global.fetch).toHaveBeenCalledWith(
                'http://localhost:8000/api/training/facts/0',
                expect.objectContaining({ method: 'DELETE' })
            );
            expect(result.success).toBe(true);
        });
    });

    describe('sendFeedback', () => {
        it('sends positive feedback', async () => {
            (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true });

            await api.sendFeedback('context', 'bot response', undefined, true);

            expect(global.fetch).toHaveBeenCalledWith(
                'http://localhost:8000/api/training/feedback',
                expect.objectContaining({
                    method: 'POST',
                    body: expect.stringContaining('"accepted":true')
                })
            );
        });

        it('sends correction feedback', async () => {
            (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true });

            await api.sendFeedback('context', 'wrong response', 'correct response', false);

            expect(global.fetch).toHaveBeenCalledWith(
                'http://localhost:8000/api/training/feedback',
                expect.objectContaining({
                    body: expect.stringContaining('"correct_response":"correct response"')
                })
            );
        });
    });

    describe('getGraphData', () => {
        it('fetches visualization graph data', async () => {
            const mockGraph = {
                nodes: [{ id: 'root', label: 'Chirag', type: 'root', data: { label: 'Chirag' } }],
                edges: []
            };

            (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(mockGraph)
            });

            const result = await api.getGraphData();

            expect(result.nodes).toHaveLength(1);
            expect(result.nodes[0].type).toBe('root');
        });
    });

    describe('addTrainingExample', () => {
        it('adds a training example', async () => {
            (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ success: true })
            });

            const result = await api.addTrainingExample('User says hi', 'Reply with hello');

            expect(global.fetch).toHaveBeenCalledWith(
                'http://localhost:8000/api/training/example',
                expect.objectContaining({
                    method: 'POST',
                    body: JSON.stringify({ context: 'User says hi', response: 'Reply with hello' })
                })
            );
            expect(result.success).toBe(true);
        });
    });
});
