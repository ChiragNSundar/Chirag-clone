"""
Autopilot Executor Service - Execute (not just draft) social messages.

Upgrades the existing autopilot system from "draft-only" to "auto-execute"
with configurable confidence thresholds, rate limits, and audit trails.

The executor wraps existing bot services (Discord, Telegram, Slack, etc.)
and adds execution capabilities with safety guardrails.

Usage:
    from services.autopilot_executor_service import get_autopilot_executor_service
    executor = get_autopilot_executor_service()
    result = executor.execute_draft(draft_id="abc123", approval="auto")
"""
import os
import json
import time
import uuid
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from config import Config
from services.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Draft:
    """A pending message draft."""
    draft_id: str
    platform: str
    recipient_id: str
    recipient_name: str
    content: str
    confidence: float           # 0.0 - 1.0, how confident the AI is
    context: str = ""           # The message/thread it's replying to
    created_at: float = field(default_factory=time.time)
    status: str = "pending"     # pending, approved, executed, rejected, failed
    executed_at: Optional[float] = None
    error: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result of executing a draft."""
    success: bool
    draft_id: str
    platform: str
    status: str
    message: str = ""
    error: Optional[str] = None


class AutopilotExecutorService:
    """
    Execution layer for the autopilot system.

    Modes:
    - "draft_only": Never auto-send (current behavior, safest)
    - "auto_high": Auto-send if confidence >= 0.85
    - "auto_medium": Auto-send if confidence >= 0.70
    - "auto_all": Auto-send everything (use with caution)

    Safety features:
    - Confidence threshold filtering
    - Per-platform rate limits
    - Execution audit log
    - Cooldown between messages
    - Content length limits
    """

    EXECUTION_MODES = {
        "draft_only": 1.01,    # Never auto-execute (threshold > 1.0)
        "auto_high": 0.85,
        "auto_medium": 0.70,
        "auto_all": 0.0,
    }

    def __init__(self):
        self.mode = os.getenv("AUTOPILOT_EXEC_MODE", "draft_only")
        self.confidence_threshold = self.EXECUTION_MODES.get(
            self.mode, self.EXECUTION_MODES["draft_only"]
        )
        self.max_messages_per_hour = int(os.getenv("AUTOPILOT_MAX_PER_HOUR", "20"))
        self.cooldown_seconds = int(os.getenv("AUTOPILOT_COOLDOWN_SECONDS", "30"))
        self.max_content_length = 2000

        # State
        self._drafts: Dict[str, Draft] = {}
        self._execution_log: List[Dict] = []
        self._last_execution_time: Dict[str, float] = {}  # platform -> timestamp
        self._hourly_counts: Dict[str, int] = {}  # platform -> count
        self._hourly_reset: float = time.time()

        # Load persisted drafts
        self._drafts_path = os.path.join(Config.DATA_DIR, "autopilot_drafts.json")
        self._load_drafts()

        logger.info(
            "Autopilot executor initialized",
            mode=self.mode,
            threshold=self.confidence_threshold,
        )

    def _load_drafts(self):
        """Load pending drafts from disk."""
        if os.path.exists(self._drafts_path):
            try:
                with open(self._drafts_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for did, ddata in data.items():
                    self._drafts[did] = Draft(**ddata)
            except Exception as e:
                logger.error(f"Failed to load drafts: {e}")

    def _save_drafts(self):
        """Save drafts to disk."""
        try:
            os.makedirs(os.path.dirname(self._drafts_path), exist_ok=True)
            data = {}
            for did, draft in self._drafts.items():
                data[did] = {
                    "draft_id": draft.draft_id,
                    "platform": draft.platform,
                    "recipient_id": draft.recipient_id,
                    "recipient_name": draft.recipient_name,
                    "content": draft.content,
                    "confidence": draft.confidence,
                    "context": draft.context,
                    "created_at": draft.created_at,
                    "status": draft.status,
                    "executed_at": draft.executed_at,
                    "error": draft.error,
                }
            with open(self._drafts_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save drafts: {e}")

    def _reset_hourly_if_needed(self):
        """Reset hourly counters if an hour has passed."""
        if time.time() - self._hourly_reset > 3600:
            self._hourly_counts.clear()
            self._hourly_reset = time.time()

    def _check_rate_limit(self, platform: str) -> bool:
        """Check if we're within rate limits for a platform."""
        self._reset_hourly_if_needed()
        count = self._hourly_counts.get(platform, 0)
        return count < self.max_messages_per_hour

    def _check_cooldown(self, platform: str) -> bool:
        """Check if cooldown period has elapsed."""
        last = self._last_execution_time.get(platform, 0)
        return (time.time() - last) >= self.cooldown_seconds

    # ============= Draft Management =============

    def create_draft(
        self,
        platform: str,
        recipient_id: str,
        recipient_name: str,
        content: str,
        confidence: float = 0.5,
        context: str = "",
    ) -> Draft:
        """
        Create a new message draft.

        If confidence >= threshold and mode allows, will auto-execute.

        Returns:
            The created Draft object.
        """
        draft_id = str(uuid.uuid4())[:8]
        draft = Draft(
            draft_id=draft_id,
            platform=platform,
            recipient_id=recipient_id,
            recipient_name=recipient_name,
            content=content[:self.max_content_length],
            confidence=confidence,
            context=context,
        )

        self._drafts[draft_id] = draft
        self._save_drafts()

        # Check if we should auto-execute
        if (
            confidence >= self.confidence_threshold
            and self._check_rate_limit(platform)
            and self._check_cooldown(platform)
        ):
            logger.info(
                "Auto-executing draft",
                draft_id=draft_id,
                platform=platform,
                confidence=confidence,
            )
            self.execute_draft(draft_id)

        return draft

    def execute_draft(self, draft_id: str) -> ExecutionResult:
        """
        Execute (send) a draft message.

        Args:
            draft_id: ID of the draft to execute.

        Returns:
            ExecutionResult with success/failure details.
        """
        draft = self._drafts.get(draft_id)
        if not draft:
            return ExecutionResult(
                success=False,
                draft_id=draft_id,
                platform="unknown",
                status="not_found",
                error="Draft not found",
            )

        if draft.status == "executed":
            return ExecutionResult(
                success=False,
                draft_id=draft_id,
                platform=draft.platform,
                status="already_executed",
                error="Draft was already executed",
            )

        # Rate limit check
        if not self._check_rate_limit(draft.platform):
            return ExecutionResult(
                success=False,
                draft_id=draft_id,
                platform=draft.platform,
                status="rate_limited",
                error=f"Rate limit exceeded for {draft.platform} "
                      f"({self.max_messages_per_hour}/hour)",
            )

        # Cooldown check
        if not self._check_cooldown(draft.platform):
            remaining = self.cooldown_seconds - (
                time.time() - self._last_execution_time.get(draft.platform, 0)
            )
            return ExecutionResult(
                success=False,
                draft_id=draft_id,
                platform=draft.platform,
                status="cooldown",
                error=f"Cooldown active, {remaining:.0f}s remaining",
            )

        # Execute via platform-specific bot service
        try:
            success = self._send_via_platform(draft)

            if success:
                draft.status = "executed"
                draft.executed_at = time.time()

                # Update rate tracking
                self._last_execution_time[draft.platform] = time.time()
                self._reset_hourly_if_needed()
                self._hourly_counts[draft.platform] = (
                    self._hourly_counts.get(draft.platform, 0) + 1
                )

                self._add_execution_log(draft, "success")
                self._save_drafts()

                logger.info(
                    "Draft executed successfully",
                    draft_id=draft_id,
                    platform=draft.platform,
                    recipient=draft.recipient_name,
                )

                return ExecutionResult(
                    success=True,
                    draft_id=draft_id,
                    platform=draft.platform,
                    status="executed",
                    message=f"Message sent to {draft.recipient_name} on {draft.platform}",
                )
            else:
                draft.status = "failed"
                draft.error = "Platform send failed"
                self._add_execution_log(draft, "failed")
                self._save_drafts()

                return ExecutionResult(
                    success=False,
                    draft_id=draft_id,
                    platform=draft.platform,
                    status="failed",
                    error="Failed to send via platform API",
                )

        except Exception as e:
            draft.status = "failed"
            draft.error = str(e)
            self._add_execution_log(draft, "error", str(e))
            self._save_drafts()

            logger.error("Draft execution failed", draft_id=draft_id, error=str(e))
            return ExecutionResult(
                success=False,
                draft_id=draft_id,
                platform=draft.platform,
                status="error",
                error=str(e),
            )

    def _send_via_platform(self, draft: Draft) -> bool:
        """
        Send a message via the appropriate platform bot service.

        Returns True on success, False on failure.
        """
        platform = draft.platform.lower()

        try:
            if platform == "discord":
                from services.discord_bot_service import get_discord_bot_service
                bot = get_discord_bot_service()
                if hasattr(bot, "send_message"):
                    return bot.send_message(draft.recipient_id, draft.content)

            elif platform == "telegram":
                from services.telegram_bot_service import get_telegram_bot_service
                bot = get_telegram_bot_service()
                if hasattr(bot, "send_message"):
                    return bot.send_message(draft.recipient_id, draft.content)

            elif platform == "slack":
                from services.slack_bot_service import get_slack_bot_service
                bot = get_slack_bot_service()
                if hasattr(bot, "send_message"):
                    return bot.send_message(draft.recipient_id, draft.content)

            elif platform == "gmail":
                from services.gmail_bot_service import get_gmail_bot_service
                bot = get_gmail_bot_service()
                if hasattr(bot, "send_draft"):
                    return bot.send_draft(draft.recipient_id, draft.content)

            elif platform == "twitter":
                from services.twitter_bot_service import get_twitter_bot_service
                bot = get_twitter_bot_service()
                if hasattr(bot, "post_tweet"):
                    return bot.post_tweet(draft.content)

            elif platform == "whatsapp":
                from services.whatsapp_bot_service import get_whatsapp_bot_service
                bot = get_whatsapp_bot_service()
                if hasattr(bot, "send_message"):
                    return bot.send_message(draft.recipient_id, draft.content)

            logger.warning(f"No send_message method for platform: {platform}")
            return False

        except ImportError as e:
            logger.warning(f"Platform service not available: {platform} - {e}")
            return False
        except Exception as e:
            logger.error(f"Platform send error: {e}")
            return False

    def reject_draft(self, draft_id: str) -> bool:
        """Reject a draft (will not be sent)."""
        draft = self._drafts.get(draft_id)
        if not draft:
            return False
        draft.status = "rejected"
        self._save_drafts()
        return True

    def get_pending_drafts(self, platform: Optional[str] = None) -> List[Draft]:
        """Get all pending (unexecuted) drafts."""
        drafts = [d for d in self._drafts.values() if d.status == "pending"]
        if platform:
            drafts = [d for d in drafts if d.platform == platform]
        drafts.sort(key=lambda d: d.created_at, reverse=True)
        return drafts

    def get_draft(self, draft_id: str) -> Optional[Draft]:
        """Get a specific draft."""
        return self._drafts.get(draft_id)

    def _add_execution_log(self, draft: Draft, status: str,
                           error: Optional[str] = None):
        """Add to execution audit log."""
        self._execution_log.append({
            "timestamp": time.time(),
            "draft_id": draft.draft_id,
            "platform": draft.platform,
            "recipient": draft.recipient_name,
            "status": status,
            "confidence": draft.confidence,
            "error": error,
        })
        # Keep bounded
        if len(self._execution_log) > 1000:
            self._execution_log = self._execution_log[-1000:]

    def get_stats(self) -> Dict:
        """Get executor statistics."""
        total = len(self._drafts)
        by_status = {}
        by_platform = {}

        for draft in self._drafts.values():
            by_status[draft.status] = by_status.get(draft.status, 0) + 1
            by_platform[draft.platform] = by_platform.get(draft.platform, 0) + 1

        return {
            "mode": self.mode,
            "confidence_threshold": self.confidence_threshold,
            "total_drafts": total,
            "by_status": by_status,
            "by_platform": by_platform,
            "max_per_hour": self.max_messages_per_hour,
            "cooldown_seconds": self.cooldown_seconds,
            "executions_logged": len(self._execution_log),
        }


# Singleton
_autopilot_executor_service = None


def get_autopilot_executor_service() -> AutopilotExecutorService:
    """Get the singleton autopilot executor service instance."""
    global _autopilot_executor_service
    if _autopilot_executor_service is None:
        _autopilot_executor_service = AutopilotExecutorService()
    return _autopilot_executor_service
