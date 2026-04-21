"""
PII Scrubber Service - Detects and redacts Personally Identifiable Information.

Scrubs sensitive data (emails, phone numbers, SSNs, credit cards, API keys,
passwords, IP addresses) from text BEFORE it is sent to cloud LLM providers.
This ensures private data never leaves the user's machine.

Usage:
    from services.pii_scrubber_service import get_pii_scrubber_service
    scrubber = get_pii_scrubber_service()
    clean_text = scrubber.scrub(text)
"""
import re
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from config import Config
from services.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PIIMatch:
    """Represents a single PII detection."""
    category: str          # e.g. "email", "ssn", "credit_card"
    original: str          # The matched text
    redacted: str          # The replacement text
    start: int             # Start position in original text
    end: int               # End position in original text
    confidence: float      # 0.0 - 1.0


@dataclass
class ScrubResult:
    """Result of a PII scrubbing operation."""
    original_text: str
    scrubbed_text: str
    detections: List[PIIMatch] = field(default_factory=list)
    pii_found: bool = False
    categories_found: List[str] = field(default_factory=list)


# ============= PII Pattern Definitions =============

PII_PATTERNS: Dict[str, Dict] = {
    "email": {
        "pattern": r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,7}\b',
        "replacement": "[EMAIL_REDACTED]",
        "confidence": 0.95,
        "description": "Email addresses",
    },
    "phone_us": {
        "pattern": r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
        "replacement": "[PHONE_REDACTED]",
        "confidence": 0.85,
        "description": "US phone numbers",
    },
    "phone_intl": {
        "pattern": r'\+\d{1,3}[-.\s]?\d{4,14}(?:\s*(?:x|ext\.?)\s*\d+)?\b',
        "replacement": "[PHONE_REDACTED]",
        "confidence": 0.80,
        "description": "International phone numbers",
    },
    "ssn": {
        "pattern": r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b',
        "replacement": "[SSN_REDACTED]",
        "confidence": 0.90,
        "description": "US Social Security Numbers",
    },
    "credit_card": {
        "pattern": r'\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))'
                   r'[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{1,4}\b',
        "replacement": "[CREDIT_CARD_REDACTED]",
        "confidence": 0.92,
        "description": "Credit/debit card numbers",
    },
    "api_key_generic": {
        "pattern": r'\b(?:sk|pk|api|key|token|secret|bearer)[-_]'
                   r'[A-Za-z0-9\-_]{16,64}\b',
        "replacement": "[API_KEY_REDACTED]",
        "confidence": 0.88,
        "description": "API keys and tokens",
    },
    "api_key_openai": {
        "pattern": r'\bsk-[A-Za-z0-9]{32,}\b',
        "replacement": "[OPENAI_KEY_REDACTED]",
        "confidence": 0.95,
        "description": "OpenAI API keys",
    },
    "api_key_aws": {
        "pattern": r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
        "replacement": "[AWS_KEY_REDACTED]",
        "confidence": 0.95,
        "description": "AWS access key IDs",
    },
    "password_in_url": {
        "pattern": r'://[^:]+:([^@]+)@',
        "replacement": "://[USER]:[PASSWORD_REDACTED]@",
        "confidence": 0.90,
        "description": "Passwords embedded in URLs",
    },
    "password_assignment": {
        "pattern": r'(?i)(?:password|passwd|pwd)\s*[=:]\s*["\']?([^\s"\']+)',
        "replacement": "password=[PASSWORD_REDACTED]",
        "confidence": 0.85,
        "description": "Password assignments in config/code",
    },
    "ipv4": {
        "pattern": r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}'
                   r'(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b',
        "replacement": "[IP_REDACTED]",
        "confidence": 0.75,
        "description": "IPv4 addresses",
    },
    "private_key_header": {
        "pattern": r'-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----',
        "replacement": "[PRIVATE_KEY_REDACTED]",
        "confidence": 0.99,
        "description": "PEM private key headers",
    },
    "jwt_token": {
        "pattern": r'\beyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\b',
        "replacement": "[JWT_REDACTED]",
        "confidence": 0.95,
        "description": "JSON Web Tokens",
    },
}

# IPs that should NOT be redacted (localhost, common LAN)
IP_WHITELIST = {
    "127.0.0.1", "0.0.0.0", "localhost",
    "192.168.1.1", "10.0.0.1", "172.16.0.1",
}


