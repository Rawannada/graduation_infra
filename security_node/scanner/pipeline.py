"""
scanner/pipeline.py — Main 14-Step Security Pipeline Orchestrator
Runs all security checks in order and returns a unified PipelineResult.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import file_validator
import content_validator
import text_extractor
import sanitizer
import injection_detector
import dlp
import threat_intel
import content_moderator
import adversarial_detector
import scorer
import output_filter


@dataclass
class PipelineResult:
    # Identity
    file_path: str = ""
    file_type: str = ""
    processed_at: str = ""

    # Step results
    step1_ok: bool = False
    step1_reason: str = ""

    step2_ok: bool = False
    step2_reason: str = ""
    step2_gate_report: dict = field(default_factory=dict)

    step3_text: str = ""
    step3_error: str | None = None

    step4_actions: list[str] = field(default_factory=list)

    step5_injection_detected: bool = False
    step5_matches: list[str] = field(default_factory=list)

    step6_dlp_findings: dict = field(default_factory=dict)
    step6_total_redacted: int = 0

    step7_threat_alert: bool = False
    step7_indicators: list[str] = field(default_factory=list)
    step7_urls_found: list[str] = field(default_factory=list)

    step8_content_blocked: bool = False
    step8_reason: str = ""

    step9_adversarial_detected: bool = False
    step9_techniques: list[str] = field(default_factory=list)

    security_score: scorer.SecurityScore = field(default_factory=scorer.SecurityScore)

    # Final decision
    status: str = "PROCESSING"   # FILE_REJECTED | PROCESSING_COMPLETE
    rejection_reason: str = ""

    # Clean analysis-ready text
    clean_text: str = ""

    # Output filter removals
    output_filter_removals: list[str] = field(default_factory=list)

    # Summary
    summary: str = ""
    summary_confidence: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["security_score"] = asdict(self.security_score)
        return d


def _reject(result: PipelineResult, reason: str) -> PipelineResult:
    result.status = "FILE_REJECTED"
    result.rejection_reason = reason
    result.summary = reason or "File rejected during validation."
    result.summary_confidence = 0
    result.security_score = scorer.SecurityScore(
        score=0,
        malware_risk="Rejected",
        prompt_injection_risk="None",
        sensitive_data="None",
        threat_indicators="None",
        adversarial_input="None",
        content_moderation="BLOCKED" if result.step8_content_blocked else "Passed",
        penalties={"rejected_before_scoring": 100},
    )
    return result


def _simple_summary(text: str, score: scorer.SecurityScore) -> tuple[str, int]:
    """
    STEP 11 — AI Processing (heuristic summarization).
    """
    if not text or len(text.strip()) < 20:
        return "Document contained insufficient readable text for summarization.", 30

    excerpt = text.strip()[:800].replace("\n\n", "\n")
    if len(text.strip()) > 800:
        excerpt += "…"

    summary = f"[Extractive Preview] {excerpt}"

    base_confidence = 90
    if score.malware_risk == "High":
        base_confidence -= 30
    elif score.malware_risk == "Medium":
        base_confidence -= 15
    if score.prompt_injection_risk == "DETECTED":
        base_confidence -= 20
    if score.threat_indicators == "ALERT":
        base_confidence -= 10

    confidence = max(10, min(base_confidence, 95))
    return summary, confidence


def _has_trigger(triggers: list[dict], trigger_types: set[str]) -> bool:
    return any(t.get("type") in trigger_types for t in (triggers or []))


def _pdf_docx_policy_block(cv) -> str | None:
    """
    Hard blocking policy for PDF/DOCX based on step 2 results.
    """
    triggers = cv.triggers or []

    if getattr(cv, "macros_found", False):
        return "DOCX contains macros or active embedded code."

    if getattr(cv, "javascript_found", False):
        return "JavaScript detected inside PDF."

    if getattr(cv, "embedded_files", 0) > 0:
        return f"Embedded file attachment(s) detected: {cv.embedded_files}."

    if _has_trigger(triggers, {"/OpenAction", "/Launch"}):
        return "Auto-open / Launch action detected."

    if getattr(cv, "risk_level", 1) >= 3:
        return f"High-risk document profile detected: {getattr(cv, 'risk_label', 'High')}."

    return None


def _csv_policy_block(
    result: PipelineResult,
    text: str,
    dlp_result,
    ti_result,
    injection_detected: bool,
    injection_matches: list[str],
) -> PipelineResult:
    """
    Hard policy for CSV files:
    Reject if sensitive data appears with injection or exfiltration indicators,
    or if CSV formula/payload patterns are present.
    """
    reasons: list[str] = []

    sensitive_categories = {
        "email",
        "phone_number",
        "ssn",
        "credit_card",
        "api_key",
        "password",
        "generic_token",
    }
    found_sensitive = set(dlp_result.findings.keys())
    matched_sensitive = sorted(found_sensitive & sensitive_categories)

    if matched_sensitive:
        reasons.append(f"DLP sensitive data detected: {', '.join(matched_sensitive)}")

    if injection_detected:
        if injection_matches:
            reasons.append("Injection detected: " + ", ".join(injection_matches[:5]))
        else:
            reasons.append("Injection detected in CSV content.")

    if getattr(ti_result, "alert", False):
        indicators = getattr(ti_result, "malicious_indicators", [])
        if indicators:
            reasons.append("Threat intel alert: " + "; ".join(indicators[:3]))
        else:
            reasons.append("Threat intel alert: malicious URL or IP detected")

    csv_formula_hits: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if not stripped:
            continue

        if stripped[0] in ("=", "+", "-", "@"):
            csv_formula_hits.append(stripped[:100])

        lowered = stripped.lower()
        if any(tok in lowered for tok in (
            "cmd|",
            "powershell",
            "javascript:",
            "file://",
            "http://pastebin.com",
            "https://pastebin.com",
            "http://rentry.co",
            "https://rentry.co",
        )):
            csv_formula_hits.append(stripped[:100])

    if csv_formula_hits:
        reasons.append("CSV formula / payload pattern detected: " + "; ".join(csv_formula_hits[:3]))

    if matched_sensitive and (injection_detected or getattr(ti_result, "alert", False)):
        reasons.append("Combined risk: sensitive data with injection or exfiltration indicator.")

    if reasons:
        result.step8_content_blocked = True
        result.step8_reason = " | ".join(reasons)
        return _reject(result, result.step8_reason)

    return result


def run(file_path: str) -> PipelineResult:
    """
    Execute the full security pipeline on a file.
    Returns a PipelineResult with all intermediate and final values.
    """
    result = PipelineResult(
        file_path=file_path,
        processed_at=datetime.now(timezone.utc).isoformat(),
    )

    ext = os.path.splitext(file_path)[1].lower()
    result.file_type = ext.lstrip(".").upper() if ext else "UNKNOWN"

    # STEP 1 — File Type Validation
    ok, reason = file_validator.validate(file_path)
    result.step1_ok = ok
    result.step1_reason = reason
    if not ok:
        return _reject(result, reason)

    # STEP 2 — Content Validation
    cv = content_validator.validate(file_path)
    result.step2_ok = cv.ok
    result.step2_reason = cv.reason
    result.step2_gate_report = getattr(cv, "gate_report", {}) or {}

    if not cv.ok:
        return _reject(result, cv.reason)

    # Hard blocking for PDF / DOCX based on content validation
    if result.file_type in {"PDF", "DOCX"}:
        block_reason = _pdf_docx_policy_block(cv)
        if block_reason:
            result.step8_content_blocked = True
            result.step8_reason = block_reason
            return _reject(result, block_reason)

    # STEP 3 — Secure Text Extraction
    text, extract_err = text_extractor.extract(file_path)
    result.step3_text = text
    result.step3_error = extract_err

    # STEP 4 — Text Sanitization
    text, sanitize_actions = sanitizer.sanitize(text)
    result.step4_actions = sanitize_actions

    # STEP 5 — Prompt Injection Detection
    text, injection_detected, injection_matches = injection_detector.detect_and_clean(text)
    result.step5_injection_detected = injection_detected
    result.step5_matches = injection_matches[:10]

    # STEP 6 — DLP
    dlp_result = dlp.scan_and_redact(text)
    text = dlp_result.redacted_text
    result.step6_dlp_findings = dlp_result.findings
    result.step6_total_redacted = dlp_result.total_redacted

    # STEP 7 — Threat Intelligence
    ti = threat_intel.check(text)
    result.step7_threat_alert = ti.alert
    result.step7_indicators = ti.malicious_indicators
    result.step7_urls_found = ti.urls_found[:20]

    # CSV hard-block policy
    if result.file_type == "CSV":
        result = _csv_policy_block(
            result=result,
            text=text,
            dlp_result=dlp_result,
            ti_result=ti,
            injection_detected=injection_detected,
            injection_matches=injection_matches,
        )
        if result.status == "FILE_REJECTED":
            return result

    # STEP 8 — Content Moderation
    mod = content_moderator.moderate(text)
    result.step8_content_blocked = mod.blocked
    result.step8_reason = mod.reason
    if mod.blocked:
        return _reject(result, f"Content moderation: {mod.reason}")

    # STEP 9 — Adversarial Input Detection
    adv = adversarial_detector.detect_and_clean(text)
    text = adv.clean_text
    result.step9_adversarial_detected = adv.detected
    result.step9_techniques = adv.techniques

    # STEP 10 — Security Scoring
    result.clean_text = text
    sec_score = scorer.compute(
        javascript_found=getattr(cv, "javascript_found", False),
        embedded_files=getattr(cv, "embedded_files", 0),
        pdf_risk_level=getattr(cv, "risk_level", 1),
        triggers=getattr(cv, "triggers", []),
        macros_found=getattr(cv, "macros_found", False),
        injection_detected=injection_detected,
        dlp_findings=dlp_result.findings,
        threat_alert=ti.alert,
        content_blocked=mod.blocked,
        adversarial_detected=adv.detected,
    )
    result.security_score = sec_score

    # Optional final low-score safeguard
    if sec_score.score < 30:
        result.step8_content_blocked = True
        result.step8_reason = f"Security score too low: {sec_score.score}/100"
        return _reject(result, result.step8_reason)

    # STEP 11 — AI Processing
    summary_text, confidence = _simple_summary(text, sec_score)

    # STEP 12 — Output Filtering
    safe_summary, removals = output_filter.filter_output(summary_text)
    result.summary = safe_summary
    result.summary_confidence = confidence
    result.output_filter_removals = removals

    result.status = "PROCESSING_COMPLETE"
    return result