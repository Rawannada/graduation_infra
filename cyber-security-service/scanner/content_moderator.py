"""
STEP 8 — Content Moderation
Detects malware development instructions, illegal activity guides, and hate speech.
"""

import re
from dataclasses import dataclass, field


@dataclass
class ModerationResult:
    blocked: bool = False
    categories: list[str] = field(default_factory=list)
    reason: str = ""


# ── Keyword / regex lists ─────────────────────────────────────────────────────

_MALWARE_PATTERNS = [
    r"shellcode",
    r"reverse\s+shell",
    r"bind\s+shell",
    r"meterpreter",
    r"metasploit",
    r"exploit\s+kit",
    r"ransomware\s+source",
    r"keylogger\s+source",
    r"botnet\s+(setup|install|deploy)",
    r"create\s+(a\s+)?virus",
    r"write\s+(a\s+)?(malware|trojan|worm|ransomware)",
    r"CVE-\d{4}-\d{4,}",          # CVE references in malicious context
    r"0day|zero[\s\-]?day\s+exploit",
    r"heap\s+spray",
    r"rop\s+chain",
    r"return[\s\-]oriented\s+programming",
    r"sql\s+injection\s+(payload|code|exploit)",
    r"xss\s+(payload|attack|script)",
    r"command\s+injection",
    r"lfi\s+exploit|rfi\s+exploit",
    r"privilege\s+escalation\s+(code|exploit|script)",
    r"rootkit\s+(install|deploy|source)",
]

_ILLEGAL_PATTERNS = [
    r"synthesize\s+(methamphetamine|fentanyl|heroin|cocaine|mdma)",
    r"how\s+to\s+make\s+(a\s+)?(bomb|explosive|ied)",
    r"manufacture\s+(illegal\s+)?(firearms|weapons|drugs)",
    r"child\s+(sexual|pornography|abuse\s+material)",
    r"csam",
    r"human\s+trafficking",
    r"contract\s+killing",
    r"hire\s+(a\s+)?hitman",
    r"money\s+laundering\s+(instructions|guide|tutorial)",
]

_HATE_SPEECH_PATTERNS = [
    # High-confidence, explicit slur + context patterns only
    r"(kill|exterminate|eliminate)\s+all\s+(jews|muslims|christians|blacks|whites|hispanics|asians)",
    r"(white|black|jewish|islamic|christian)\s+genocide",
    r"ethnic\s+cleansing\s+(plan|guide|manifesto)",
    r"nazi\s+manifesto",
    r"race\s+war\s+(now|instructions|guide)",
]

def _compile_group(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE | re.DOTALL) for p in patterns]

_COMPILED_MALWARE  = _compile_group(_MALWARE_PATTERNS)
_COMPILED_ILLEGAL  = _compile_group(_ILLEGAL_PATTERNS)
_COMPILED_HATE     = _compile_group(_HATE_SPEECH_PATTERNS)


def moderate(text: str) -> ModerationResult:
    """
    Check text for prohibited content. Returns a ModerationResult.
    """
    result = ModerationResult()
    reasons: list[str] = []

    # Check malware instructions
    for pat in _COMPILED_MALWARE:
        m = pat.search(text)
        if m:
            result.categories.append("malware_instructions")
            reasons.append(f"Malware-related content: '{m.group(0)[:60]}'")
            break  # one hit per category is enough

    # Check illegal activity
    for pat in _COMPILED_ILLEGAL:
        m = pat.search(text)
        if m:
            result.categories.append("illegal_activity")
            reasons.append(f"Illegal activity instructions: '{m.group(0)[:60]}'")
            break

    # Check hate speech
    for pat in _COMPILED_HATE:
        m = pat.search(text)
        if m:
            result.categories.append("hate_speech")
            reasons.append(f"Hate speech detected: '{m.group(0)[:60]}'")
            break

    if result.categories:
        result.blocked = True
        result.reason = " | ".join(reasons)

    return result
