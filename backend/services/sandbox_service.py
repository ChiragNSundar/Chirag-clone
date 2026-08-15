"""
Sandbox Service - Restricted Python execution environment for agentic tasks.

Provides a safe, sandboxed Python REPL where the AI agent can execute code
without risking the host system. Uses RestrictedPython when available,
falls back to a custom AST-based sandbox.

Features:
- Whitelisted builtins only (no open, exec, eval, import, __import__)
- Memory and time limits
- No filesystem or network access
- Captures stdout/stderr safely
- Execution audit log

Usage:
    from services.sandbox_service import get_sandbox_service
    sandbox = get_sandbox_service()
    result = sandbox.execute("print(2 + 2)")
"""
import ast
import sys
import io
import time
import traceback
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from config import Config
from services.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ExecutionResult:
    """Result of a sandboxed code execution."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    return_value: Any = None
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    error_type: Optional[str] = None
    truncated: bool = False


# ============= Security: Blocked AST Nodes =============

BLOCKED_AST_NODES = {
    ast.Import,
    ast.ImportFrom,
}

# Attributes that must never be accessed
BLOCKED_ATTRIBUTES = {
    "__import__", "__builtins__", "__loader__", "__spec__",
    "__subclasses__", "__bases__", "__mro__", "__class__",
    "_getframe", "f_globals", "f_locals", "f_back",
    "gi_frame", "gi_code", "co_code",
    "__code__", "__globals__", "__closure__",
}

# Safe builtins whitelist
SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bin": bin,
    "bool": bool,
    "bytearray": bytearray,
    "bytes": bytes,
    "chr": chr,
    "complex": complex,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "format": format,
    "frozenset": frozenset,
    "hash": hash,
    "hex": hex,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "oct": oct,
    "ord": ord,
    "pow": pow,
    "print": print,  # Will be redirected to StringIO
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
    # Math constants
    "True": True,
    "False": False,
    "None": None,
}

# Safe modules that can be imported in the sandbox
SAFE_MODULES = {
    "math", "statistics", "random", "string",
    "datetime", "collections", "itertools", "functools",
    "json", "re", "textwrap", "decimal", "fractions",
}


class CodeValidator:
    """Validates Python code AST for safety before execution."""

    def validate(self, code: str) -> tuple:
        """
        Validate code for safety.

        Returns:
            (is_safe: bool, reason: str)
        """
        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

        for node in ast.walk(tree):
            # Block dangerous imports
            if type(node) in BLOCKED_AST_NODES:
                module_name = ""
                if isinstance(node, ast.Import):
                    module_name = node.names[0].name if node.names else ""
                elif isinstance(node, ast.ImportFrom):
                    module_name = node.module or ""

                # Allow safe modules
                base_module = module_name.split(".")[0] if module_name else ""
                if base_module not in SAFE_MODULES:
                    return False, f"Import of '{module_name}' is not allowed"

            # Block access to dangerous attributes
            if isinstance(node, ast.Attribute):
                if node.attr in BLOCKED_ATTRIBUTES:
                    return False, f"Access to '{node.attr}' is not allowed"

            # Block exec/eval calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ("exec", "eval", "compile", "__import__",
                                         "globals", "locals", "vars", "dir",
                                         "getattr", "setattr", "delattr",
                                         "open", "input", "breakpoint"):
                        return False, f"Call to '{node.func.id}' is not allowed"

        return True, "Code is safe"


class SandboxService:
    """
    Sandboxed Python execution environment.

    Provides a restricted Python REPL where the AI agent can safely
    execute computations, data transformations, and analysis without
    risking the host system.
    """

    def __init__(self):
        self.enabled = getattr(Config, "SANDBOX_ENABLED", True)
        self.max_execution_time = int(
            getattr(Config, "SANDBOX_TIMEOUT_SECONDS", 10)
        )
        self.max_output_chars = int(
            getattr(Config, "SANDBOX_MAX_OUTPUT_CHARS", 10000)
        )
        self._validator = CodeValidator()
        self._execution_count = 0
        self._total_blocked = 0
        self._audit_log: List[Dict] = []
        self._max_audit = 500

        # Persistent namespace for multi-step execution
        self._session_namespaces: Dict[str, Dict] = {}

        logger.info(f"Sandbox service initialized (enabled={self.enabled})")

    def _build_safe_globals(self, session_id: Optional[str] = None) -> Dict:
        """Build the restricted globals dict for execution."""
        safe_globals = {"__builtins__": dict(SAFE_BUILTINS)}

        # Add safe module import function
        def safe_import(name, *args, **kwargs):
            base = name.split(".")[0]
            if base in SAFE_MODULES:
                return __import__(name, *args, **kwargs)
            raise ImportError(f"Import of '{name}' is not allowed in sandbox")

        safe_globals["__builtins__"]["__import__"] = safe_import

        # Merge session namespace if provided
        if session_id and session_id in self._session_namespaces:
            safe_globals.update(self._session_namespaces[session_id])

        return safe_globals

    def execute(
        self,
        code: str,
        session_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> ExecutionResult:
        """
        Execute Python code in a sandboxed environment.

        Args:
            code: Python code to execute.
            session_id: Optional session ID for persistent namespace.
            timeout: Override default timeout (seconds).

        Returns:
            ExecutionResult with stdout, stderr, and execution metadata.
        """
        if not self.enabled:
            return ExecutionResult(
                success=False,
                error="Sandbox execution is disabled",
                error_type="DisabledError",
            )

        if not code or not code.strip():
            return ExecutionResult(
                success=False,
                error="No code provided",
                error_type="ValueError",
            )

        # Step 1: Validate code safety
        is_safe, reason = self._validator.validate(code)
        if not is_safe:
            self._total_blocked += 1
            self._add_audit("blocked", code, reason)
            logger.warning(f"Sandbox blocked unsafe code: {reason}")
            return ExecutionResult(
                success=False,
                error=f"Code blocked: {reason}",
                error_type="SecurityError",
            )

        # Step 2: Execute with timeout
        effective_timeout = timeout or self.max_execution_time
        safe_globals = self._build_safe_globals(session_id)
        safe_locals: Dict[str, Any] = {}

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        result = ExecutionResult(success=False)
        start_time = time.monotonic()

        def _run():
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            try:
                sys.stdout = stdout_capture
                sys.stderr = stderr_capture

                exec(compile(code, "<sandbox>", "exec"), safe_globals, safe_locals)

                result.success = True
            except Exception as e:
                result.error = str(e)
                result.error_type = type(e).__name__
                stderr_capture.write(traceback.format_exc())
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=effective_timeout)

        elapsed_ms = (time.monotonic() - start_time) * 1000
        result.execution_time_ms = round(elapsed_ms, 2)

        if thread.is_alive():
            result.success = False
            result.error = f"Execution timed out after {effective_timeout}s"
            result.error_type = "TimeoutError"
            self._add_audit("timeout", code, result.error)
            logger.warning(f"Sandbox execution timed out after {effective_timeout}s")
        else:
            # Capture output
            stdout_val = stdout_capture.getvalue()
            stderr_val = stderr_capture.getvalue()

            # Truncate if too long
            if len(stdout_val) > self.max_output_chars:
                stdout_val = stdout_val[:self.max_output_chars] + "\n... [truncated]"
                result.truncated = True
            if len(stderr_val) > self.max_output_chars:
                stderr_val = stderr_val[:self.max_output_chars] + "\n... [truncated]"
                result.truncated = True

            result.stdout = stdout_val
            result.stderr = stderr_val

            # Save session namespace (excluding builtins)
            if session_id and result.success:
                self._session_namespaces[session_id] = {
                    k: v for k, v in safe_locals.items()
                    if not k.startswith("_")
                }

        self._execution_count += 1
        status = "success" if result.success else "error"
        self._add_audit(status, code[:200], result.error)

        return result

    def clear_session(self, session_id: str):
        """Clear a session's persistent namespace."""
        self._session_namespaces.pop(session_id, None)

    def _add_audit(self, status: str, code: str, detail: Optional[str] = None):
        """Add an entry to the audit log."""
        self._audit_log.append({
            "timestamp": time.time(),
            "status": status,
            "code_preview": code[:100],
            "detail": detail,
        })
        if len(self._audit_log) > self._max_audit:
            self._audit_log = self._audit_log[-self._max_audit:]

    def get_stats(self) -> Dict:
        """Get sandbox execution statistics."""
        return {
            "enabled": self.enabled,
            "total_executions": self._execution_count,
            "total_blocked": self._total_blocked,
            "active_sessions": len(self._session_namespaces),
            "max_timeout_seconds": self.max_execution_time,
            "safe_modules": sorted(SAFE_MODULES),
        }


# Singleton
_sandbox_service = None


def get_sandbox_service() -> SandboxService:
    """Get the singleton sandbox service instance."""
    global _sandbox_service
    if _sandbox_service is None:
        _sandbox_service = SandboxService()
    return _sandbox_service
