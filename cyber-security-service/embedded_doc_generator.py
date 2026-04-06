# TEST_3.py
import pikepdf
from pikepdf import Pdf

def make_embedded_pdf(path="embedded_document.pdf"):
    # نِشء PDF جديد
    pdf = Pdf.new()
    pdf.add_blank_page(page_size=(612, 792))

    pdf.docinfo["/Title"] = "Embedded File PDF"

    # ن嵒 ملف نصي صغير جوه الـ PDF كـ attachment
    data = b"Test embedded file content"
    filespec = pikepdf.AttachedFileSpec(pdf, data, mime_type="text/plain")
    pdf.attachments["test.txt"] = filespec

    pdf.save(path)
    pdf.close()
    print(f"[+] Created {path}")

if __name__ == "__main__":
    make_embedded_pdf()
