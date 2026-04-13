"""
STEP 1 — File Type Validation
Validates file extension, MIME type, and basic file signature safety.
"""

from __future__ import annotations

import os
import mimetypes


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv"}
BLOCKED_EXTENSIONS = {".exe", ".js", ".bat", ".sh", ".dll", ".msi", ".ps1", ".vbs", ".cmd", ".com"}

MAGIC_SIGNATURES = {
    b"%PDF": "application/pdf",
    b"PK\x03\x04": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

DANGEROUS_MAGIC = {
    b"MZ": "Windows PE/EXE",
    b"\x7fELF": "ELF Executable",
    b"#!/": "Shell Script",
    b"#!": "Script",
}

ALLOWED_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/csv",
    "application/vnd.ms-excel",   # common CSV MIME from Excel / browsers
    "application/octet-stream",   # fallback for unknown/plain-text-ish files
}


def _looks_like_text(data: bytes) -> bool:
    """
    Heuristic check for TXT/CSV:
    - reject obvious binary blobs
    - allow normal text, CSV, UTF-8-ish content
    """
    if not data:
        return True

    if b"\x00" in data:
        return False

    text_like = 0
    for b in data:
        if b in (9, 10, 13):  # tab, LF, CR
            text_like += 1
        elif 32 <= b <= 126:  # printable ASCII
            text_like += 1
        elif b >= 128:        # allow UTF-8 / extended text bytes
            text_like += 1

    ratio = text_like / len(data)
    return ratio >= 0.85


def validate(file_path: str) -> tuple[bool, str]:
    """
    Returns (ok, reason).
    ok=True  -> file is accepted for further processing.
    ok=False -> file is rejected; reason explains why.
    """
    if not os.path.isfile(file_path):
        return False, f"File not found: {file_path}"

    ext = os.path.splitext(file_path)[1].lower()

    # 1) Extension check
    if ext in BLOCKED_EXTENSIONS:
        return False, f"Blocked file extension: '{ext}'"

    if ext not in ALLOWED_EXTENSIONS:
        return False, (
            f"Unsupported file extension: '{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # 2) Header / magic-byte check
    with open(file_path, "rb") as f:
        header = f.read(4096)

    for sig, label in DANGEROUS_MAGIC.items():
        if header.startswith(sig):
            return False, f"Dangerous file signature detected ({label}). Extension spoofing suspected."

    if ext not in {".txt", ".csv"}:
        matched = any(header.startswith(sig) for sig in MAGIC_SIGNATURES)
        if not matched:
            return False, (
                f"File magic bytes do not match expected signature for '{ext}' files. "
                "Possible spoofed extension."
            )
    else:
        if not _looks_like_text(header):
            return False, (
                f"'{ext}' file does not appear to be plain text/CSV content. "
                "Possible binary or spoofed file."
            )

    # 3) MIME type check
    mime, _ = mimetypes.guess_type(file_path)
    if mime is None:
        mime = "application/octet-stream"

    if ext == ".pdf":
        if mime != "application/pdf":
            return False, f"MIME type '{mime}' is not allowed for PDF."
    elif ext == ".docx":
        if mime != "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return False, f"MIME type '{mime}' is not allowed for DOCX."
    elif ext == ".csv":
        if mime not in {"text/csv", "text/plain", "application/vnd.ms-excel", "application/octet-stream"}:
            return False, f"MIME type '{mime}' is not allowed for CSV."
    elif ext == ".txt":
        if mime not in {"text/plain", "application/octet-stream"}:
            return False, f"MIME type '{mime}' is not allowed for TXT."

    return True, "File type validation passed."