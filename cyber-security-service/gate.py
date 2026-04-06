import pikepdf
import json
import sys
from hashlib import sha256
from datetime import datetime
from typing import Optional, List, Dict, Any
import io

SUSPICIOUS_KEYS = [
    "/AA", "/JS", "/JavaScript", "/OpenAction",
    "/Launch", "/URI", "/SubmitForm",
    "/AcroForm", "/RichMedia", "/XFA", "/EmbeddedFile"
]

# أوزان المخاطر (معلّقة للتوثيق)
RISK_WEIGHTS = {
    "javascript": 7,
    "embedded_file": 4,
    "open_launch": 5,
    "many_links": 2,
    "single_page": 1,
    "objstm": 2,
    "rich_media": 5,
    "xfa": 4,
    "per_suspicious_obj": 1,   # حد أقصى 6
}

def scan_embedded_pdf(content: bytes, depth: int = 0, max_depth: int = 3) -> Optional[Dict]:
    """فحص ملف PDF مضمن بشكل متكرر (إذا كان المحتوى يبدو كـ PDF)."""
    if depth >= max_depth:
        return {"error": "Max recursion depth reached"}
    if not content.startswith(b"%PDF"):
        return None
    try:
        with io.BytesIO(content) as f:
            pdf = pikepdf.open(f)
            # تقرير مبسط (يمكن توسيعه)
            return {
                "javascript_found": any(check for check in [scan_all_objects(pdf)])  # تبسيط
            }
    except Exception as e:
        return {"error": str(e)}

