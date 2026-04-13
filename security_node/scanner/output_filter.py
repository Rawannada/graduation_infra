"""
STEP 12 — Output Filtering
Scans AI-generated output for accidental leakage of system internals,
API keys, or hidden instructions before returning to the caller.
"""

import re

# Patterns to detect in outgoing responses
_LEAK_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("system_prompt_header", re.compile(r"(system\s+prompt\s*:|<system>)", re.IGNORECASE)),
    ("api_key_prefix",       re.compile(r"(?:sk-|pk-|Bearer\s+|ghp_|glpat-|AKIA)[A-Za-z0-9\-_]{16,}")),
    ("internal_variable",    re.compile(r"\b__(class|dict|globals|builtins|import|subclasses)__\b")),
    ("injection_remnant",    re.compile(r"\[INST\]|\[\/INST\]|<\|im_start\|>|<\|im_end\|>", re.IGNORECASE)),
    ("hidden_instruction",   re.compile(r"ignore\s+previous\s+instructions?", re.IGNORECASE)),
]


def filter_output(text: str) -> tuple[str, list[str]]:
    """
    Scans `text` for leakage patterns and removes/redacts them.
    Returns (safe_text, list_of_removals).
    """
    removals: list[str] = []

    for label, pattern in _LEAK_PATTERNS:
        found = pattern.findall(text)
        if found:
            removals.append(f"Removed '{label}' pattern ({len(found)} occurrence(s))")
            text = pattern.sub("[FILTERED]", text)

    return text, removals