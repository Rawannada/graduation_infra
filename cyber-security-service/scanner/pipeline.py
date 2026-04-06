"""
scanner/pipeline.py — Main 14-Step Security Pipeline Orchestrator
Runs all security checks in order and returns a unified PipelineResult.
"""

import os
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Direct imports (no scanner. prefix needed)
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
    status: str = "PROCESSING"       # FILE_REJECTED | PROCESSING_COMPLETE
    rejection_reason: str = ""

    # Clean, analysis-ready text
    clean_text: str = ""

    # Output filter removals
    output_filter_removals: list[str] = field(default_factory=list)

    # Short summary produced by the AI analysis layer (Step 11)
    summary: str = ""
    summary_confidence: int = 0

    def to_dict(self) -> dict:
        """Convert to a JSON-serialisable dict."""
        d = {k: v for k, v in self.__dict__.items()}
        # SecurityScore is a dataclass — convert it too
        d["security_score"] = self.security_score.__dict__
        return d


# ─────────────────────────────────────────────────────────────────────────────

def _simple_summary(text: str, score: scorer.SecurityScore) -> tuple[str, int]:
    """
    STEP 11 — AI Processing (simulated summarization).
    Produces a brief extractive summary and a confidence score.
    In production this would call an LLM API; here we use heuristics.
    """
    if not text or len(text.strip()) < 20:
        return "Document contained insufficient readable text for summarization.", 30

    # Take up to 800 chars of the clean text as a stand-in for a real summary
    excerpt = text.strip()[:800].replace("\n\n", "\n")
    if len(text.strip()) > 800:
        excerpt += "…"

    summary = f"[Extractive Preview] {excerpt}"

    # Confidence degrades with risk
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


# ─────────────────────────────────────────────────────────────────────────────

def run(file_path: str) -> PipelineResult:
    """
    Execute the full 14-step security pipeline on a file.
    Returns a PipelineResult with all intermediate and final values.
    """
    result = PipelineResult(
        file_path=file_path,
        processed_at=datetime.now(timezone.utc).isoformat(),
    )
    ext = os.path.splitext(file_path)[1].lower()
    result.file_type = ext.lstrip(".").upper() if ext else "UNKNOWN"

    # ── STEP 1 — File Type Validation ────────────────────────────────────────
    ok, reason = file_validator.validate(file_path)
    result.step1_ok = ok
    result.step1_reason = reason
    if not ok:
        result.status = "FILE_REJECTED"
        result.rejection_reason = reason
        return result

    # ── STEP 2 — Content Validation ──────────────────────────────────────────
    cv = content_validator.validate(file_path)
    result.step2_ok = cv.ok
    result.step2_reason = cv.reason
    result.step2_gate_report = cv.gate_report
    if not cv.ok:
        result.status = "FILE_REJECTED"
        result.rejection_reason = cv.reason
        return result

    # ── STEP 3 — Secure Text Extraction ──────────────────────────────────────
    text, extract_err = text_extractor.extract(file_path)
    result.step3_text = text
    result.step3_error = extract_err

    # ── STEP 4 — Text Sanitization ───────────────────────────────────────────
    text, sanitize_actions = sanitizer.sanitize(text)
    result.step4_actions = sanitize_actions

    # ── STEP 5 — Prompt Injection Detection ──────────────────────────────────
    text, injection_detected, injection_matches = injection_detector.detect_and_clean(text)
    result.step5_injection_detected = injection_detected
    result.step5_matches = injection_matches[:10]   # cap for report size

    # ── STEP 6 — DLP (Sensitive Data Detection) ──────────────────────────────
    dlp_result = dlp.scan_and_redact(text)
    text = dlp_result.redacted_text
    result.step6_dlp_findings = dlp_result.findings
    result.step6_total_redacted = dlp_result.total_redacted

    # ── STEP 7 — Threat Intelligence ─────────────────────────────────────────
    ti = threat_intel.check(text)
    result.step7_threat_alert = ti.alert
    result.step7_indicators = ti.malicious_indicators
    result.step7_urls_found = ti.urls_found[:20]    # cap for report size

    # ── STEP 8 — Content Moderation ──────────────────────────────────────────
    mod = content_moderator.moderate(text)
    result.step8_content_blocked = mod.blocked
    result.step8_reason = mod.reason
    if mod.blocked:
        result.status = "FILE_REJECTED"
        result.rejection_reason = f"Content moderation: {mod.reason}"
        return result

    # ── STEP 9 — Adversarial Input Detection ─────────────────────────────────
    adv = adversarial_detector.detect_and_clean(text)
    text = adv.clean_text
    result.step9_adversarial_detected = adv.detected
    result.step9_techniques = adv.techniques

    # ── STEP 10 — Security Scoring ───────────────────────────────────────────
    result.clean_text = text
    sec_score = scorer.compute(
        javascript_found=cv.javascript_found,
        embedded_files=cv.embedded_files,
        pdf_risk_level=cv.risk_level,
        triggers=cv.triggers,
        macros_found=cv.macros_found,
        injection_detected=injection_detected,
        dlp_findings=dlp_result.findings,
        threat_alert=ti.alert,
        content_blocked=mod.blocked,
        adversarial_detected=adv.detected,
    )
    result.security_score = sec_score

    # ── STEP 11 — AI Processing ───────────────────────────────────────────────
    summary_text, confidence = _simple_summary(text, sec_score)

    # ── STEP 12 — Output Filtering ───────────────────────────────────────────
    safe_summary, removals = output_filter.filter_output(summary_text)
    result.summary = safe_summary
    result.summary_confidence = confidence
    result.output_filter_removals = removals

    result.status = "PROCESSING_COMPLETE"
    return result


