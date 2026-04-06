import pikepdf
from pikepdf import Pdf, Name

def make_high_risk_pdf(path="high_risk_document.pdf"):
    pdf = Pdf.new()
    page = pdf.add_blank_page(page_size=(612, 792))

    # Metadata عادية
    pdf.docinfo[Name("/Title")] = "High Risk PDF"
    pdf.docinfo[Name("/Author")] = "Lab"
    pdf.docinfo[Name("/Subject")] = "Fake JS markers for scanner test"

    # نكتب في محتوى الصفحة نص فيه الكلمات اللي الـ scanner بيدوّر عليها
    # الكود بتاعك بيستخدم: if key in page_str على:
    # "/AA", "/JS", "/JavaScript", "/OpenAction", "/Launch", "/URI", "/SubmitForm"
    stream_bytes = b"""
        q
        BT
        /F1 12 Tf
        100 700 Td
        (This page simulates /OpenAction and /JavaScript and /JS and /AA and /Launch and /URI and /SubmitForm) Tj
        ET
        Q
    """
    page.Contents = pdf.make_stream(stream_bytes)

    pdf.save(path)
    pdf.close()
    print(f"[+] Created {path}")

if __name__ == "__main__":
    make_high_risk_pdf()

