"""
main.py — CLI entry point for the Secure AI Document Processing Engine.

Usage:
    python main.py <file_path> [--json] [--output <report_file.json>]

Examples:
    python main.py document.pdf
    python main.py document.pdf --json
    python main.py document.pdf --output report.json
    python main.py document.pdf --json --output report.json
"""

import argparse
import json
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scanner.pipeline import run, format_report


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pdf-security-scanner",
        description=(
            "Secure AI Document Processing Engine\n"
            "Analyzes PDF, DOCX, and TXT files through a 14-step security pipeline."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to the document to scan (PDF, DOCX, or TXT).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Also print the full JSON report to stdout after the text report.",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        default=None,
        help="Write the JSON report to this file path.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="Suppress the gate.py console output during PDF binary scan.",
    )

    args = parser.parse_args()

    file_path = args.file

    if not file_path:
        print("\n[!] No file specified. Please provide a path to a PDF, DOCX, or TXT file.")
        
        # List available files in current directory
        supported_exts = (".pdf", ".docx", ".txt")
        files = [f for f in os.listdir(".") if f.lower().endswith(supported_exts)]
        
        if files:
            print("\nAvailable documents in current directory:")
            for f in files:
                print(f"  - {f}")
            print(f"\nExample usage: python main.py {files[0]}")
        else:
            print("\nUsage: python main.py <file_path> [--json] [--output <report_file.json>]")
        
        sys.exit(1)

    # Optionally suppress gate.py stdout during PDF scan
    if args.quiet:
        import io
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

    try:
        result = run(file_path)
    finally:
        if args.quiet:
            sys.stdout = old_stdout

    # ── Human-readable report ─────────────────────────────────────────────────
    report_text = format_report(result)
    print(report_text)

    # ── JSON output ───────────────────────────────────────────────────────────
    report_dict = result.to_dict()
    # Drop the raw full text from JSON output to keep it readable
    report_dict.pop("step3_text", None)
    report_dict.pop("clean_text", None)

    if args.json:
        print("\n" + "─" * 60)
        print("JSON REPORT")
        print("─" * 60)
        print(json.dumps(report_dict, indent=2, ensure_ascii=False, default=str))

    if args.output:
        out_path = args.output
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n[✓] JSON report saved to: {out_path}")

    # ── Exit code ─────────────────────────────────────────────────────────────
    # Non-zero exit code if file was rejected
    if result.status == "FILE_REJECTED":
        sys.exit(2)


if __name__ == "__main__":
    main()