def scan_all_objects(pdf: pikepdf.Pdf) -> List[Dict]:
    """
    يتجول في جميع كائنات PDF ويبحث عن المفاتيح المشبوهة في القواميس.
    يُعيد قائمة بالنتائج (كل نتيجة تحتوي على رقم الكائن والمفتاح والصفحة إن أمكن).
    """
    results = []
    seen = set()  # لتجنب التكرار (بعض الكائنات قد تظهر أكثر من مرة)

    def walk(obj, path=""):
        if id(obj) in seen:
            return
        seen.add(id(obj))

        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in SUSPICIOUS_KEYS:
                    results.append({
                        "type": key,
                        "object": getattr(obj, "objgen", (None,))[0],  # رقم الكائن إن وجد
                        "path": path,
                    })
                walk(value, path + f"/{key}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                walk(item, path + f"[{i}]")
        elif isinstance(obj, pikepdf.Stream):
            # التحقق من نوع التدفق (مثلاً /ObjStm)
            if obj.get("/Type") == "/ObjStm":
                results.append({
                    "type": "ObjStmPresent",
                    "object": getattr(obj, "objgen", (None,))[0],
                })
            walk(obj.as_dict(), path)

    # ابدأ من جذر المستند (Root)
    walk(pdf.Root, "/Root")
    # أيضاً تجول في جميع الكائنات غير المباشرة
    for obj in pdf.objects:
        walk(obj, "")
    return results

def extract_urls_from_annotations(pdf: pikepdf.Pdf) -> List[str]:
    """استخراج عناوين URL من تعليقات الروابط في كل الصفحات."""
    urls = []
    for page in pdf.pages:
        if "/Annots" in page:
            annots = page["/Annots"]
            if isinstance(annots, list):
                for annot in annots:
                    if isinstance(annot, dict):
                        # روابط من النوع Link مع إجراء /URI
                        if annot.get("/Subtype") == "/Link" and "/A" in annot:
                            action = annot["/A"]
                            if action.get("/S") == "/URI" and "/URI" in action:
                                uri = action["/URI"]
                                if isinstance(uri, str):
                                    urls.append(uri)
    return urls

def extract_embedded_files(pdf: pikepdf.Pdf, debug=False) -> Dict[str, Any]:
    """
    استخراج وتحليل الملفات المضمنة.
    تُعيد قاموساً يحتوي على:
        - count: عدد الملفات
        - files: قائمة بتفاصيل كل ملف (اسم، حجم، هاش، نوع، وتقرير فرعي إذا كان PDF)
    """
    result = {"count": 0, "files": []}
    attachments = {}
    try:
        attachments = pdf.attachments  # قاموس {الاسم: محتوى bytes}
    except Exception as e:
        if debug:
            print(f"[Debug] attachments failed: {e}")
        # محاولة بديلة عبر /EmbeddedFiles في الجذر
        if "/EmbeddedFiles" in pdf.Root:
            try:
                names_tree = pdf.Root["/EmbeddedFiles"]
                # هذا قد يكون أكثر تعقيداً، نتركه بسيطاً الآن
                pass
            except:
                pass

    for name, content in attachments.items():
        info = {
            "name": name,
            "size": len(content),
            "hash": sha256(content).hexdigest(),
            "magic": content[:8].hex(),
        }
        # تخمين النوع: PDF?
        if content.startswith(b"%PDF"):
            info["type"] = "PDF"
            # فحص متكرر
            sub_report = scan_embedded_pdf(content, depth=1)
            if sub_report:
                info["nested_scan"] = sub_report
        elif content.startswith(b"MZ"):
            info["type"] = "PE (executable)"
        else:
            info["type"] = "unknown"
        result["files"].append(info)
    result["count"] = len(result["files"])
    return result

def scan_pdf(file_path: str, file_id: Optional[str] = None, debug: bool = False) -> dict:
    """
    يقوم بتحليل أمني متقدم لملف PDF.
    
    المعاملات:
        file_path (str): مسار الملف.
        file_id (Optional[str]): معرف اختياري من النظام الخارجي.
        debug (bool): إذا كان True، تتم طباعة تفاصيل الأخطاء.

    العائد:
        dict: تقرير مفصل يحتوي على:
            - file_id, file_name, file_hash, created_at
            - javascript_found (bool)
            - embedded_files (int) و embedded_files_details (list)
            - suspicious_objects (int) و triggers (list)
            - metadata, num_pages, encrypted, objstm_count
            - risk_level (1-3), risk_label (Low/Medium/High)
            - profile (benign_like, dropper_like, phishing_like, ...)
            - security_block (bool), security_decision (accept/review/reject)
            - extracted_urls (list)
            - errors (list)
            - flags, explanation, إلخ.
    """
    report = {
        "file_id": file_id,
        "file_name": file_path,
        "file_hash": None,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "javascript_found": False,
        "embedded_files": 0,
        "embedded_files_details": [],
        "suspicious_objects": 0,
        "triggers": [],
        "metadata": {},
        "num_pages": None,
        "encrypted": None,
        "objstm_count": 0,
        "risk_level": 1,
        "risk_label": "Low",
        "profile": "unknown",
        "engine_version": "pdf-cyber-scanner-v3-improved",
        "security_block": False,
        "security_decision": "accept",
        "extracted_urls": [],
        "errors": [],
        "debug": debug,
    }

    print(f"\n[+] Scanning file: {file_path}\n")

    try:
        # حساب هاش الملف
        with open(file_path, "rb") as f:
            report["file_hash"] = sha256(f.read()).hexdigest()

        pdf = pikepdf.open(file_path)

        # ========= مؤشرات عامة =========
        try:
            report["num_pages"] = len(pdf.pages)
            report["encrypted"] = bool(pdf.is_encrypted)
            if report["num_pages"] == 1:
                report["triggers"].append({"type": "SinglePageDocument", "page": 0})
                report["suspicious_objects"] += 1
        except Exception as e:
            report["errors"].append(f"Pages/encryption check: {e}")
            if debug:
                print(f"[Debug] Error getting pages/encryption: {e}")

        # الميتاداتا
        report["metadata"] = {k: str(v) for k, v in pdf.docinfo.items()}

        # ========= مسح جميع الكائنات بحثاً عن المفاتيح المشبوهة =========
        suspicious_finds = scan_all_objects(pdf)
        for find in suspicious_finds:
            t = find["type"]
            report["triggers"].append(find)
            report["suspicious_objects"] += 1
            if t in ["/JS", "/JavaScript"]:
                report["javascript_found"] = True

        # عد Object Streams
        objstm_count = sum(1 for t in report["triggers"] if t["type"] == "ObjStmPresent")
        report["objstm_count"] = objstm_count

        # ========= الملفات المضمنة =========
        emb = extract_embedded_files(pdf, debug=debug)
        report["embedded_files"] = emb["count"]
        report["embedded_files_details"] = emb["files"]
        if emb["count"] > 0:
            report["triggers"].append({"type": "EmbeddedFiles", "count": emb["count"]})

        # ========= استخراج الروابط =========
        report["extracted_urls"] = extract_urls_from_annotations(pdf)

        # ========= التحقق من وجود /OpenAction و /Launch في الكتالوج =========
        root = pdf.Root
        if "/OpenAction" in root:
            report["triggers"].append({"type": "/OpenAction", "object": "Root"})
            report["suspicious_objects"] += 1
        if "/Launch" in root:
            report["triggers"].append({"type": "/Launch", "object": "Root"})
            report["suspicious_objects"] += 1

        # ========= تصنيف الملف (Profile) =========
        js_triggers = [t for t in report["triggers"] if t["type"] in ["/JS", "/JavaScript"]]
        open_launch = [t for t in report["triggers"] if t["type"] in ["/OpenAction", "/Launch"]]
        uri_triggers = [t for t in report["triggers"] if t["type"] == "/URI"]
        submit_triggers = [t for t in report["triggers"] if t["type"] == "/SubmitForm"]
        acro_triggers = [t for t in report["triggers"] if t["type"] == "/AcroForm"]
        embedded_triggers = [t for t in report["triggers"] if t["type"] == "EmbeddedFiles"]

        if js_triggers and (embedded_triggers or open_launch):
            profile = "dropper_like"
        elif len(uri_triggers) >= 5 and (submit_triggers or acro_triggers):
            profile = "phishing_like"
        elif submit_triggers or acro_triggers:
            profile = "form_heavy"
        elif embedded_triggers:
            profile = "attachment_heavy"
        else:
            profile = "benign_like"
        report["profile"] = profile

        # ========= إضافة علامة ManyExternalLinks إذا كان هناك روابط كثيرة =========
        uri_only = [t for t in report["triggers"] if t["type"] == "/URI"]
        if len(uri_only) > 5:
            report["triggers"].append({"type": "ManyExternalLinks", "count": len(uri_only)})
            report["suspicious_objects"] += 1

        # ========= حساب المخاطر (Risk Score) =========
        score = 0
        if report["javascript_found"]:
            score += RISK_WEIGHTS["javascript"]
        if report["embedded_files"] > 0:
            score += RISK_WEIGHTS["embedded_file"]
        score += min(report["suspicious_objects"], 6)  # حد أقصى 6 من الأوزان الصغيرة

        has_open_launch = any(t["type"] in ["/OpenAction", "/Launch"] for t in report["triggers"])
        if has_open_launch:
            score += RISK_WEIGHTS["open_launch"]

        has_many_links = any(t["type"] == "ManyExternalLinks" for t in report["triggers"])
        if has_many_links:
            score += RISK_WEIGHTS["many_links"]

        if any(t["type"] == "SinglePageDocument" for t in report["triggers"]):
            score += RISK_WEIGHTS["single_page"]

        if any(t["type"] == "ObjStmPresent" for t in report["triggers"]):
            score += RISK_WEIGHTS["objstm"]

        if any(t["type"] == "/RichMedia" for t in report["triggers"]):
            score += RISK_WEIGHTS["rich_media"]

        if any(t["type"] == "/XFA" for t in report["triggers"]):
            score += RISK_WEIGHTS["xfa"]

        # تحديد مستوى الخطورة
        if score >= 10:
            report["risk_level"] = 3
            report["risk_label"] = "High"
        elif score >= 4:
            report["risk_level"] = 2
            report["risk_label"] = "Medium"
        else:
            report["risk_level"] = 1
            report["risk_label"] = "Low"

        # ========= قرار أمني =========
        if report["risk_level"] == 3:
            report["security_block"] = True
            report["security_decision"] = "reject"
        elif report["risk_level"] == 2:
            report["security_block"] = False
            report["security_decision"] = "review"
        else:
            report["security_block"] = False
            report["security_decision"] = "accept"

        # ========= إحصائيات =========
        trigger_stats = {}
        for t in report["triggers"]:
            t_type = t["type"]
            trigger_stats[t_type] = trigger_stats.get(t_type, 0) + 1
        report["trigger_stats"] = trigger_stats
        report["total_triggers"] = len(report["triggers"])

        # ========= Flags =========
        report["flags"] = {
            "has_javascript": report["javascript_found"],
            "has_embedded_files": report["embedded_files"] > 0,
            "has_forms": any(t["type"] in ["/AcroForm", "/SubmitForm"] for t in report["triggers"]),
            "has_external_links": any(t["type"] == "/URI" for t in report["triggers"]),
            "is_single_page": report["num_pages"] == 1,
            "has_objstm": report["objstm_count"] > 0
        }

        # ========= Explanation =========
        explanation_parts = []
        if report["javascript_found"]:
            explanation_parts.append("JavaScript code detected inside the PDF.")
        if report["embedded_files"] > 0:
            explanation_parts.append(f"{report['embedded_files']} embedded file(s) detected.")
        if has_open_launch:
            explanation_parts.append("Auto-open actions (/OpenAction or /Launch) present.")
        if has_many_links:
            explanation_parts.append("High number of external links (possible phishing behavior).")
        if report["encrypted"]:
            explanation_parts.append("Document is encrypted.")
        if report["objstm_count"] > 0:
            explanation_parts.append("Object streams (/ObjStm) found, which may indicate obfuscation.")
        if any(t["type"] == "/RichMedia" for t in report["triggers"]):
            explanation_parts.append("RichMedia annotations (Flash) found, could be malicious.")
        if any(t["type"] == "/XFA" for t in report["triggers"]):
            explanation_parts.append("XFA forms found, may contain dynamic content.")
        if not explanation_parts:
            explanation = "No strong malicious indicators detected. Document looks benign-like."
        else:
            explanation = " ".join(explanation_parts)
        report["explanation"] = explanation

        # حفظ التقرير كـ JSON
        report_file = file_path + ".report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=4)

        # طباعة التقرير المختصر
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
        print(f"Risk Level        : {report['risk_label']} ({report['risk_level']})")
        print(f"Profile           : {report['profile']}")
        print(f"Security Decision : {report['security_decision']}")
        print(f"Extracted URLs    : {report['extracted_urls']}")
        print(f"Explanation       : {report.get('explanation')}")
        print("==============================\n")

        pdf.close()
        return report

    except Exception as e:
        error_msg = f"[!] Error opening PDF: {e}"
        print(error_msg)
        report["errors"].append(error_msg)
        return report

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gate.py <pdf_file_path> [file_id] [--debug]")
        sys.exit(1)

    file_path = sys.argv[1]
    file_id = sys.argv[2] if len(sys.argv) >= 3 and not sys.argv[2].startswith("--") else None
    debug = "--debug" in sys.argv

    scan_pdf(file_path, file_id=file_id, debug=debug)