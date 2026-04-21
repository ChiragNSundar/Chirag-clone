"""
Agentic Routes - API endpoints for shell execution, sandbox, autopilot execution,
entity resolution, and background processing.

These endpoints expose the new agentic capabilities added in v3.2.
"""
from fastapi import APIRouter, HTTPException, Body
from typing import Optional, List, Dict
from services.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/agentic", tags=["Agentic"])


# ============= Shell Execution =============

@router.post("/shell/execute")
async def execute_shell_command(
    command: str = Body(...),
    args: List[str] = Body(default=[]),
    cwd: Optional[str] = Body(default=None),
    approval_token: Optional[str] = Body(default=None),
):
    """Execute a shell command within the safety sandbox."""
    from services.shell_execution_service import get_shell_execution_service
    shell = get_shell_execution_service()
    result = shell.execute(
        command=command,
        args=args,
        cwd=cwd,
        approval_token=approval_token,
    )
    return {
        "success": result.success,
        "command": result.command,
        "args": result.args,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "execution_time_ms": result.execution_time_ms,
        "error": result.error,
        "approved": result.approved,
    }


@router.post("/shell/approve/{token}")
async def approve_shell_command(token: str):
    """Approve a pending shell command by its token."""
    from services.shell_execution_service import get_shell_execution_service
    shell = get_shell_execution_service()
    result = shell.approve(token)
    if result is None:
        raise HTTPException(status_code=404, detail="Approval token not found or expired")
    return {
        "success": result.success,
        "command": result.command,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "error": result.error,
    }


@router.get("/shell/pending")
async def get_pending_approvals():
    """Get list of shell commands pending approval."""
    from services.shell_execution_service import get_shell_execution_service
    shell = get_shell_execution_service()
    return {"pending": shell.get_pending_approvals()}


@router.get("/shell/stats")
async def get_shell_stats():
    """Get shell execution statistics."""
    from services.shell_execution_service import get_shell_execution_service
    return get_shell_execution_service().get_stats()


# ============= Python Sandbox =============

@router.post("/sandbox/execute")
async def execute_sandbox_code(
    code: str = Body(...),
    session_id: Optional[str] = Body(default=None),
    timeout: Optional[int] = Body(default=None),
):
    """Execute Python code in the agentic sandbox."""
    from services.sandbox_service import get_sandbox_service
    sandbox = get_sandbox_service()
    result = sandbox.execute(code=code, session_id=session_id, timeout=timeout)
    return {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "execution_time_ms": result.execution_time_ms,
        "error": result.error,
        "error_type": result.error_type,
        "truncated": result.truncated,
    }


@router.delete("/sandbox/session/{session_id}")
async def clear_sandbox_session(session_id: str):
    """Clear a sandbox session's persistent namespace."""
    from services.sandbox_service import get_sandbox_service
    get_sandbox_service().clear_session(session_id)
    return {"success": True, "message": f"Session '{session_id}' cleared"}


@router.get("/sandbox/stats")
async def get_sandbox_stats():
    """Get sandbox execution statistics."""
    from services.sandbox_service import get_sandbox_service
    return get_sandbox_service().get_stats()


# ============= Autopilot Executor =============

@router.post("/execute/draft")
async def create_and_optionally_execute_draft(
    platform: str = Body(...),
    recipient_id: str = Body(...),
    recipient_name: str = Body(...),
    content: str = Body(...),
    confidence: float = Body(default=0.5),
    context: str = Body(default=""),
):
    """Create a draft (may auto-execute based on confidence and mode)."""
    from services.autopilot_executor_service import get_autopilot_executor_service
    executor = get_autopilot_executor_service()
    draft = executor.create_draft(
        platform=platform,
        recipient_id=recipient_id,
        recipient_name=recipient_name,
        content=content,
        confidence=confidence,
        context=context,
    )
    return {
        "draft_id": draft.draft_id,
        "status": draft.status,
        "platform": draft.platform,
        "confidence": draft.confidence,
    }


@router.post("/execute/send/{draft_id}")
async def execute_draft(draft_id: str):
    """Manually execute (send) a pending draft."""
    from services.autopilot_executor_service import get_autopilot_executor_service
    executor = get_autopilot_executor_service()
    result = executor.execute_draft(draft_id)
    return {
        "success": result.success,
        "draft_id": result.draft_id,
        "status": result.status,
        "message": result.message,
        "error": result.error,
    }


@router.post("/execute/reject/{draft_id}")
async def reject_draft(draft_id: str):
    """Reject a pending draft."""
    from services.autopilot_executor_service import get_autopilot_executor_service
    executor = get_autopilot_executor_service()
    success = executor.reject_draft(draft_id)
    if not success:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"success": True, "draft_id": draft_id, "status": "rejected"}


