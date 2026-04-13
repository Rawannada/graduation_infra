import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import urlparse

import pikepdf


SUSPICIOUS_KEYS = [
    "/AA",
    "/JS",
    "/JavaScript",
    "/OpenAction",
    "/Launch",
    "/URI",
    "/SubmitForm",
    "/AcroForm",
    "/RichMedia",
    "/RichMediaActivation",
    "/EmbeddedFile",
    "/GoToE",
    "/GoToR",
    "/Named",
]

HARD_BLOCK_TYPES = {
    "/JS",
    "/JavaScript",
    "/OpenAction",
    "/Launch",
    "/EmbeddedFile",
    "/RichMedia",
    "/RichMediaActivation",
}

HIGH_SEVERITY_TYPES = {
    "/AA",
    "/SubmitForm",
    "/AcroForm",
    "/GoToE",
    "/GoToR",
    "/URI",
    "/Named",
}

def _safe_count(obj) -> int:
    try:
        return len(obj)
    except Exception:
        return 1

def _extract_host(url: str) -> str:
    try:
        parsed = urlparse(url)
        return (parsed.hostname or "").lower()
    except Exception:
        return ""

def _init_report(file_path: str, file_id: str | None) -> dict:
    return {
        "file_id": file_id,
        "file_name": file_path,
        "file_hash": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "javascript_found": False,
        "embedded_files": 0,
        "suspicious_objects": 0,
        "triggers": [],
        "metadata": {},
        "num_pages": None,
        "encrypted": None,
        "objstm_count": None,
        "risk_level": 1,
        "risk_label": "Low",
        "profile": "unknown",
        "engine_version": "pdf-cyber-scanner-v3",
        "security_block": False,
        "security_decision": "accept",
        "trigger_stats": {},
        "total_triggers": 0,
        "flags": {},
        "explanation": "",
    }

def _add_trigger(report: dict, t_type: str, **extra) -> None:
    trig = {"type": t_type, **extra}
    report["triggers"].append(trig)
    report["trigger_stats"][t_type] = report["trigger_stats"].get(t_type, 0) + 1

