"""
STEP 9 — Adversarial Input Detection
Detects and neutralizes Unicode obfuscation, homoglyph substitutions,
zero-width character steganography, and encoded hidden prompts.
"""

import re
import unicodedata
import base64
from dataclasses import dataclass, field


@dataclass
class AdversarialResult:
    clean_text: str = ""
    detected: bool = False
    techniques: list[str] = field(default_factory=list)


# ── Homoglyph / lookalike Unicode ranges ─────────────────────────────────────
# Characters that look like ASCII but are different Unicode code points.
_HOMOGLYPH_MAP: dict[str, str] = {
    # Cyrillic lookalikes
    "\u0430": "a",  "\u0435": "e",  "\u043e": "o",  "\u0440": "p",
    "\u0441": "c",  "\u0445": "x",  "\u0443": "y",  "\u0456": "i",
    # Greek lookalikes
    "\u03b1": "a",  "\u03b5": "e",  "\u03bf": "o",  "\u03c1": "p",
    "\u03ba": "k",  "\u03bd": "v",  "\u03c5": "u",
    # Math / bold / italic letter variants (common in Unicode obfuscation)
    "\u1d00": "a",  "\u1d07": "e",
    # Fullwidth ASCII
    **{chr(0xFF01 + i): chr(0x21 + i) for i in range(94)},
}

# ── Zero-width / invisible character set ─────────────────────────────────────
_ZERO_WIDTH = {
    "\u200B", "\u200C", "\u200D", "\u200E", "\u200F",
    "\u202A", "\u202B", "\u202C", "\u202D", "\u202E",
    "\uFEFF", "\u00AD", "\u2060",
}

# ── Regex for suspiciously encoded hidden content ────────────────────────────
_RE_BASE64_INSTRUCTION = re.compile(
    r"[A-Za-z0-9+/]{30,}={0,2}",
    re.IGNORECASE
)

# Decode and check if decoded base64 contains prompt injection markers
_INJECTION_MARKER_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+instructions?",
        r"system\s+prompt",
        r"override",
        r"reveal",
        r"jailbreak",
    ]
]


def _decode_base64_safely(s: str) -> str | None:
    """Try to decode a string as base64, return None on failure."""
    try:
        # Pad if necessary
        padded = s + "=" * (-len(s) % 4)
        decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
        return decoded if len(decoded) > 10 else None
    except Exception:
        return None


def _normalize_homoglyphs(text: str) -> tuple[str, bool]:
    """Replace known homoglyph characters with their ASCII equivalents."""
    changed = False
    result = []
    for ch in text:
        mapped = _HOMOGLYPH_MAP.get(ch)
        if mapped:
            result.append(mapped)
            changed = True
        else:
            result.append(ch)
    return "".join(result), changed


def _strip_zero_width(text: str) -> tuple[str, bool]:
    """Remove zero-width / invisible characters from text."""
    result = [ch for ch in text if ch not in _ZERO_WIDTH]
    changed = len(result) < len(text)
    return "".join(result), changed


def _detect_encoded_prompts(text: str) -> tuple[str, bool]:
    """Look for base64 blobs that, when decoded, contain injection patterns."""
    detected = False

    def _check_blob(m: re.Match) -> str:
        nonlocal detected
        blob = m.group(0)
        decoded = _decode_base64_safely(blob)
        if decoded:
            for pat in _INJECTION_MARKER_PATTERNS:
                if pat.search(decoded):
                    detected = True
                    return "[ENCODED_INJECTION_REMOVED]"
        return blob  # keep if not suspicious

    new_text = _RE_BASE64_INSTRUCTION.sub(_check_blob, text)
    return new_text, detected


def detect_and_clean(text: str) -> AdversarialResult:
    """
    Detect and neutralize adversarial input patterns.
    Returns an AdversarialResult with the cleaned text.
    """
    result = AdversarialResult(clean_text=text)

    # 1) Strip zero-width / invisible characters
    text, zw_found = _strip_zero_width(text)
    if zw_found:
        result.detected = True
        result.techniques.append("zero_width_character_steganography")

    # 2) Normalize homoglyphs
    text, hg_found = _normalize_homoglyphs(text)
    if hg_found:
        result.detected = True
        result.techniques.append("homoglyph_substitution")

    # 3) NFC normalization (collapses composed characters used for obfuscation)
    normalized = unicodedata.normalize("NFC", text)
    if normalized != text:
        result.detected = True
        result.techniques.append("unicode_normalization_evasion")
    text = normalized

    # 4) Check for base64-encoded injection payloads
    text, enc_found = _detect_encoded_prompts(text)
    if enc_found:
        result.detected = True
        result.techniques.append("base64_encoded_injection")

    result.clean_text = text
    return result
