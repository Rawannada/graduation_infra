import os
import sys
import zipfile
from dataclasses import dataclass, field

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from gate import scan_pdf, SUSPICIOUS_KEYS  # noqa: F401


@dataclass
class ContentValidationResult:
    ok: bool = True
    reason: str = ""
    javascript_found: bool = False
    embedded_files: int = 0
    suspicious_objects: int = 0
    triggers: list = field(default_factory=list)
    risk_level: int = 1
    risk_label: str = "Low"
    profile: str = "benign_like"
    gate_report: dict = field(default_factory=dict)
    macros_found: bool = False


def validate_pdf(file_path: str) -> ContentValidationResult:
    """
    Run the existing gate.py scanner on a PDF file.
    """
    result = ContentValidationResult()

    try:
        report = scan_pdf(file_path)

        result.gate_report = report
        result.javascript_found = report.get("javascript_found", False)
        result.embedded_files = report.get("embedded_files", 0)
        result.suspicious_objects = report.get("suspicious_objects", 0)
        result.triggers = report.get("triggers", [])
        result.risk_level = report.get("risk_level", 1)
        result.risk_label = report.get("risk_label", "Low")
        result.profile = report.get("profile", "benign_like")

        security_decision = report.get("security_decision", "accept")
        if security_decision == "reject":
            result.ok = False
            result.reason = (
                f"PDF rejected by binary scanner: "
                f"{report.get('explanation', 'High-risk content detected.')}"
            )

    except Exception as e:
        result.ok = False
        result.reason = f"PDF content validation error: {e}"

    return result


def validate_docx(file_path: str) -> ContentValidationResult:
    """
    Inspect a DOCX ZIP file for VBA macros and embedded scripts.
    DOCX files are ZIP archives and macros often appear as vbaProject.bin.
    """
    result = ContentValidationResult()

    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            names = zf.namelist()

            macro_files = [n for n in names if "vbaProject" in n or n.endswith(".bin")]
            if macro_files:
                result.macros_found = True
                result.ok = False
                result.reason = (
                    f"DOCX contains VBA macro file(s): {', '.join(macro_files)}. "
                    f"Macro-enabled documents are rejected for security."
                )
                return result

            for name in names:
                if name.endswith(".xml") or name.endswith(".rels"):
                    try:
                        content = zf.read(name).decode("utf-8", errors="ignore")
                        lowered = content.lower()

                        if "<script" in lowered or "javascript:" in lowered:
                            result.ok = False
                            result.reason = f"Embedded script detected in DOCX part: {name}"
                            return result
                    except Exception:
                        pass

    except zipfile.BadZipFile:
        result.ok = False
        result.reason = "DOCX file is not a valid ZIP archive (corrupted or spoofed)."
    except Exception as e:
        result.ok = False
        result.reason = f"DOCX content validation error: {e}"

    return result


def validate_csv(file_path: str) -> ContentValidationResult:
    """
    Parse CSV to check for CSV Injection (DDE) attacks.
    If any cell starts with '=', '+', '-', or '@' and contains non-numeric payload, reject it.
    """
    import csv
    result = ContentValidationResult()
    triggers = ('=', '+', '-', '@')
    
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            with open(file_path, "r", encoding=encoding, errors="replace", newline="") as f:
                reader = csv.reader(f)
                for row_idx, row in enumerate(reader):
                    for cell in row:
                        c = cell.strip()
                        if c.startswith(triggers):
                            # Strip out common number/phone/date characters
                            import re
                            remainder = re.sub(r'[\d\.,\-\(\)\s]', '', c[1:])
                            # If there are still alphabetic/symbol characters left, it might be a payload
                            if len(c) > 1 and remainder:
                                result.ok = False
                                result.reason = f"CSV Injection (DDE) detected in row {row_idx+1}: '{c[:30]}...'"
                                return result
            result.ok = True
            result.reason = "CSV passed injection validation."
            return result
        except Exception:
            continue
            
    result.ok = False
    result.reason = "CSV validation failed: could not decode file."
    return result


def validate(file_path: str) -> ContentValidationResult:
    """
    Route to the correct content validator based on file extension.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return validate_pdf(file_path)
    elif ext == ".docx":
        return validate_docx(file_path)
    elif ext == ".csv":
        return validate_csv(file_path)
    else:
        return ContentValidationResult(
            ok=True,
            reason="TXT files pass content validation by default."
        )