def scan_pdf(file_path: str, file_id: str | None = None) -> dict:
    report = _init_report(file_path, file_id)

    try:
        with open(file_path, "rb") as f:
            report["file_hash"] = sha256(f.read()).hexdigest()

        pdf = pikepdf.open(file_path)

        try:
            report["num_pages"] = len(pdf.pages)
            report["encrypted"] = bool(pdf.is_encrypted)
            if report["num_pages"] == 1:
                _add_trigger(report, "SinglePageDocument", page=0)
                report["suspicious_objects"] += 1
        except Exception:
            pass

        try:
            report["metadata"] = {k: str(v) for k, v in pdf.docinfo.items()}
        except Exception:
            report["metadata"] = {}

        for idx, page in enumerate(pdf.pages):
            page_str = ""
            contents_str = ""
            annots_str = ""

            try:
                page_str = str(page)
            except Exception:
                pass

            try:
                if getattr(page, "Contents", None) is not None:
                    contents_bytes = page.Contents.read_bytes()
                    contents_str = contents_bytes.decode("latin-1", errors="ignore")
            except Exception:
                pass

            try:
                if "/Annots" in page:
                    annots_str = str(page["/Annots"])
            except Exception:
                pass

            combined = f"{page_str}\n{contents_str}\n{annots_str}"

            for key in SUSPICIOUS_KEYS:
                count = combined.count(key)
                if count:
                    report["suspicious_objects"] += count
                    for _ in range(count):
                        _add_trigger(report, key, page=idx)
                    if key in {"/JS", "/JavaScript"}:
                        report["javascript_found"] = True

        try:
            root_str = str(pdf.Root)
            for key in SUSPICIOUS_KEYS:
                if key in root_str:
                    if not any(t["type"] == key and "page" not in t for t in report["triggers"]):
                        report["suspicious_objects"] += 1
                        _add_trigger(report, key, location="Root/Document-level")
                        if key in {"/JS", "/JavaScript"}:
                            report["javascript_found"] = True
        except Exception:
            pass

        attached_count = 0
        try:
            attached_count = len(pdf.attachments)
        except Exception:
            attached_count = 0

        root_embedded = 0
        try:
            if "/Names" in pdf.Root and "/EmbeddedFiles" in pdf.Root["/Names"]:
                embedded = pdf.Root["/Names"]["/EmbeddedFiles"]
                root_embedded = _safe_count(embedded)
            elif "/EmbeddedFiles" in pdf.Root:
                embedded = pdf.Root["/EmbeddedFiles"]
                root_embedded = _safe_count(embedded)
        except Exception:
            pass

        report["embedded_files"] = max(attached_count, root_embedded)
        if report["embedded_files"] > 0:
            _add_trigger(report, "EmbeddedFiles", count=report["embedded_files"])

        objstm_count = 0
        try:
            for obj in pdf.objects:
                if "/ObjStm" in str(obj):
                    objstm_count += 1
            report["objstm_count"] = objstm_count
            if objstm_count > 0:
                _add_trigger(report, "ObjStmPresent", count=objstm_count)
                report["suspicious_objects"] += 1
        except Exception:
            report["objstm_count"] = None

        uri_triggers = [t for t in report["triggers"] if t["type"] == "/URI"]
        open_launch = [t for t in report["triggers"] if t["type"] in {"/OpenAction", "/Launch"}]
        submit_triggers = [t for t in report["triggers"] if t["type"] == "/SubmitForm"]
        acro_triggers = [t for t in report["triggers"] if t["type"] == "/AcroForm"]
        embedded_triggers = [t for t in report["triggers"] if t["type"] == "EmbeddedFiles"]

        profile = "benign_like"
        if report["javascript_found"] and (embedded_triggers or open_launch):
            profile = "dropper_like"
        elif len(uri_triggers) >= 5 and (submit_triggers or acro_triggers):
            profile = "phishing_like"
        elif submit_triggers or acro_triggers:
            profile = "form_heavy"
        elif embedded_triggers:
            profile = "attachment_heavy"
        elif open_launch:
            profile = "autoopen_like"

        report["profile"] = profile

        if len(uri_triggers) > 5:
            _add_trigger(report, "ManyExternalLinks", count=len(uri_triggers))
            report["suspicious_objects"] += 1

        score = 0

        if report["javascript_found"]:
            score += 7
        if report["embedded_files"] > 0:
            score += 4
        score += min(report["suspicious_objects"], 6)

        if any(t["type"] in {"/OpenAction", "/Launch"} for t in report["triggers"]):
            score += 5
        if any(t["type"] == "ManyExternalLinks" for t in report["triggers"]):
            score += 2
        if any(t["type"] == "SinglePageDocument" for t in report["triggers"]):
            score += 1
        if any(t["type"] == "ObjStmPresent" for t in report["triggers"]):
            score += 2

        if report["javascript_found"] or any(t["type"] in HARD_BLOCK_TYPES for t in report["triggers"]):
            report["risk_level"] = 3
            report["risk_label"] = "High"
        elif score >= 4:
            report["risk_level"] = 2
            report["risk_label"] = "Medium"
        else:
            report["risk_level"] = 1
            report["risk_label"] = "Low"

        hard_block = report["javascript_found"] or any(t["type"] in HARD_BLOCK_TYPES for t in report["triggers"])
        if hard_block:
            report["security_block"] = True
            report["security_decision"] = "reject"
        elif report["risk_level"] == 2:
            report["security_block"] = False
            report["security_decision"] = "review"
        else:
            report["security_block"] = False
            report["security_decision"] = "accept"

        report["total_triggers"] = len(report["triggers"])
        report["flags"] = {
            "has_javascript": report["javascript_found"],
            "has_embedded_files": report["embedded_files"] > 0,
            "has_forms": any(t["type"] in {"/AcroForm", "/SubmitForm"} for t in report["triggers"]),
            "has_external_links": any(t["type"] == "/URI" for t in report["triggers"]),
            "is_single_page": report["num_pages"] == 1,
            "has_objstm": (report["objstm_count"] or 0) > 0,
            "has_open_action": any(t["type"] == "/OpenAction" for t in report["triggers"]),
            "has_launch_action": any(t["type"] == "/Launch" for t in report["triggers"]),
        }

        explanation_parts = []

        if report["javascript_found"]:
            explanation_parts.append("JavaScript detected inside the PDF.")
        if report["embedded_files"] > 0:
            explanation_parts.append(f"{report['embedded_files']} embedded file(s) detected.")
        if any(t["type"] in {"/OpenAction", "/Launch"} for t in report["triggers"]):
            explanation_parts.append("Auto-open action detected.")
        if len(uri_triggers) > 5:
            explanation_parts.append("High number of external links.")
        if report["encrypted"]:
            explanation_parts.append("Document is encrypted.")
        if any(t["type"] == "ObjStmPresent" for t in report["triggers"]):
            explanation_parts.append("Object streams found, which may indicate obfuscation.")

        if not explanation_parts:
            report["explanation"] = "No strong malicious indicators detected. Document looks benign-like."
        else:
            report["explanation"] = " ".join(explanation_parts)

        report_file = file_path + ".report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=4)

        pdf.close()
        return report

    except Exception as e:
        report["error"] = str(e)
        return report


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gate.py <pdf_file_path> [file_id]")
        sys.exit(1)

    file_path = sys.argv[1]
    file_id = sys.argv[2] if len(sys.argv) >= 3 else None

    print(f"\n[+] Scanning file: {file_path}\n")
    report = scan_pdf(file_path, file_id=file_id)

    print("=== PDF Cyber Scan Report ===")
    print(f"File ID           : {report['file_id']}")
    print(f"File Name         : {report['file_name']}")
    print(f"File SHA256       : {report['file_hash']}")
    print(f"Num Pages         : {report['num_pages']}")
    print(f"Encrypted         : {report['encrypted']}")
    print(f"ObjStm Count      : {report['objstm_count']}")
    print(f"Javascript Found  : {report['javascript_found']}")
    print(f"Embedded Files    : {report['embedded_files']}")
    print(f"Suspicious Obj    : {report['suspicious_objects']}")
    print(f"Metadata          : {report['metadata']}")
    print(f"Risk Level        : {report['risk_label']} ({report['risk_level']})")
    print(f"Profile           : {report['profile']}")
    print(f"Engine Version    : {report['engine_version']}")
    print(f"Security Decision : {report['security_decision']}")
    print(f"Security Block    : {report['security_block']}")
    print(f"Total Triggers    : {report.get('total_triggers')}")
    print(f"Trigger Stats     : {report.get('trigger_stats')}")
    print(f"Flags             : {report.get('flags')}")
    print(f"Explanation       : {report.get('explanation')}")
    print(f"Triggers          : {report['triggers']}")
    if "error" in report:
        print(f"Error             : {report['error']}")
    print("==============================\n")