# ── STEPS 13 & 14 — Formatted Report ─────────────────────────────────────────

# Width of the report body
_W = 72

def _line(char: str = "─") -> str:
    return char * _W

def _header(text: str, char: str = "═") -> str:
    return char * _W + "\n" + f"  {text}" + "\n" + char * _W

def _section(title: str) -> str:
    pad = _W - 4 - len(title)
    return f"\n{'─' * _W}\n  {title}  {'─' * max(0, pad)}\n"

def _badge(label: str, value: str) -> str:
    """Left-aligned key : right-styled value."""
    return f"  {label:<28}: {value}"

def _risk_bar(score: int) -> str:
    """ASCII progress bar for the security score (0=bad, 100=good)."""
    filled = round(score / 5)          # out of 20 blocks
    empty  = 20 - filled
    bar    = "█" * filled + "░" * empty
    if score >= 80:
        grade = "SAFE"
    elif score >= 55:
        grade = "MODERATE RISK"
    elif score >= 30:
        grade = "HIGH RISK"
    else:
        grade = "CRITICAL RISK"
    return f"  [{bar}]  {score}/100  ({grade})"

def _verdict_banner(score: int, status: str) -> list[str]:
    """Big verdict block at the top of the report."""
    if status == "FILE_REJECTED":
        emoji = "🚫"
        word  = "FILE REJECTED"
        border = "!"
    elif score >= 80:
        emoji = "✅"
        word  = "DOCUMENT ACCEPTED — LOW RISK"
        border = "="
    elif score >= 55:
        emoji = "⚠️"
        word  = "ACCEPTED WITH WARNINGS — MODERATE RISK"
        border = "-"
    else:
        emoji = "🔴"
        word  = "HIGH RISK — ANALYST REVIEW REQUIRED"
        border = "!"
    inner = f"  {emoji}  {word}  {emoji}"
    return [
        border * _W,
        inner,
        border * _W,
    ]


