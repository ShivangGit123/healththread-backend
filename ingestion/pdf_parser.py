import fitz
import pdfplumber
import os
import platform

def parse_pdf(filepath: str) -> dict:
    result = {
        'text': '',
        'tables': [],
        'filename': os.path.basename(filepath)
    }

    doc = fitz.open(filepath)
    pages_text = []

    for page in doc:
        text = page.get_text()

        # If no text — try OCR only if Tesseract available
        if len(text.strip()) < 50:
            try:
                from PIL import Image
                import pytesseract
                import io

                # Set path only on Windows
                if platform.system() == "Windows":
                    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

                print(f"  📷 Page {page.number + 1} is scanned — running OCR...")
                pix = page.get_pixmap(dpi=300)
                img_bytes = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_bytes))
                text = pytesseract.image_to_string(img)
                print(f"  ✅ OCR done — {len(text)} characters")

            except Exception as e:
                print(f"  ⚠️ OCR failed: {e} — using pymupdf text extraction")
                # Fallback — try harder with pymupdf
                text = page.get_text("blocks")
                if isinstance(text, list):
                    text = " ".join([b[4] for b in text if len(b) > 4])

        pages_text.append(text)

    result['text'] = '\n'.join(pages_text)
    doc.close()

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if table and any(any(cell for cell in row) for row in table):
                    result['tables'].append(table)

    return result