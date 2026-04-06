"""
STEP 1 — File Type Validation
Validates file extension, MIME type, and magic bytes.
"""

import os
import mimetypes

# Allowed and blocked extensions
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
BLOCKED_EXTENSIONS = {".exe", ".js", ".bat", ".sh", ".dll", ".msi", ".ps1", ".vbs", ".cmd", ".com"}

# Magic byte signatures for allowed types
MAGIC_SIGNATURES = {
    b"%PDF":               "application/pdf",
    b"PK\x03\x04":        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX (ZIP)
}

# Known dangerous magic bytes
DANGEROUS_MAGIC = {
    b"MZ":          "Windows PE/EXE",
    b"\x7fELF":     "ELF Executable",
    b"#!/":         "Shell Script",
    b"#!":          "Script",
}

ALLOWED_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "application/octet-stream",   # sometimes TXT/binary files report this
}


def validate(file_path: str) -> tuple[bool, str]:
    """
    Returns (ok, reason).
    ok=True  → file is accepted for further processing.
    ok=False → file is rejected; reason explains why.
    """
    if not os.path.isfile(file_path):
        return False, f"File not found: {file_path}"

    # ── 1. Extension check ──────────────────────────────────────────────────
    ext = os.path.splitext(file_path)[1].lower()
    if ext in BLOCKED_EXTENSIONS:
        return False, f"Blocked file extension: '{ext}'"
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file extension: '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"

    # ── 2. Magic bytes check ────────────────────────────────────────────────
    with open(file_path, "rb") as f:
        header = f.read(8)

    for sig, label in DANGEROUS_MAGIC.items():
        if header.startswith(sig):
            return False, f"Dangerous file signature detected ({label}). Extension spoofing suspected."

    # For TXT files we skip magic-byte enforcement (plain text has no fixed header)
    if ext != ".txt":
        matched = False
        for sig in MAGIC_SIGNATURES:
            if header.startswith(sig):
                matched = True
                break
        if not matched:
            return False, f"File magic bytes do not match expected signature for '{ext}' files. Possible spoofed extension."

    # ── 3. MIME type check (best-effort, stdlib only) ────────────────────────
    mime, _ = mimetypes.guess_type(file_path)
    if mime is None:
        mime = "application/octet-stream"   # unknown — allow through; magic bytes already checked

    # strictly enforce on non-TXT
    if ext != ".txt" and mime not in ALLOWED_MIMES:
        return False, f"MIME type '{mime}' is not allowed."

    return True, "File type validation passed."
