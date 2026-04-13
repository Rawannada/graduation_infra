
"""
STEP 4 — Text Sanitization
Removes/neutralizes scripts, HTML tags, hidden Unicode characters,
encoded instructions, and suspicious URL markers from extracted text.
"""

import re
import unicodedata

# ── Regex patterns ────────────────────────────────────────────────────────────

# Strip HTML / XML tags
_RE_HTML_TAGS = re.compile(r"<[^>]+>", re.IGNORECASE)

# Strip <script>…</script> blocks (including content)
_RE_SCRIPT_BLOCK = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)

# Hidden / zero-width Unicode code points
_HIDDEN_UNICODE_CHARS = [
    "\u200B",  # Zero-width space
    "\u200C",  # Zero-width non-joiner
    "\u200D",  # Zero-width joiner
    "\u200E",  # Left-to-right mark
    "\u200F",  # Right-to-left mark
    "\u202A",  # Left-to-right embedding
    "\u202B",  # Right-to-left embedding
    "\u202C",  # Pop directional formatting
    "\u202D",  # Left-to-right override
    "\u202E",  # Right-to-left override (used in file-name spoofing attacks)
    "\uFEFF",  # BOM / zero-width no-break space
    "\u00AD",  # Soft hyphen
    "\u2060",  # Word joiner
    "\uFFFD",  # Replacement character used in obfuscation
]

# Base64-encoded blobs that are suspiciously long (likely encoded instructions)
_RE_BASE64_BLOB = re.compile(r"(?:[A-Za-z0-9+/]{40,}={0,2})")

# Hex-encoded blobs
_RE_HEX_BLOB = re.compile(r"\b(?:[0-9a-fA-F]{2}[ ]?){16,}\b")

# Suspicious URL schemes embedded in text
_RE_SUSPICIOUS_URL = re.compile(
    r"https?://[^\s\"'<>]+|ftp://[^\s\"'<>]+|data:[^\s;]+;base64,[A-Za-z0-9+/]+=*",
    re.IGNORECASE
)


def sanitize(text: str) -> tuple[str, list[str]]:
    """
    Returns (sanitized_text, list_of_actions_taken).
    """
    actions: list[str] = []
    original_len = len(text)

    # 1) Strip <script> blocks
    cleaned = _RE_SCRIPT_BLOCK.sub("", text)
    if len(cleaned) < len(text):
        actions.append("Removed <script> blocks")
    text = cleaned

    # 2) Strip remaining HTML tags
    cleaned = _RE_HTML_TAGS.sub("", text)
    if len(cleaned) < len(text):
        actions.append("Stripped HTML tags")
    text = cleaned

    # 3) Remove hidden Unicode characters
    before = len(text)
    for ch in _HIDDEN_UNICODE_CHARS:
        text = text.replace(ch, "")
    if len(text) < before:
        actions.append("Removed hidden/zero-width Unicode characters")

    # 4) Normalize Unicode (NFC) to collapse homoglyph substitutions
    text = unicodedata.normalize("NFC", text)

    # 5) Neutralize suspiciously long base64 blobs
    cleaned = _RE_BASE64_BLOB.sub("[BASE64_BLOB_REMOVED]", text)
    if cleaned != text:
        actions.append("Neutralized base64-encoded blobs")
    text = cleaned

    # 6) Neutralize hex blobs
    cleaned = _RE_HEX_BLOB.sub("[HEX_BLOB_REMOVED]", text)
    if cleaned != text:
        actions.append("Neutralized hex-encoded blobs")
    text = cleaned

    # 7) Flag (but preserve, for threat intel) suspicious URLs — mark them
    url_matches = _RE_SUSPICIOUS_URL.findall(text)
    if url_matches:
        actions.append(f"Flagged {len(url_matches)} suspicious URL(s) for threat intel review")

    if len(text) < original_len - 5:
        actions.append(f"Text reduced from {original_len} → {len(text)} chars after sanitization")

    return text, actions


def extract_urls(text: str) -> list[str]:
    """Pull all URLs from text for threat intel processing."""
    return _RE_SUSPICIOUS_URL.findall(text)