class PIIScrubberService:
    """
    Service for detecting and redacting PII from text before sending to cloud LLMs.

    Features:
    - Regex-based detection for 13+ PII categories
    - Configurable scrubbing levels (off, moderate, strict)
    - Whitelist support for known-safe values (e.g. localhost IPs)
    - Audit log of scrubbed items for transparency
    - Zero external dependencies (pure Python regex)
    """

    SCRUB_LEVELS = {
        "off": [],
        "moderate": [
            "email", "ssn", "credit_card", "api_key_generic",
            "api_key_openai", "api_key_aws", "password_in_url",
            "password_assignment", "private_key_header", "jwt_token",
        ],
        "strict": list(PII_PATTERNS.keys()),  # All categories
    }

    def __init__(self):
        self.scrub_level = os.getenv("PII_SCRUB_LEVEL", "moderate")
        self.enabled = os.getenv("PII_SCRUB_ENABLED", "true").lower() == "true"
        self._compiled_patterns: Dict[str, re.Pattern] = {}
        self._whitelist: set = set(IP_WHITELIST)
        self._audit_log: List[Dict] = []
        self._max_audit_entries = 1000

        # Compile all regex patterns at init time for performance
        self._compile_patterns()

        if self.enabled:
            logger.info(
                "PII scrubber initialized",
                level=self.scrub_level,
                categories=len(self._get_active_categories()),
            )
        else:
            logger.info("PII scrubber is disabled")

    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        for category, config in PII_PATTERNS.items():
            try:
                self._compiled_patterns[category] = re.compile(
                    config["pattern"], re.IGNORECASE
                )
            except re.error as e:
                logger.error(f"Failed to compile PII pattern '{category}': {e}")

    def _get_active_categories(self) -> List[str]:
        """Get the list of active PII categories based on scrub level."""
        return self.SCRUB_LEVELS.get(self.scrub_level, self.SCRUB_LEVELS["moderate"])

    def detect(self, text: str) -> List[PIIMatch]:
        """
        Detect PII in text without redacting it.

        Args:
            text: The input text to scan.

        Returns:
            List of PIIMatch objects for each detection.
        """
        if not self.enabled or not text:
            return []

        detections: List[PIIMatch] = []
        active_categories = self._get_active_categories()

        for category in active_categories:
            if category not in self._compiled_patterns:
                continue

            pattern = self._compiled_patterns[category]
            config = PII_PATTERNS[category]

            for match in pattern.finditer(text):
                matched_text = match.group(0)

                # Check whitelist
                if matched_text in self._whitelist:
                    continue

                # Skip localhost-like IPs for the IP category
                if category == "ipv4" and matched_text in IP_WHITELIST:
                    continue

                detections.append(PIIMatch(
                    category=category,
                    original=matched_text,
                    redacted=config["replacement"],
                    start=match.start(),
                    end=match.end(),
                    confidence=config["confidence"],
                ))

        return detections

    def scrub(self, text: str) -> str:
        """
        Detect and redact all PII from text.

        This is the primary method to call before sending text to a cloud LLM.

        Args:
            text: The input text to scrub.

        Returns:
            The scrubbed text with PII replaced by redaction markers.
        """
        result = self.scrub_detailed(text)
        return result.scrubbed_text

    def scrub_detailed(self, text: str) -> ScrubResult:
        """
        Detect and redact PII, returning detailed results including what was found.

        Args:
            text: The input text to scrub.

        Returns:
            ScrubResult with scrubbed text and detection details.
        """
        if not self.enabled or not text:
            return ScrubResult(original_text=text, scrubbed_text=text)

        detections = self.detect(text)

        if not detections:
            return ScrubResult(original_text=text, scrubbed_text=text)

        # Sort detections by position (reverse) so replacements don't shift indices
        detections.sort(key=lambda d: d.start, reverse=True)

        scrubbed = text
        for detection in detections:
            scrubbed = (
                scrubbed[:detection.start]
                + detection.redacted
                + scrubbed[detection.end:]
            )

        # Deduplicate category list
        categories_found = list(set(d.category for d in detections))

        # Audit log (keep bounded)
        self._add_audit_entry(detections)

        logger.info(
            "PII scrubbed from text",
            detections_count=len(detections),
            categories=categories_found,
        )

        return ScrubResult(
            original_text=text,
            scrubbed_text=scrubbed,
            detections=detections,
            pii_found=True,
            categories_found=categories_found,
        )

    def scrub_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Scrub PII from a list of LLM chat messages.

        Args:
            messages: List of {"role": "...", "content": "..."} dicts.

        Returns:
            New list with scrubbed content.
        """
        if not self.enabled:
            return messages

        scrubbed_messages = []
        for msg in messages:
            scrubbed_msg = dict(msg)
            if "content" in scrubbed_msg and scrubbed_msg["content"]:
                scrubbed_msg["content"] = self.scrub(scrubbed_msg["content"])
            scrubbed_messages.append(scrubbed_msg)
        return scrubbed_messages

    def add_to_whitelist(self, value: str):
        """Add a value to the whitelist (will not be redacted)."""
        self._whitelist.add(value)

    def remove_from_whitelist(self, value: str):
        """Remove a value from the whitelist."""
        self._whitelist.discard(value)

    def _add_audit_entry(self, detections: List[PIIMatch]):
        """Add an entry to the audit log."""
        import time
        entry = {
            "timestamp": time.time(),
            "count": len(detections),
            "categories": [d.category for d in detections],
        }
        self._audit_log.append(entry)

        # Trim audit log if too large
        if len(self._audit_log) > self._max_audit_entries:
            self._audit_log = self._audit_log[-self._max_audit_entries:]

    def get_stats(self) -> Dict:
        """Get PII scrubbing statistics."""
        total_scrubs = len(self._audit_log)
        total_detections = sum(e["count"] for e in self._audit_log)

        category_counts: Dict[str, int] = {}
        for entry in self._audit_log:
            for cat in entry["categories"]:
                category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "enabled": self.enabled,
            "scrub_level": self.scrub_level,
            "total_scrubs": total_scrubs,
            "total_detections": total_detections,
            "category_counts": category_counts,
            "active_categories": self._get_active_categories(),
            "whitelist_size": len(self._whitelist),
        }


# Singleton
_pii_scrubber_service = None


def get_pii_scrubber_service() -> PIIScrubberService:
    """Get the singleton PII scrubber service instance."""
    global _pii_scrubber_service
    if _pii_scrubber_service is None:
        _pii_scrubber_service = PIIScrubberService()
    return _pii_scrubber_service
