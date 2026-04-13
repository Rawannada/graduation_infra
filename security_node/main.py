import os
import sys
import json
from scanner.pipeline import run

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <file_path>")
        sys.exit(1)

    file_path = sys.argv[1]

    if not os.path.isfile(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)

    result = run(file_path)
    data = result.to_dict()

    print("\n=== Secure Document Scanner ===")
    print(f"File       : {data.get('file_path')}")
    print(f"Type       : {data.get('file_type')}")
    print(f"Status     : {data.get('status')}")
    print(f"Score      : {data.get('security_score', {}).get('score')}/100")
    print(f"Malware    : {data.get('security_score', {}).get('malware_risk')}")
    print(f"Injection  : {data.get('security_score', {}).get('prompt_injection_risk')}")
    print(f"DLP        : {data.get('security_score', {}).get('sensitive_data')}")
    print(f"Threat Intel: {data.get('security_score', {}).get('threat_indicators')}")
    print(f"Moderation : {data.get('security_score', {}).get('content_moderation')}")
    print(f"Summary    : {data.get('summary')}")
    print(f"Confidence : {data.get('summary_confidence')}")

    report_path = file_path + ".pipeline.report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nReport saved to: {report_path}")

if __name__ == "__main__":
    main()