def format_report(result: PipelineResult) -> str:
    """
    STEP 13 (Explainable Security) + STEP 14 (Confidence Score).
    Produces a comprehensive, SOC-grade security report.
    """
    L: list[str] = []
    sc   = result.security_score
    gr   = result.step2_gate_report or {}
    name = os.path.basename(result.file_path)

    # ══════════════════════════════════════════════════════════════════════════
    # HEADER
    # ══════════════════════════════════════════════════════════════════════════
    L.append("═" * _W)
    L.append("  SECURE AI DOCUMENT PROCESSING ENGINE")
    L.append("  Comprehensive Security Analysis Report  │  v2.0  │  14-Step Pipeline")
    L.append("═" * _W)
    L.append(f"  File       : {name}")
    L.append(f"  Full Path  : {result.file_path}")
    L.append(f"  Type       : {result.file_type}")
    L.append(f"  Scanned At : {result.processed_at}")
    if gr.get("file_hash"):
        L.append(f"  SHA-256    : {gr['file_hash']}")
    L.append("")

    # ── Verdict banner ────────────────────────────────────────────────────────
    for b in _verdict_banner(sc.score if result.status != "FILE_REJECTED" else 0,
                              result.status):
        L.append(b)
    L.append("")

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1 — EXECUTIVE SUMMARY
    # ══════════════════════════════════════════════════════════════════════════
    L.append(_section("SECTION 1  —  EXECUTIVE SUMMARY"))

    if result.status == "FILE_REJECTED":
        L.append("  STATUS         : ❌  FILE REJECTED")
        L.append(f"  REJECTION CAUSE: {result.rejection_reason}")
        L.append("")

        # Quick checklist of what failed
        checks = [
            ("File Type Validation",  result.step1_ok),
            ("Content Validation",    result.step2_ok),
            ("Content Moderation",    not result.step8_content_blocked),
        ]
        L.append("  Security Gate Results:")
        for label, passed in checks:
            icon = "✓" if passed else "✗"
            L.append(f"    [{icon}]  {label}")
        L.append("")
        L.append(_line())
        return "\n".join(L)

    # Normal accepted path
    L.append("  STATUS              : ✅  PROCESSING COMPLETE")
    L.append("")
    L.append("  Risk Score at a Glance:")
    L.append(_risk_bar(sc.score))
    L.append("")

    # 4-column summary table
    cols = [
        ("Malware / Binary Risk",   sc.malware_risk),
        ("Prompt Injection",        sc.prompt_injection_risk),
        ("Sensitive Data (DLP)",    sc.sensitive_data),
        ("Threat Intel Indicators", sc.threat_indicators),
        ("Adversarial Obfuscation", sc.adversarial_input),
        ("Content Moderation",      sc.content_moderation),
    ]
    L.append("  ┌──────────────────────────────┬───────────────────────────┐")
    L.append("  │ Security Dimension           │ Result                    │")
    L.append("  ├──────────────────────────────┼───────────────────────────┤")
    for label, val in cols:
        L.append(f"  │ {label:<28} │ {val:<25} │")
    L.append("  └──────────────────────────────┴───────────────────────────┘")

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — FILE METADATA & STRUCTURE
    # ══════════════════════════════════════════════════════════════════════════
    L.append(_section("SECTION 2  —  FILE METADATA & STRUCTURE"))

    file_size = "N/A"
    try:
        file_size = f"{os.path.getsize(result.file_path):,} bytes"
    except Exception:
        pass

    L.append(_badge("File Name",             name))
    L.append(_badge("File Size",             file_size))
    L.append(_badge("File Type",             result.file_type))
    L.append(_badge("SHA-256 Hash",          gr.get("file_hash", "N/A")))
    L.append(_badge("Pages",                 str(gr.get("num_pages", "N/A"))))
    L.append(_badge("Encrypted",             str(gr.get("encrypted", "N/A"))))
    L.append(_badge("Object Streams (ObjStm)", str(gr.get("objstm_count", "N/A"))))
    L.append(_badge("Document Profile",      gr.get("profile", "N/A")))
    L.append(_badge("Engine Version",        gr.get("engine_version", "pdf-cyber-scanner-v2")))
    L.append(_badge("Chars Extracted",       str(len(result.step3_text))))
    if result.step3_error:
        L.append(_badge("Extraction Warning",    result.step3_error))

    # PDF Metadata block
    meta = gr.get("metadata", {})
    if meta:
        L.append("")
        L.append("  PDF Document Properties:")
        for k, v in meta.items():
            L.append(f"    {k:<20}: {str(v)[:55]}")

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3 — BINARY / CONTENT ANALYSIS (gate.py results)
    # ══════════════════════════════════════════════════════════════════════════
    L.append(_section("SECTION 3  —  BINARY & EMBEDDED CONTENT ANALYSIS"))

    L.append(_badge("JavaScript Detected",   "⚠ YES" if gr.get("javascript_found") else "✓ None"))
    L.append(_badge("Embedded Files",        f"{gr.get('embedded_files', 0)} file(s)"))
    L.append(_badge("Suspicious Objects",    str(gr.get("suspicious_objects", 0))))
    L.append(_badge("Total Triggers Fired",  str(gr.get("total_triggers", 0))))
    L.append(_badge("Binary Risk Level",     f"{gr.get('risk_label','N/A')}  (Level {gr.get('risk_level','N/A')}/3)"))

    # Trigger detail table
    triggers = gr.get("triggers", [])
    if triggers:
        L.append("")
        L.append("  Trigger Detail Log:")
        L.append("  ┌──────────────────────────┬────────┬──────────────────────┐")
        L.append("  │ Trigger Type             │ Page   │ Notes                │")
        L.append("  ├──────────────────────────┼────────┼──────────────────────┤")
        for t in triggers:
            ttype = str(t.get("type", ""))[:24]
            tpage = str(t.get("page", t.get("count", "")))[:6]
            tnote = ""
            if t.get("type") in ["/JS", "/JavaScript"]:
                tnote = "⚠ Active JavaScript"
            elif t.get("type") == "EmbeddedFiles":
                tnote = f"{t.get('count','?')} attachment(s)"
            elif t.get("type") == "ObjStmPresent":
                tnote = "Possible obfuscation"
            elif t.get("type") == "/OpenAction":
                tnote = "Auto-exec on open"
            elif t.get("type") == "/Launch":
                tnote = "⚠ Launch action"
            elif t.get("type") == "/URI":
                tnote = "External link"
            elif t.get("type") == "/SubmitForm":
                tnote = "Data exfil risk"
            elif t.get("type") == "ManyExternalLinks":
                tnote = "Phishing indicator"
            L.append(f"  │ {ttype:<24} │ {tpage:<6} │ {tnote:<20} │")
        L.append("  └──────────────────────────┴────────┴──────────────────────┘")

        # Trigger stats
        stats = gr.get("trigger_stats", {})
        if stats:
            L.append("")
            L.append("  Trigger Frequency Summary:")
            for ttype, cnt in stats.items():
                bar = "▪" * min(cnt, 20)
                L.append(f"    {ttype:<28} {bar} ({cnt})")
    else:
        L.append("")
        L.append("  No binary-level triggers detected — structure appears benign.")

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 4 — TEXT LAYER ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    L.append(_section("SECTION 4  —  TEXT LAYER ANALYSIS"))

    # Step 4 — Sanitization
    L.append("  [Step 4]  Text Sanitization:")
    if result.step4_actions:
        for a in result.step4_actions:
            L.append(f"    • {a}")
    else:
        L.append("    • No sanitization actions required — text was clean.")

    # Step 5 — Prompt Injection
    L.append("")
    inj_status = "⚠  PROMPT INJECTION ATTEMPTS DETECTED" if result.step5_injection_detected else "✓  No prompt injection patterns found"
    L.append(f"  [Step 5]  Prompt Injection Detection  :  {inj_status}")
    if result.step5_matches:
        L.append(f"  {'─'*66}")
        L.append("  Matched Patterns (first 10):")
        for i, m in enumerate(result.step5_matches[:10], 1):
            L.append(f"    [{i:02d}] \"{m[:70]}\"")
        L.append("  All matched patterns have been REMOVED from the processed text.")

    # Step 9 — Adversarial
    L.append("")
    adv_status = "⚠  Adversarial patterns neutralized" if result.step9_adversarial_detected else "✓  No adversarial input detected"
    L.append(f"  [Step 9]  Adversarial Input Detection :  {adv_status}")
    if result.step9_techniques:
        for t in result.step9_techniques:
            desc = {
                "zero_width_character_steganography": "Zero-width / invisible Unicode used to hide instructions",
                "homoglyph_substitution":             "Lookalike characters (Cyrillic/Greek/fullwidth) to evade filters",
                "unicode_normalization_evasion":      "Composed Unicode sequences used to bypass pattern matching",
                "base64_encoded_injection":           "Base64-encoded payload decoded to reveal injection attempt",
            }.get(t, t)
            L.append(f"    ⚠  {desc}")

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 5 — DATA LOSS PREVENTION (DLP)
    # ══════════════════════════════════════════════════════════════════════════
    L.append(_section("SECTION 5  —  DATA LOSS PREVENTION (DLP)"))

    if result.step6_total_redacted > 0:
        L.append(f"  ⚠  {result.step6_total_redacted} sensitive item(s) detected and REDACTED")
        L.append("")
        L.append("  ┌──────────────────────────────┬────────┬───────────────────┐")
        L.append("  │ Data Category                │  Count │ Action Taken      │")
        L.append("  ├──────────────────────────────┼────────┼───────────────────┤")
        category_descriptions = {
            "email":               "Email Addresses",
            "phone_number":        "Phone Numbers",
            "credit_card":         "Credit Card Numbers",
            "ssn":                 "Social Security Numbers",
            "api_key":             "API Keys / Tokens",
            "generic_token":       "Generic Secret Tokens",
            "password":            "Password / Secret Values",
            "ip_address_with_port":"IP:Port Combinations",
        }
        for cat, cnt in result.step6_dlp_findings.items():
            label = category_descriptions.get(cat, cat)
            L.append(f"  │ {label:<28} │ {cnt:>6} │ [REDACTED]        │")
        L.append("  └──────────────────────────────┴────────┴───────────────────┘")
        L.append("")
        L.append("  ⚠  All values above have been replaced with [REDACTED]")
        L.append("     in the processed text before AI analysis.")
    else:
        L.append("  ✓  No PII or sensitive credentials detected in document text.")

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 6 — THREAT INTELLIGENCE
    # ══════════════════════════════════════════════════════════════════════════
    L.append(_section("SECTION 6  —  THREAT INTELLIGENCE"))

    url_count = len(result.step7_urls_found)
    L.append(_badge("URLs Found in Document",      str(url_count)))
    L.append(_badge("Threat Intel Alert",
                    "🔴  MALICIOUS INDICATORS FOUND" if result.step7_threat_alert
                    else "✓  No known-bad indicators"))

    if result.step7_urls_found:
        L.append("")
        L.append("  URLs Extracted:")
        for url in result.step7_urls_found[:15]:
            flag = " ⚠ BLOCKLISTED" if any(
                url in ind for ind in result.step7_indicators
            ) else ""
            L.append(f"    • {url[:65]}{flag}")
        if url_count > 15:
            L.append(f"    … and {url_count - 15} more (see JSON report for full list)")

    if result.step7_indicators:
        L.append("")
        L.append("  🔴  Malicious / Suspicious Indicators Detected:")
        for ind in result.step7_indicators:
            L.append(f"    ▸ {ind}")

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 7 — SECURITY SCORING BREAKDOWN
    # ══════════════════════════════════════════════════════════════════════════
    L.append(_section("SECTION 7  —  SECURITY SCORING BREAKDOWN"))

    L.append(_risk_bar(sc.score))
    L.append("")
    L.append(f"  Final Score  : {sc.score} / 100  (higher = safer)")
    L.append("")

    if sc.penalties:
        L.append("  Penalty Ledger:")
        L.append("  ┌──────────────────────────────────┬─────────────┬──────────┐")
        L.append("  │ Risk Factor                      │ Penalty     │ Cumulative│")
        L.append("  ├──────────────────────────────────┼─────────────┼──────────┤")
        running = 100
        for factor, pts in sc.penalties.items():
            running -= pts
            display = {
                "javascript":      "JavaScript Detected",
                "embedded_files":  "Embedded File(s)",
                "open_or_launch":  "Auto-Open / Launch Action",
                "high_risk_pdf":   "High Binary Risk (gate scan)",
                "medium_risk_pdf": "Medium Binary Risk (gate scan)",
                "macros_found":    "VBA Macros in DOCX",
                "prompt_injection":"Prompt Injection Detected",
                "dlp_findings":    "Sensitive Data Exposed (DLP)",
                "threat_intel":    "Threat Intel IOC Match",
                "content_blocked": "Prohibited Content Found",
                "adversarial_input":"Adversarial Input Patterns",
                "objstm":          "Object Stream Obfuscation",
                "many_links":      "Excessive External Links",
            }.get(factor, factor)
            L.append(f"  │ {display:<32} │ -{pts:<11} │ {max(0,running):<9}│")
        L.append("  └──────────────────────────────────┴─────────────┴──────────┘")
    else:
        L.append("  ✓  No penalties applied — document scored maximum 100/100.")

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 8 — DOCUMENT CONTENT PREVIEW  (Step 11 — AI Processing)
    # ══════════════════════════════════════════════════════════════════════════
    L.append(_section("SECTION 8  —  DOCUMENT CONTENT PREVIEW  (AI Processing)"))

    L.append(f"  Analysis Confidence   : {result.summary_confidence}%")
    L.append("")
    # Wrap summary at 68 chars
    summary_body = result.summary.replace("[Extractive Preview] ", "")
    for line in summary_body.split("\n"):
        while len(line) > 68:
            L.append(f"  {line[:68]}")
            line = line[68:]
        if line.strip():
            L.append(f"  {line}")

    if result.output_filter_removals:
        L.append("")
        L.append("  [Step 12] Output Filter Actions:")
        for r in result.output_filter_removals:
            L.append(f"    ↳ {r}")

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 9 — ANALYST RECOMMENDATIONS
    # ══════════════════════════════════════════════════════════════════════════
    L.append(_section("SECTION 9  —  ANALYST RECOMMENDATIONS"))

    recs: list[tuple[str, str]] = []  # (priority, text)

    if gr.get("javascript_found"):
        recs.append(("CRITICAL", "JavaScript detected inside the PDF. Open ONLY in an isolated sandbox. "
                     "Do NOT execute in a production viewer. Strip JS before distribution."))
    if gr.get("embedded_files", 0) > 0:
        recs.append(("HIGH", f"{gr['embedded_files']} embedded file(s) found. Extract and scan each attachment "
                     "independently before opening."))
    if any(t.get("type") in ["/OpenAction", "/Launch"] for t in triggers):
        recs.append(("CRITICAL", "Auto-open / Launch action present. This file will attempt to execute code "
                     "automatically when opened. Block at the gateway."))
    if result.step5_injection_detected:
        recs.append(("HIGH", "Prompt injection patterns were found and neutralized. If this document "
                     "is processed by an AI system, verify that injection removal was successful."))
    if result.step6_total_redacted > 0:
        recs.append(("HIGH", f"{result.step6_total_redacted} sensitive data item(s) detected (PII/credentials). "
                     "Notify data protection team. Audit document origin and access history."))
    if result.step7_threat_alert:
        recs.append(("CRITICAL", f"{len(result.step7_indicators)} threat intelligence hit(s). "
                     "Block the listed IOCs at the firewall/proxy. Report to SOC for incident investigation."))
    if result.step9_adversarial_detected:
        recs.append(("MEDIUM", "Adversarial Unicode obfuscation detected. The document may be crafted to "
                     "evade text-based filters. Treat as suspicious; request additional human review."))
    if gr.get("objstm_count", 0):
        recs.append(("MEDIUM", "Object streams (ObjStm) are present. These can hide malicious content "
                     "from simple PDF parsers. Validate with a full-extraction tool (e.g., pdfid, pdf-parser)."))
    if gr.get("encrypted"):
        recs.append(("LOW", "Document is encrypted. Encrypted PDFs can hide malicious content "
                     "from static scanners. Decrypt in sandbox before deep analysis."))
    if gr.get("num_pages") == 1:
        recs.append(("LOW", "Single-page document — a common trait of malware dropper PDFs. "
                     "Corroborate with other risk signals."))

    if not recs:
        recs.append(("INFO", "No specific remediation actions required. Document appears low-risk. "
                     "Continue standard handling procedures."))

    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    recs.sort(key=lambda x: priority_order.get(x[0], 5))

    priority_icons = {
        "CRITICAL": "🔴 CRITICAL",
        "HIGH":     "🟠 HIGH    ",
        "MEDIUM":   "🟡 MEDIUM  ",
        "LOW":      "🔵 LOW     ",
        "INFO":     "⚪ INFO    ",
    }

    for i, (priority, text) in enumerate(recs, 1):
        icon = priority_icons.get(priority, priority)
        L.append(f"  [{i}] {icon}  —  {text[:120]}")
        if len(text) > 120:
            remaining = text[120:]
            while remaining:
                L.append(f"       {remaining[:110]}")
                remaining = remaining[110:]
        L.append("")

    # ══════════════════════════════════════════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════════════════════════════════════════
    L.append("═" * _W)
    L.append(f"  Security Score  : {sc.score}/100    │    Analysis Confidence : {result.summary_confidence}%")
    L.append(f"  Decision        : {gr.get('security_decision','accept').upper()}")
    L.append(f"  Engine          : {gr.get('engine_version','pdf-cyber-scanner-v2')}  │  Pipeline Steps: 14")
    L.append("═" * _W)
    L.append("  END OF REPORT")
    L.append("═" * _W)
    L.append("")

    return "\n".join(L)

