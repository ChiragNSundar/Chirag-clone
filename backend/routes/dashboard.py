"""
Dashboard Routes - Statistics, analytics, profile, and visualization endpoints.
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
import logging
import time

from services.robustness import get_health_monitor

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])


# ============= Helper Functions =============

def _get_memory_service():
    from services.memory_service import get_memory_service
    return get_memory_service()

def _get_personality_service():
    from services.personality_service import get_personality_service
    return get_personality_service()


# ============= Health & Metrics =============

@router.get("/api/system/metrics")
async def system_metrics():
    """
    Get system performance metrics.
    Useful for monitoring cache efficiency, memory usage, and connection pool status.
    """
    import psutil
    import os
    
    metrics = {
        "timestamp": time.time(),
        "process": {}
    }
    
    # Process memory
    try:
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        metrics["process"] = {
            "memory_mb": round(memory_info.rss / (1024 * 1024), 2),
            "cpu_percent": process.cpu_percent(),
            "threads": process.num_threads()
        }
    except Exception:
        pass
    
    # Cache stats
    try:
        from services.cache_service import get_cache_service
        cache = get_cache_service()
        metrics["cache"] = cache.get_stats()
    except Exception:
        metrics["cache"] = {"available": False}
    
    # HTTP pool stats
    try:
        from services.http_pool import get_http_pool
        pool = get_http_pool()
        if pool._session and not pool._session.closed:
            connector = pool._session.connector
            metrics["http_pool"] = {
                "active": True,
                "limit": connector.limit if connector else 0,
                "limit_per_host": connector.limit_per_host if connector else 0
            }
        else:
            metrics["http_pool"] = {"active": False}
    except Exception:
        metrics["http_pool"] = {"available": False}
    
    return metrics


@router.get("/api/health")
async def health_check(detailed: bool = False):
    """
    Health Check Endpoint.
    
    Args:
        detailed: If true, includes service-level health status
        
    Returns:
        Health status with optional service details
    """
    from config import Config
    
    health_monitor = get_health_monitor()
    
    # Basic health info
    response = {
        "status": "healthy",
        "version": "2.3.0",
        "framework": "FastAPI",
        "timestamp": time.time()
    }
    
    if detailed:
        # Check LLM service
        try:
            from services.llm_service import get_llm_service
            llm = get_llm_service()
            circuit_state = llm.get_circuit_state()
            health_monitor.update_status(
                "llm",
                not circuit_state.get("is_open", False),
                f"Circuit: {circuit_state.get('state', 'UNKNOWN')}"
            )
        except Exception as e:
            health_monitor.update_status("llm", False, str(e))
        
        # Check memory/vector service
        try:
            memory = _get_memory_service()
            stats = memory.get_training_stats()
            health_monitor.update_status("memory", True, f"{stats.get('total_entries', 0)} entries")
        except Exception as e:
            health_monitor.update_status("memory", False, str(e))
        
        # Check voice service
        try:
            from services.voice_service import get_voice_service
            voice = get_voice_service()
            voice_status = voice.get_status()
            health_monitor.update_status(
                "voice",
                voice_status.get("tts_available", False) or voice_status.get("stt_available", False),
                f"TTS: {voice_status.get('tts_available')}, STT: {voice_status.get('stt_available')}"
            )
        except Exception as e:
            health_monitor.update_status("voice", False, str(e))
        
        # Check knowledge service
        try:
            from services.knowledge_service import get_knowledge_service
            knowledge = get_knowledge_service()
            doc_count = len(knowledge.list_documents()) if hasattr(knowledge, 'list_documents') else 0
            health_monitor.update_status("knowledge", True, f"{doc_count} documents")
        except Exception as e:
            health_monitor.update_status("knowledge", False, str(e))
        
        # Get overall health
        is_healthy, degraded_services, message = health_monitor.get_overall_health()
        
        response["status"] = "healthy" if is_healthy else "unhealthy"
        response["message"] = message
        response["services"] = health_monitor.get_all_status()
        
        if degraded_services:
            response["degraded_services"] = degraded_services
            if is_healthy:
                response["status"] = "degraded"
    
    return response


# ============= Dashboard Stats =============

@router.get("/api/dashboard/stats")
async def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        memory = _get_memory_service()
        personality = _get_personality_service().get_profile()
        stats = memory.get_training_stats()
        
        return {
            "total_training_examples": stats.get('total_examples', 0),
            "facts_count": len(personality.facts),
            "quirks_count": len(personality.typing_quirks),
            "emoji_count": len(personality.emoji_patterns),
            "sources": stats.get('sources', {}),
            "personality_completion": min(100, int(
                (len(personality.facts) * 5) + 
                (len(personality.typing_quirks) * 3) + 
                (stats.get('total_examples', 0) * 0.5)
            ))
        }
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        return {
            "total_training_examples": 0,
            "facts_count": 0,
            "quirks_count": 0,
            "emoji_count": 0,
            "sources": {},
            "personality_completion": 0
        }


# ============= Profile =============

@router.get("/api/profile")
async def get_profile():
    """Get full personality profile for the About Me page"""
    try:
        personality = _get_personality_service().get_profile()
        memory = _get_memory_service()
        stats = memory.get_training_stats()
        
        # Generate AI summary
        tone_desc = []
        if personality.tone_markers.get('casual', 0) > 0.6:
            tone_desc.append("casual and laid-back")
        if personality.tone_markers.get('sarcastic', 0) > 0.4:
            tone_desc.append("witty with a hint of sarcasm")
        if personality.tone_markers.get('enthusiastic', 0) > 0.6:
            tone_desc.append("enthusiastic and energetic")
        if personality.tone_markers.get('brief', 0) > 0.6:
            tone_desc.append("concise and to-the-point")
        
        summary = f"{personality.name} communicates in a {', '.join(tone_desc) if tone_desc else 'balanced'} style. "
        if personality.typing_quirks:
            summary += f"They often use phrases like '{personality.typing_quirks[0]}'. "
        if personality.emoji_patterns:
            top_emoji = list(personality.emoji_patterns.keys())[:3]
            summary += f"Favorite emojis include {' '.join(top_emoji)}. "
        
        return {
            "name": personality.name,
            "summary": summary,
            "facts": personality.facts,
            "quirks": personality.typing_quirks,
            "emojis": personality.emoji_patterns,
            "tone_markers": personality.tone_markers,
            "avg_message_length": personality.avg_message_length,
            "training_examples": stats.get('total_examples', 0),
            "common_phrases": personality.common_phrases[:10]
        }
    except Exception as e:
        logger.error(f"Profile error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Visualization =============

@router.get("/api/visualization/graph")
async def get_memory_graph():
    """Get graph data for visualization"""
    try:
        personality = _get_personality_service().get_profile()
        
        # Build graph structure compatible with React Flow or similar
        nodes = []
        edges = []
        
        # Central Node
        nodes.append({"id": "root", "label": personality.name, "type": "root", "data": {"label": personality.name}})
        
        # Categories
        categories = ["Personality", "Facts", "Quirks"]
        for cat in categories:
            cat_id = f"cat_{cat.lower()}"
            nodes.append({"id": cat_id, "label": cat, "type": "category", "data": {"label": cat}})
            edges.append({"id": f"e_root_{cat_id}", "source": "root", "target": cat_id})
            
        # Add Quirks
        for i, quirk in enumerate(personality.typing_quirks[:5]):
            node_id = f"quirk_{i}"
            nodes.append({"id": node_id, "label": quirk, "type": "leaf", "data": {"label": quirk}})
            edges.append({"id": f"e_cat_quirks_{node_id}", "source": "cat_quirks", "target": node_id})
            
        # Add Facts
        for i, fact in enumerate(personality.facts[:5]):
            node_id = f"fact_{i}"
            nodes.append({"id": node_id, "label": fact[:20]+"...", "type": "leaf", "data": {"label": fact}})
            edges.append({"id": f"e_cat_facts_{node_id}", "source": "cat_facts", "target": node_id})
            
        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        logger.error(f"Graph error: {e}")
        return {"nodes": [], "edges": []}


# ============= Analytics =============

@router.get("/api/analytics/detailed")
async def get_detailed_analytics():
    """Get detailed analytics for dashboard visualizations"""
    try:
        memory = _get_memory_service()
        personality = _get_personality_service().get_profile()
        stats = memory.get_training_stats()
        
        return {
            "training": {
                "total_examples": stats.get('total_examples', 0),
                "sources": stats.get('sources', {}),
                "recent_activity": stats.get('recent_activity', [])
            },
            "personality": {
                "facts_count": len(personality.facts),
                "quirks_count": len(personality.typing_quirks),
                "emoji_count": len(personality.emoji_patterns),
                "avg_message_length": personality.avg_message_length,
                "tone_markers": personality.tone_markers,
                "common_phrases": personality.common_phrases[:20],
                "top_emojis": dict(sorted(personality.emoji_patterns.items(), key=lambda x: x[1], reverse=True)[:10])
            },
            "learning_progress": {
                "personality_score": min(100, int(
                    (len(personality.facts) * 5) + 
                    (len(personality.typing_quirks) * 3) + 
                    (stats.get('total_examples', 0) * 0.5)
                )),
                "data_sources_count": len(stats.get('sources', {}))
            }
        }
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        return {
            "training": {"total_examples": 0, "sources": {}, "recent_activity": []},
            "personality": {"facts_count": 0, "quirks_count": 0, "emoji_count": 0, "avg_message_length": 0, "tone_markers": {}, "common_phrases": [], "top_emojis": {}},
            "learning_progress": {"personality_score": 0, "data_sources_count": 0}
        }


@router.get("/api/analytics/conversations")
async def get_conversation_analytics():
    """Get comprehensive conversation analytics."""
    try:
        from services.analytics_service import get_analytics_service
        service = get_analytics_service()
        return service.get_conversation_analytics()
    except Exception as e:
        logger.error(f"Conversation analytics error: {e}")
        return {}


@router.get("/api/analytics/topics")
async def get_topic_distribution(limit: int = 20):
    """Get topic distribution from conversations."""
    try:
        from services.analytics_service import get_analytics_service
        service = get_analytics_service()
        return service.get_topic_distribution(limit=limit)
    except Exception as e:
        logger.error(f"Topic distribution error: {e}")
        return {"topics": []}
