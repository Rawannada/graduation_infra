"""
STEP 10 — Security Scoring
Aggregates all pipeline flags into a weighted 0–100 security score.
"""

from dataclasses import dataclass, field


@dataclass
class SecurityScore:
    score: int = 100          # 100 = perfectly clean, 0 = maximally dangerous
    malware_risk: str = "Clean"
    prompt_injection_risk: str = "None"
    sensitive_data: str = "None"
    threat_indicators: str = "None"
    adversarial_input: str = "None"
    content_moderation: str = "Passed"
    # Detailed breakdown
    penalties: dict = field(default_factory=dict)


# Penalty weights
_WEIGHTS = {
    "javascript":           15,
    "embedded_files":       30,
    "open_or_launch":       15,
    "high_risk_pdf":        20,   # gate risk_level == 3
    "medium_risk_pdf":       8,   # gate risk_level == 2
    "prompt_injection":     20,
    "dlp_findings":          5,   # per category capped at 15
    "threat_intel":         20,
    "content_blocked":      35,   # instant near-block
    "adversarial_input":    10,
    "macros_found":         20,
    "objstm":                5,
    "many_links":           10,
}


def compute(
    *,
    # Step 2 — content validation
    javascript_found: bool = False,
    embedded_files: int = 0,
    pdf_risk_level: int = 1,         # 1=Low, 2=Medium, 3=High
    pdf_profile: str = "benign_like",
    triggers: list | None = None,
    macros_found: bool = False,
    # Step 5 — prompt injection
    injection_detected: bool = False,
    # Step 6 — DLP
    dlp_findings: dict | None = None,
    # Step 7 — threat intel
    threat_alert: bool = False,
    # Step 8 — content moderation
    content_blocked: bool = False,
    # Step 9 — adversarial
    adversarial_detected: bool = False,
) -> SecurityScore:
    """
    Compute the final security score from all pipeline signals.
    Returns a SecurityScore dataclass.
    """
    triggers = triggers or []
    dlp_findings = dlp_findings or {}
    result = SecurityScore()
    penalties: dict[str, int] = {}
    total_penalty = 0

    def _add_penalty(key: str, amount: int) -> None:
        nonlocal total_penalty
        penalties[key] = amount
        total_penalty += amount

    # JavaScript in PDF
    if javascript_found:
        _add_penalty("javascript", _WEIGHTS["javascript"])

    # Embedded files
    if embedded_files > 0:
        _add_penalty("embedded_files", _WEIGHTS["embedded_files"])

    # OpenAction / Launch triggers
    has_open_launch = any(
        t.get("type") in ["/OpenAction", "/Launch"] for t in triggers
    )
    if has_open_launch:
        _add_penalty("open_or_launch", _WEIGHTS["open_or_launch"])

    # ObjStm present
    has_objstm = any(t.get("type") == "ObjStmPresent" for t in triggers)
    if has_objstm:
        _add_penalty("objstm", _WEIGHTS["objstm"])

    # Many external links
    has_many_links = any(t.get("type") == "ManyExternalLinks" for t in triggers)
    if has_many_links:
        _add_penalty("many_links", _WEIGHTS["many_links"])

    # PDF overall risk level
    if pdf_risk_level == 3:
        _add_penalty("high_risk_pdf", _WEIGHTS["high_risk_pdf"])
    elif pdf_risk_level == 2:
        _add_penalty("medium_risk_pdf", _WEIGHTS["medium_risk_pdf"])

    # Profiles penalty
    if pdf_profile == "phishing_like":
        _add_penalty("phishing_profile", 15)
    elif pdf_profile == "dropper_like":
        _add_penalty("dropper_profile", 15)

    # DOCX macros
    if macros_found:
        _add_penalty("macros_found", _WEIGHTS["macros_found"])

    # Prompt injection
    if injection_detected:
        _add_penalty("prompt_injection", _WEIGHTS["prompt_injection"])

    # DLP findings — 5 pts per category, capped at 15
    if dlp_findings:
        dlp_penalty = min(len(dlp_findings) * _WEIGHTS["dlp_findings"], 15)
        _add_penalty("dlp_findings", dlp_penalty)

    # Threat intel alert
    if threat_alert:
        _add_penalty("threat_intel", _WEIGHTS["threat_intel"])

    # Content moderation block
    if content_blocked:
        _add_penalty("content_blocked", _WEIGHTS["content_blocked"])

    # Adversarial input
    if adversarial_detected:
        _add_penalty("adversarial_input", _WEIGHTS["adversarial_input"])

    result.penalties = penalties
    result.score = max(0, 100 - total_penalty)

    # ── Human-readable labels ─────────────────────────────────────────────────

    if content_blocked:
        result.malware_risk = "Rejected"
    elif pdf_risk_level == 3 or macros_found or javascript_found:
        result.malware_risk = "High"
    elif pdf_risk_level == 2 or embedded_files > 0:
        result.malware_risk = "High"
    else:
        result.malware_risk = "Clean"

    if injection_detected:
        result.prompt_injection_risk = "DETECTED"
    else:
        result.prompt_injection_risk = "None"

    if dlp_findings:
        cats = ", ".join(dlp_findings.keys())
        result.sensitive_data = f"Detected ({cats})"
    else:
        result.sensitive_data = "None"

    result.threat_indicators = "ALERT" if threat_alert else "None"
    result.adversarial_input = "Detected" if adversarial_detected else "None"
    result.content_moderation = "BLOCKED" if content_blocked else "Passed"

    return result