@router.get("/execute/pending")
async def get_pending_drafts(platform: Optional[str] = None):
    """Get all pending (unexecuted) drafts."""
    from services.autopilot_executor_service import get_autopilot_executor_service
    executor = get_autopilot_executor_service()
    drafts = executor.get_pending_drafts(platform)
    return {
        "pending": [
            {
                "draft_id": d.draft_id,
                "platform": d.platform,
                "recipient_name": d.recipient_name,
                "content": d.content[:200] + ("..." if len(d.content) > 200 else ""),
                "confidence": d.confidence,
                "created_at": d.created_at,
            }
            for d in drafts
        ]
    }


@router.get("/execute/stats")
async def get_executor_stats():
    """Get autopilot executor statistics."""
    from services.autopilot_executor_service import get_autopilot_executor_service
    return get_autopilot_executor_service().get_stats()


# ============= Entity Resolution =============

@router.post("/entities/register")
async def register_entity_identity(
    platform: str = Body(...),
    platform_id: str = Body(...),
    display_name: str = Body(...),
    metadata: Optional[Dict] = Body(default=None),
):
    """Register a new platform identity."""
    from services.entity_resolution_service import get_entity_resolution_service
    er = get_entity_resolution_service()
    entity_id = er.register_identity(platform, platform_id, display_name, metadata)
    entity = er.get_entity(entity_id)
    return {
        "entity_id": entity_id,
        "canonical_name": entity.canonical_name if entity else display_name,
        "total_identities": len(entity.identities) if entity else 1,
    }


@router.post("/entities/link")
async def link_entity_identities(
    key_a: str = Body(..., description="e.g. 'discord:john#1234'"),
    key_b: str = Body(..., description="e.g. 'gmail:john@example.com'"),
):
    """Link two platform identities as the same person."""
    from services.entity_resolution_service import get_entity_resolution_service
    er = get_entity_resolution_service()
    eid = er.link_identities(key_a, key_b)
    if not eid:
        raise HTTPException(status_code=404, detail="One or both identities not found")
    entity = er.get_entity(eid)
    return {
        "entity_id": eid,
        "canonical_name": entity.canonical_name if entity else "Unknown",
        "identities": list(entity.identities.keys()) if entity else [],
    }


@router.get("/entities/search")
async def search_entities(query: str, limit: int = 10):
    """Search entities by name."""
    from services.entity_resolution_service import get_entity_resolution_service
    er = get_entity_resolution_service()
    results = er.search_entities(query, limit)
    return {
        "results": [
            {
                "entity_id": e.entity_id,
                "canonical_name": e.canonical_name,
                "platforms": [i.platform for i in e.identities.values()],
                "tags": e.tags,
            }
            for e in results
        ]
    }


@router.get("/entities/suggestions")
async def get_merge_suggestions():
    """Get suggested entity merges based on name similarity."""
    from services.entity_resolution_service import get_entity_resolution_service
    er = get_entity_resolution_service()
    suggestions = er.suggest_merges()
    return {
        "suggestions": [
            {"entity_a": a, "entity_b": b, "reason": r}
            for a, b, r in suggestions
        ]
    }


@router.get("/entities/stats")
async def get_entity_stats():
    """Get entity resolution statistics."""
    from services.entity_resolution_service import get_entity_resolution_service
    return get_entity_resolution_service().get_stats()


# ============= Background Processing =============

@router.post("/background/trigger/{task_name}")
async def trigger_background_task(task_name: str):
    """Manually trigger a background task."""
    from services.background_processor_service import get_background_processor_service
    processor = get_background_processor_service()
    result = processor.trigger_task(task_name)
    if "error" in result and not result.get("success", True):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/background/digests")
async def get_recent_digests(limit: int = 7):
    """Get recent daily digests."""
    from services.background_processor_service import get_background_processor_service
    processor = get_background_processor_service()
    return {"digests": processor.get_recent_digests(limit)}


@router.get("/background/stats")
async def get_background_stats():
    """Get background processor statistics."""
    from services.background_processor_service import get_background_processor_service
    return get_background_processor_service().get_stats()


# ============= PII Scrubber =============

@router.get("/pii/stats")
async def get_pii_stats():
    """Get PII scrubber statistics."""
    from services.pii_scrubber_service import get_pii_scrubber_service
    return get_pii_scrubber_service().get_stats()


@router.post("/pii/test")
async def test_pii_scrubbing(text: str = Body(..., embed=True)):
    """Test PII scrubbing on a sample text (for debugging)."""
    from services.pii_scrubber_service import get_pii_scrubber_service
    scrubber = get_pii_scrubber_service()
    result = scrubber.scrub_detailed(text)
    return {
        "scrubbed_text": result.scrubbed_text,
        "pii_found": result.pii_found,
        "categories_found": result.categories_found,
        "detection_count": len(result.detections),
    }
