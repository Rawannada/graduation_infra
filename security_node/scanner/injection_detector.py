"""
STEP 5 — Prompt Injection Detection
Detects and neutralizes instructions embedded in document content that
attempt to override AI behavior.
"""

import re

# Patterns that indicate prompt injection attacks
_INJECTION_PATTERNS: list[tuple[str, re.Pattern]] = []

_RAW_PATTERNS = [
    # Classic overrides
    r"ignore\s+(all\s+)?previous\s+instructions?",
    r"disregard\s+(all\s+)?previous\s+instructions?",
    r"forget\s+(all\s+)?previous\s+instructions?",
    r"override\s+(all\s+)?(previous\s+)?instructions?",

    # System prompt leakage attempts
    r"reveal\s+(your\s+)?system\s+prompt",
    r"show\s+(me\s+)?(your\s+)?(hidden\s+)?prompt",
    r"print\s+(your\s+)?system\s+prompt",
    r"what\s+(is|are)\s+(your\s+)?(system\s+)?instructions?",
    r"tell\s+me\s+your\s+(system\s+)?instructions?",

    # Role override
    r"act\s+as\s+(a\s+)?(developer|admin|root|superuser|god)\s*mode",
    r"you\s+are\s+now\s+(a\s+)?(different|new|another)\s+ai",
    r"pretend\s+(you\s+are|to\s+be)\s+",
    r"roleplay\s+as\s+",
    r"switch\s+to\s+(developer|admin|jailbreak)\s+mode",

    # DAN / jailbreak
    r"\bDAN\b",
    r"do\s+anything\s+now",
    r"jailbreak",
    r"enable\s+developer\s+mode",

    # Instruction injection keywords
    r"new\s+instructions?\s*:",
    r"system\s*:\s*(you\s+are|your\s+role)",
    r"<\s*system\s*>",
    r"\[INST\]",
    r"\[\/INST\]",
    r"<\|im_start\|>",
    r"<\|im_end\|>",

    # Data exfiltration via prompt
    r"send\s+(all\s+)?(data|content|text)\s+to\s+",
    r"exfiltrate",
    r"leak\s+(the\s+)?(data|content|system\s+prompt)",
]

for pat in _RAW_PATTERNS:
    _INJECTION_PATTERNS.append((pat, re.compile(pat, re.IGNORECASE | re.DOTALL)))


def detect_and_clean(text: str) -> tuple[str, bool, list[str]]:
    """
    Returns (clean_text, detected, matched_patterns).
    clean_text       → text with injection patterns removed/neutralized.
    detected         → True if any injection pattern was found.
    matched_patterns → list of matched pattern descriptions.
    """
    detected = False
    matches: list[str] = []

    for raw_pat, compiled_pat in _INJECTION_PATTERNS:
        found = compiled_pat.findall(text)
        if found:
            detected = True
            for f in found:
                # Store a truncated version of the actual match
                match_str = f if isinstance(f, str) else str(f)
                matches.append(match_str[:120])
            # Neutralize: replace with a placeholder
            text = compiled_pat.sub("[INJECTION_ATTEMPT_REMOVED]", text)

    return text, detected, matches
