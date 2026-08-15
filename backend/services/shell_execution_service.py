"""
Shell Execution Service - Safe, sandboxed OS command execution.

Provides a controlled interface for the AI agent to run shell commands
on the host system with strict security guardrails:
- Command whitelist (only pre-approved commands)
- Argument sanitization (no pipes, redirects, semicolons)
- Working directory restrictions
- Timeout enforcement
- Output capture and size limits
- Full audit logging

Usage:
    from services.shell_execution_service import get_shell_execution_service
    shell = get_shell_execution_service()
    result = shell.execute("ls", ["-la", "/home/user/documents"])
"""
import os
import re
import time
import subprocess
import shlex
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from config import Config
from services.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ShellResult:
    """Result of a shell command execution."""
    success: bool
    command: str
    args: List[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    truncated: bool = False
    approved: bool = False


# ============= Security Definitions =============

# Commands that are ALWAYS allowed (read-only, safe)
WHITELISTED_COMMANDS: Set[str] = {
    # File listing & info
    "ls", "dir", "find", "tree", "wc", "file", "stat", "du", "df",
    # Text processing (read-only)
    "cat", "head", "tail", "grep", "awk", "sed", "sort", "uniq",
    "cut", "tr", "diff", "echo", "printf",
    # System info
    "date", "whoami", "hostname", "uname", "uptime", "which", "where",
    "env", "printenv",
    # Python/Node
    "python", "python3", "node", "npm", "pip",
    # Git (read-only)
    "git",
    # Network diagnostics
    "ping", "curl", "wget",
    # Windows equivalents
    "type", "more", "findstr", "systeminfo", "tasklist",
    "Get-ChildItem", "Get-Content", "Get-Process", "Get-Date",
}

# Commands that are NEVER allowed (destructive, dangerous)
BLACKLISTED_COMMANDS: Set[str] = {
    "rm", "rmdir", "del", "format", "mkfs",
    "dd", "fdisk", "parted",
    "shutdown", "reboot", "halt", "poweroff",
    "kill", "killall", "pkill", "taskkill",
    "chmod", "chown", "chgrp",
    "passwd", "useradd", "userdel", "usermod",
    "su", "sudo", "runas",
    "iptables", "ufw", "firewall-cmd",
    "reg", "regedit",  # Windows registry
    "net",  # Windows network commands
}

# Shell metacharacters that indicate injection attempts
DANGEROUS_PATTERNS = [
    r'[;&|`$]',           # Command chaining, backticks, variable expansion
    r'>\s*/',             # Redirect to root paths
    r'>>\s*/',            # Append redirect to root paths
    r'\$\(',             # Command substitution
    r'<\(',              # Process substitution
    r'\.\.',             # Directory traversal
]

# Git subcommands that are safe (read-only)
SAFE_GIT_SUBCOMMANDS: Set[str] = {
    "status", "log", "diff", "branch", "tag", "show",
    "remote", "stash", "config", "ls-files", "rev-parse",
    "describe", "shortlog", "blame",
}

# Git subcommands that REQUIRE approval
APPROVAL_GIT_SUBCOMMANDS: Set[str] = {
    "add", "commit", "push", "pull", "merge", "rebase",
    "checkout", "switch", "reset", "clean", "fetch",
}


class ShellExecutionService:
    """
    Safe shell execution service with command whitelisting and sandboxing.

    Security model:
    1. Command must be in the whitelist (or requires explicit approval)
    2. Arguments are sanitized for shell injection
    3. Working directory is restricted to project root
    4. Execution has a timeout
    5. Output is captured and size-limited
    6. All executions are audit-logged
    """

    def __init__(self):
        self.enabled = os.getenv("SHELL_EXEC_ENABLED", "true").lower() == "true"
        self.timeout = int(os.getenv("SHELL_EXEC_TIMEOUT", "30"))
        self.max_output_chars = int(os.getenv("SHELL_EXEC_MAX_OUTPUT", "50000"))
        self.require_approval_for_writes = os.getenv(
            "SHELL_EXEC_REQUIRE_APPROVAL", "true"
        ).lower() == "true"

        # Restrict working directory to project root
        self.project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        self.allowed_cwd_roots: List[str] = [self.project_root]

        self._execution_count = 0
        self._blocked_count = 0
        self._audit_log: List[Dict] = []
        self._max_audit = 500
        self._pending_approvals: Dict[str, Dict] = {}

        logger.info(
            "Shell execution service initialized",
            enabled=self.enabled,
            project_root=self.project_root,
        )

    def _validate_command(self, command: str, args: List[str]) -> tuple:
        """
        Validate a command for safety.

        Returns:
            (is_allowed: bool, needs_approval: bool, reason: str)
        """
        cmd_lower = command.lower().strip()
        cmd_base = os.path.basename(cmd_lower)

        # Check blacklist first
        if cmd_base in BLACKLISTED_COMMANDS:
            return False, False, f"Command '{command}' is blacklisted (dangerous)"

        # Check for shell injection in args
        full_args_str = " ".join(args)
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, full_args_str):
                return False, False, f"Arguments contain dangerous pattern: {pattern}"

        # Special handling for git
        if cmd_base == "git" and args:
            subcommand = args[0].lower()
            if subcommand in SAFE_GIT_SUBCOMMANDS:
                return True, False, "Safe git subcommand"
            elif subcommand in APPROVAL_GIT_SUBCOMMANDS:
                return True, True, f"Git '{subcommand}' requires approval"
            else:
                return False, False, f"Git subcommand '{subcommand}' is not recognized"

        # Special handling for python/pip (restrict to safe operations)
        if cmd_base in ("python", "python3"):
            # Allow --version, -c with safe code, running scripts in project
            if args and args[0] == "--version":
                return True, False, "Safe python --version"
            return True, True, "Python execution requires approval"

        if cmd_base == "pip":
            if args and args[0] in ("list", "show", "freeze", "--version"):
                return True, False, "Safe pip info command"
            return True, True, "Pip install/uninstall requires approval"

        # Check whitelist
        if cmd_base in WHITELISTED_COMMANDS:
            return True, False, f"Command '{command}' is whitelisted"

        # Unknown command — block
        return False, False, f"Command '{command}' is not in the allowed list"

    def _validate_cwd(self, cwd: Optional[str]) -> tuple:
        """Validate the working directory is within allowed roots."""
        if cwd is None:
            return True, self.project_root

        abs_cwd = os.path.abspath(cwd)
        for root in self.allowed_cwd_roots:
            if abs_cwd.startswith(root):
                return True, abs_cwd

        return False, None

    def execute(
        self,
        command: str,
        args: Optional[List[str]] = None,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        approval_token: Optional[str] = None,
    ) -> ShellResult:
        """
        Execute a shell command safely.

        Args:
            command: The command to execute (e.g. "ls", "git").
            args: List of arguments.
            cwd: Working directory (must be within project root).
            timeout: Override default timeout.
            approval_token: Token for pre-approved write commands.

        Returns:
            ShellResult with stdout, stderr, and execution metadata.
        """
        if not self.enabled:
            return ShellResult(
                success=False,
                command=command,
                error="Shell execution is disabled",
            )

        args = args or []
        effective_timeout = timeout or self.timeout

        # Validate working directory
        cwd_valid, resolved_cwd = self._validate_cwd(cwd)
        if not cwd_valid:
            self._blocked_count += 1
            return ShellResult(
                success=False,
                command=command,
                args=args,
                error=f"Working directory '{cwd}' is outside allowed roots",
            )

        # Validate command
        is_allowed, needs_approval, reason = self._validate_command(command, args)

        if not is_allowed:
            self._blocked_count += 1
            self._add_audit("blocked", command, args, reason)
            logger.warning("Shell command blocked", command=command, reason=reason)
            return ShellResult(
                success=False,
                command=command,
                args=args,
                error=reason,
            )

        if needs_approval and self.require_approval_for_writes:
            if not approval_token or approval_token not in self._pending_approvals:
                # Create an approval request
                import uuid
                token = str(uuid.uuid4())[:8]
                self._pending_approvals[token] = {
                    "command": command,
                    "args": args,
                    "cwd": resolved_cwd,
                    "reason": reason,
                    "created_at": time.time(),
                }
                self._add_audit("pending_approval", command, args, reason)
                return ShellResult(
                    success=False,
                    command=command,
                    args=args,
                    error=f"This command requires approval. Token: {token}. "
                          f"Reason: {reason}",
                    approved=False,
                )
            else:
                # Consume the approval token
                del self._pending_approvals[approval_token]

        # Execute the command
        start_time = time.monotonic()
        try:
            cmd_list = [command] + args
            process = subprocess.run(
                cmd_list,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                cwd=resolved_cwd,
                env=self._get_safe_env(),
            )

            elapsed_ms = (time.monotonic() - start_time) * 1000

            stdout = process.stdout or ""
            stderr = process.stderr or ""
            truncated = False

            if len(stdout) > self.max_output_chars:
                stdout = stdout[:self.max_output_chars] + "\n... [truncated]"
                truncated = True
            if len(stderr) > self.max_output_chars:
                stderr = stderr[:self.max_output_chars] + "\n... [truncated]"
                truncated = True

            result = ShellResult(
                success=process.returncode == 0,
                command=command,
                args=args,
                stdout=stdout,
                stderr=stderr,
                exit_code=process.returncode,
                execution_time_ms=round(elapsed_ms, 2),
                truncated=truncated,
                approved=True,
            )

            self._execution_count += 1
            self._add_audit("executed", command, args, f"exit={process.returncode}")
            return result

        except subprocess.TimeoutExpired:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            self._add_audit("timeout", command, args, f"timeout={effective_timeout}s")
            return ShellResult(
                success=False,
                command=command,
                args=args,
                execution_time_ms=round(elapsed_ms, 2),
                error=f"Command timed out after {effective_timeout}s",
            )
        except FileNotFoundError:
            return ShellResult(
                success=False,
                command=command,
                args=args,
                error=f"Command '{command}' not found",
            )
        except Exception as e:
            logger.error("Shell execution error", command=command, error=str(e))
            return ShellResult(
                success=False,
                command=command,
                args=args,
                error=str(e),
            )

    def _get_safe_env(self) -> Dict[str, str]:
        """Get a sanitized environment dict (strip secrets)."""
        safe_env = dict(os.environ)
        # Remove sensitive env vars from subprocess environment
        sensitive_keys = [
            "JWT_SECRET",
            "ELEVENLABS_API_KEY", "DISCORD_BOT_TOKEN",
            "TELEGRAM_BOT_TOKEN", "TWITTER_CLIENT_SECRET",
            "GOOGLE_CLIENT_SECRET", "GMAIL_CLIENT_SECRET",
            "WHATSAPP_ACCESS_TOKEN", "WANDB_API_KEY",
        ]
        for key in sensitive_keys:
            safe_env.pop(key, None)
        return safe_env

    def approve(self, token: str) -> Optional[ShellResult]:
        """Approve a pending command by its token and execute it."""
        if token not in self._pending_approvals:
            return None

        pending = self._pending_approvals[token]
        return self.execute(
            command=pending["command"],
            args=pending["args"],
            cwd=pending["cwd"],
            approval_token=token,
        )

    def get_pending_approvals(self) -> List[Dict]:
        """Get list of commands waiting for approval."""
        # Clean up expired approvals (older than 10 minutes)
        cutoff = time.time() - 600
        self._pending_approvals = {
            k: v for k, v in self._pending_approvals.items()
            if v["created_at"] > cutoff
        }
        return [
            {"token": k, **v} for k, v in self._pending_approvals.items()
        ]

    def _add_audit(self, status: str, command: str, args: List[str],
                   detail: Optional[str] = None):
        """Add an entry to the audit log."""
        self._audit_log.append({
            "timestamp": time.time(),
            "status": status,
            "command": command,
            "args": args[:5],  # Limit stored args
            "detail": detail,
        })
        if len(self._audit_log) > self._max_audit:
            self._audit_log = self._audit_log[-self._max_audit:]

    def get_stats(self) -> Dict:
        """Get shell execution statistics."""
        return {
            "enabled": self.enabled,
            "total_executions": self._execution_count,
            "total_blocked": self._blocked_count,
            "pending_approvals": len(self._pending_approvals),
            "project_root": self.project_root,
            "timeout_seconds": self.timeout,
            "whitelisted_commands": len(WHITELISTED_COMMANDS),
        }


# Singleton
_shell_execution_service = None


def get_shell_execution_service() -> ShellExecutionService:
    """Get the singleton shell execution service instance."""
    global _shell_execution_service
    if _shell_execution_service is None:
        _shell_execution_service = ShellExecutionService()
    return _shell_execution_service
