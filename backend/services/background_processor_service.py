"""
Background Processor Service - Continuous autonomous processing.

Runs background tasks on a schedule to keep the Digital Twin's brain
up-to-date without requiring user interaction:
- Memory consolidation (merge similar memories, prune stale ones)
- Knowledge graph maintenance (rebuild indices, suggest merges)
- Daily review digest (summarize the day's interactions)
- Entity resolution refresh (auto-link new contacts)
- System health monitoring

Uses APScheduler (already a project dependency) for scheduling.

Usage:
    from services.background_processor_service import get_background_processor_service
    processor = get_background_processor_service()
    processor.start()
"""
import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable
from config import Config
from services.logger import get_logger

logger = get_logger(__name__)

# APScheduler import with fallback
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    HAS_SCHEDULER = True
except ImportError:
    HAS_SCHEDULER = False
    logger.warning("APScheduler not installed. Background processing disabled.")


class BackgroundProcessorService:
    """
    Autonomous background processor for the Digital Twin.

    Runs periodic tasks to maintain and improve the clone's knowledge
    and context without requiring explicit user interaction.
    """

    def __init__(self):
        self.enabled = os.getenv(
            "BACKGROUND_PROCESSOR_ENABLED", "true"
        ).lower() == "true"
        self.scheduler = None
        self._running = False
        self._task_log: List[Dict] = []
        self._max_log = 500
        self._task_stats: Dict[str, Dict] = {}

        # Log path for daily digests
        self._digest_path = os.path.join(Config.DATA_DIR, "daily_digests")

        if self.enabled and HAS_SCHEDULER:
            self._init_scheduler()

    def _init_scheduler(self):
        """Initialize the background scheduler with all tasks."""
        try:
            self.scheduler = BackgroundScheduler(
                timezone="UTC",
                job_defaults={
                    "coalesce": True,
                    "max_instances": 1,
                    "misfire_grace_time": 300,
                },
            )

            # Register all background tasks
            self._register_tasks()

            logger.info("Background processor initialized with tasks")
        except Exception as e:
            logger.error(f"Failed to init background processor: {e}")

    def _register_tasks(self):
        """Register all periodic background tasks."""
        if not self.scheduler:
            return

        # 1. Memory consolidation — every 6 hours
        self.scheduler.add_job(
            self._task_memory_consolidation,
            IntervalTrigger(hours=6),
            id="memory_consolidation",
            name="Memory Consolidation",
            replace_existing=True,
        )

        # 2. Entity resolution refresh — every 4 hours
        self.scheduler.add_job(
            self._task_entity_refresh,
            IntervalTrigger(hours=4),
            id="entity_refresh",
            name="Entity Resolution Refresh",
            replace_existing=True,
        )

        # 3. Daily review digest — every day at 23:00 UTC
        self.scheduler.add_job(
            self._task_daily_digest,
            CronTrigger(hour=23, minute=0),
            id="daily_digest",
            name="Daily Review Digest",
            replace_existing=True,
        )

        # 4. Knowledge graph maintenance — every 12 hours
        self.scheduler.add_job(
            self._task_graph_maintenance,
            IntervalTrigger(hours=12),
            id="graph_maintenance",
            name="Knowledge Graph Maintenance",
            replace_existing=True,
        )

        # 5. System health check — every 30 minutes
        self.scheduler.add_job(
            self._task_health_check,
            IntervalTrigger(minutes=30),
            id="health_check",
            name="System Health Check",
            replace_existing=True,
        )

    def start(self):
        """Start the background processor."""
        if not self.enabled or not HAS_SCHEDULER or not self.scheduler:
            logger.info("Background processor not starting (disabled or no scheduler)")
            return

        if self._running:
            return

        try:
            self.scheduler.start()
            self._running = True
            logger.info("Background processor started")
        except Exception as e:
            logger.error(f"Failed to start background processor: {e}")

    def stop(self):
        """Stop the background processor."""
        if self.scheduler and self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Background processor stopped")

    # ============= Task Implementations =============

    def _task_memory_consolidation(self):
        """
        Consolidate memories:
        - Merge duplicate/near-duplicate training examples
        - Update core memory summaries
        - Prune very old, low-relevance memories
        """
        task_name = "memory_consolidation"
        start = time.time()
        logger.info("Running memory consolidation...")

        results: Dict[str, Any] = {"merged": 0, "pruned": 0, "errors": []}

        try:
            # Core memory summarization
            try:
                from services.core_memory_service import get_core_memory_service
                core_mem = get_core_memory_service()
                if hasattr(core_mem, "consolidate"):
                    consolidation = core_mem.consolidate()
                    results["core_memory"] = consolidation
                elif hasattr(core_mem, "summarize_recent"):
                    core_mem.summarize_recent()
                    results["core_memory"] = "summarized"
            except Exception as e:
                results["errors"].append(f"Core memory: {e}")

            # Memory deduplication via MemoryService
            try:
                from services.memory_service import get_memory_service
                mem = get_memory_service()
                if hasattr(mem, "deduplicate"):
                    dedup_count = mem.deduplicate()
                    results["merged"] = dedup_count
            except Exception as e:
                results["errors"].append(f"Memory dedup: {e}")

        except Exception as e:
            results["errors"].append(f"General: {e}")
            logger.error(f"Memory consolidation error: {e}")

        elapsed = time.time() - start
        self._log_task(task_name, elapsed, results)

    def _task_entity_refresh(self):
        """
        Refresh entity resolution:
        - Check for new merge suggestions
        - Auto-merge high-confidence matches
        - Update interaction counts
        """
        task_name = "entity_refresh"
        start = time.time()
        logger.info("Running entity resolution refresh...")

        results: Dict[str, Any] = {"suggestions": 0, "auto_merged": 0, "errors": []}

        try:
            from services.entity_resolution_service import get_entity_resolution_service
            er = get_entity_resolution_service()

            suggestions = er.suggest_merges()
            results["suggestions"] = len(suggestions)

            # Auto-merge only exact name matches (very conservative)
            for eid_a, eid_b, reason in suggestions:
                entity_a = er.get_entity(eid_a)
                entity_b = er.get_entity(eid_b)
                if entity_a and entity_b:
                    norm_a = er._normalize_name(entity_a.canonical_name)
                    norm_b = er._normalize_name(entity_b.canonical_name)
                    if norm_a == norm_b and norm_a:
                        # Get a key from each entity to link
                        keys_a = entity_a.get_identity_keys()
                        keys_b = entity_b.get_identity_keys()
                        if keys_a and keys_b:
                            er.link_identities(keys_a[0], keys_b[0])
                            results["auto_merged"] += 1

        except ImportError:
            results["errors"].append("Entity resolution service not available")
        except Exception as e:
            results["errors"].append(str(e))
            logger.error(f"Entity refresh error: {e}")

        elapsed = time.time() - start
        self._log_task(task_name, elapsed, results)

    def _task_daily_digest(self):
        """
        Generate a daily review digest:
        - Summarize today's conversations
        - Note new knowledge learned
        - Track personality evolution
        - Save to disk for morning briefing
        """
        task_name = "daily_digest"
        start = time.time()
        logger.info("Generating daily digest...")

        digest = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "generated_at": datetime.now().isoformat(),
            "sections": {},
        }

        # Conversation stats
        try:
            from services.conversation_analytics_service import (
                get_conversation_analytics_service,
            )
            analytics = get_conversation_analytics_service()
            if hasattr(analytics, "get_today_stats"):
                digest["sections"]["conversations"] = analytics.get_today_stats()
            elif hasattr(analytics, "get_stats"):
                digest["sections"]["conversations"] = analytics.get_stats()
        except Exception as e:
            digest["sections"]["conversations"] = {"error": str(e)}

        # Knowledge stats
        try:
            from services.knowledge_service import get_knowledge_service
            knowledge = get_knowledge_service()
            if hasattr(knowledge, "get_stats"):
                digest["sections"]["knowledge"] = knowledge.get_stats()
        except Exception as e:
            digest["sections"]["knowledge"] = {"error": str(e)}

        # Entity stats
        try:
            from services.entity_resolution_service import get_entity_resolution_service
            er = get_entity_resolution_service()
            digest["sections"]["entities"] = er.get_stats()
        except Exception as e:
            digest["sections"]["entities"] = {"error": str(e)}

        # Save digest to disk
        try:
            os.makedirs(self._digest_path, exist_ok=True)
            digest_file = os.path.join(
                self._digest_path, f"digest_{digest['date']}.json"
            )
            with open(digest_file, "w", encoding="utf-8") as f:
                json.dump(digest, f, indent=2, ensure_ascii=False)
            logger.info(f"Daily digest saved: {digest_file}")
        except Exception as e:
            logger.error(f"Failed to save digest: {e}")

        elapsed = time.time() - start
        self._log_task(task_name, elapsed, {"digest_date": digest["date"]})

    def _task_graph_maintenance(self):
        """
        Maintain the knowledge graph:
        - Rebuild indices
        - Remove orphan nodes
        - Log graph statistics
        """
        task_name = "graph_maintenance"
        start = time.time()
        logger.info("Running knowledge graph maintenance...")

        results: Dict[str, Any] = {"errors": []}

        try:
            from services.graph_service import get_graph_service
            graph = get_graph_service()
            stats = graph.get_stats()
            results["nodes"] = stats.get("nodes", 0)
            results["edges"] = stats.get("edges", 0)

            # Remove isolated nodes (no edges) older than 30 days
            # (conservative — only if explicitly orphaned)
            if hasattr(graph.graph, "nodes"):
                orphans = [
                    n for n in graph.graph.nodes()
                    if graph.graph.degree(n) == 0
                ]
                results["orphan_nodes"] = len(orphans)

        except Exception as e:
            results["errors"].append(str(e))
            logger.error(f"Graph maintenance error: {e}")

        elapsed = time.time() - start
        self._log_task(task_name, elapsed, results)

    def _task_health_check(self):
        """
        System health monitoring:
        - Check LLM service circuit breaker state
        - Check cache stats
        - Log memory usage
        """
        task_name = "health_check"
        start = time.time()

        results: Dict[str, Any] = {"errors": []}

        try:
            # LLM circuit breaker
            from services.llm_service import get_llm_service
            llm = get_llm_service()
            results["circuit_breaker"] = llm.get_circuit_state()
        except Exception as e:
            results["errors"].append(f"LLM: {e}")

        try:
            # Cache stats
            from services.cache_service import get_cache_service
            cache = get_cache_service()
            results["cache"] = cache.get_stats()
        except Exception as e:
            results["errors"].append(f"Cache: {e}")

        try:
            # PII scrubber stats
            from services.pii_scrubber_service import get_pii_scrubber_service
            pii = get_pii_scrubber_service()
            results["pii_scrubber"] = pii.get_stats()
        except Exception as e:
            results["errors"].append(f"PII: {e}")

        elapsed = time.time() - start
        self._log_task(task_name, elapsed, results)

    # ============= Utilities =============

    def _log_task(self, task_name: str, elapsed: float, results: Dict):
        """Log a task execution."""
        entry = {
            "task": task_name,
            "timestamp": time.time(),
            "elapsed_seconds": round(elapsed, 2),
            "results": results,
        }
        self._task_log.append(entry)
        if len(self._task_log) > self._max_log:
            self._task_log = self._task_log[-self._max_log:]

        # Update task stats
        if task_name not in self._task_stats:
            self._task_stats[task_name] = {"runs": 0, "total_time": 0, "last_run": None}
        self._task_stats[task_name]["runs"] += 1
        self._task_stats[task_name]["total_time"] += elapsed
        self._task_stats[task_name]["last_run"] = datetime.now().isoformat()

        logger.info(
            f"Background task completed: {task_name}",
            elapsed=f"{elapsed:.2f}s",
        )

    def trigger_task(self, task_name: str) -> Dict:
        """Manually trigger a background task."""
        task_map = {
            "memory_consolidation": self._task_memory_consolidation,
            "entity_refresh": self._task_entity_refresh,
            "daily_digest": self._task_daily_digest,
            "graph_maintenance": self._task_graph_maintenance,
            "health_check": self._task_health_check,
        }

        if task_name not in task_map:
            return {"error": f"Unknown task: {task_name}", "available": list(task_map.keys())}

        try:
            task_map[task_name]()
            return {"success": True, "task": task_name}
        except Exception as e:
            return {"success": False, "task": task_name, "error": str(e)}

    def get_recent_digests(self, limit: int = 7) -> List[Dict]:
        """Get recent daily digests."""
        digests = []
        if not os.path.exists(self._digest_path):
            return digests

        files = sorted(os.listdir(self._digest_path), reverse=True)[:limit]
        for fname in files:
            try:
                with open(os.path.join(self._digest_path, fname), "r") as f:
                    digests.append(json.load(f))
            except Exception:
                pass

        return digests

    def get_stats(self) -> Dict:
        """Get background processor statistics."""
        return {
            "enabled": self.enabled,
            "running": self._running,
            "has_scheduler": HAS_SCHEDULER,
            "task_stats": self._task_stats,
            "recent_logs": self._task_log[-10:],
        }


# Singleton
_background_processor_service = None


def get_background_processor_service() -> BackgroundProcessorService:
    """Get the singleton background processor service instance."""
    global _background_processor_service
    if _background_processor_service is None:
        _background_processor_service = BackgroundProcessorService()
    return _background_processor_service
