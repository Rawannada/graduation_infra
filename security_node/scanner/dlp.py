"""
STEP 6 — Sensitive Data Detection (DLP)
Detects and redacts PII and sensitive credentials from document text.
"""

import re
from dataclasses import dataclass, field


@dataclass
class DLPResult:
    redacted_text: str
    findings: dict = field(default_factory=dict)  # category → count
    total_redacted: int = 0


# ── Regex patterns for sensitive data ────────────────────────────────────────

_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Email addresses
    ("email", re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
        re.IGNORECASE
    )),

    # Phone numbers (E.164, US 10-digit, International)
    ("phone_number", re.compile(
        r"(?:\+?\d{1,3}[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}",
    )),

    # Credit card numbers (Visa, MC, Amex, Discover — with optional separators)
    ("credit_card", re.compile(
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|"
        r"6(?:011|5[0-9]{2})[0-9]{12}|(?:\d{4}[\s\-]){3}\d{4})\b"
    )),

    # US Social Security Numbers
    ("ssn", re.compile(
        r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"
    )),

    # API keys / tokens (common prefixes)
    ("api_key", re.compile(
        r"(?:sk-|pk-|Bearer\s+|ghp_|glpat-|xoxb-|xoxp-|AKIA)[A-Za-z0-9\-_]{16,}",
        re.IGNORECASE
    )),

    # Generic long secrets / tokens (hex or base62, ≥32 chars, likely a token)
    ("generic_token", re.compile(
        r"\b[A-Za-z0-9]{32,64}\b"
    )),

    # Password-like patterns (explicitly labeled)
    ("password", re.compile(
        r"(?:password|passwd|pwd|secret|token)\s*[:=]\s*\S+",
        re.IGNORECASE
    )),

    # IPv4 addresses with port (potentially sensitive infra data)
    ("ip_address_with_port", re.compile(
        r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b"
    )),
]


def _luhn_check(number: str) -> bool:
    """Validate a credit card number with the Luhn algorithm."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def scan_and_redact(text: str) -> DLPResult:
    """
    Scans text for sensitive data, redacts all matches, and returns a DLPResult.
    """
    findings: dict[str, int] = {}
    total = 0

    for category, pattern in _PATTERNS:
        matches = pattern.findall(text)
        if not matches:
            continue

        # Extra validation for credit cards
        if category == "credit_card":
            valid_matches = []
            for m in matches:
                if _luhn_check(m):
                    valid_matches.append(m)
            matches = valid_matches

        if matches:
            count = len(matches)
            findings[category] = findings.get(category, 0) + count
            total += count
            text = pattern.sub("[REDACTED]", text)

    return DLPResult(
        redacted_text=text,
        findings=findings,
        total_redacted=total,
    )
