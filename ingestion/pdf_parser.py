import fitz
import pdfplumber
import os
from PIL import Image
import pytesseract
import io

# Windows Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

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

        # If no text — it's a scanned image, use OCR
        if len(text.strip()) < 50:
            print(f"  📷 Page {page.number + 1} is scanned — running OCR...")
            pix = page.get_pixmap(dpi=300)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            text = pytesseract.image_to_string(img)
            print(f"  ✅ OCR done — {len(text)} characters extracted")

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