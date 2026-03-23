import fitz
import pdfplumber
import os
import base64
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def extract_text_with_groq_vision(page):
    """Use Groq vision model to extract text from scanned PDF page"""
    try:
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        base64_image = base64.b64encode(img_bytes).decode("utf-8")

        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "Extract ALL text from this medical report image. Return only the extracted text, nothing else."
                    }
                ]
            }],
            temperature=0
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"  ⚠️ Vision extraction failed: {e}")
        return ""

def parse_pdf(filepath: str) -> dict:
    result = {
        'text': '',
        'tables': [],
        'filename': os.path.basename(filepath)
    }

    doc = fitz.open(filepath)
    pages_text = []

    for page in doc:
        # Try normal text extraction first
        text = page.get_text()

        # If no text — use Groq vision
        if len(text.strip()) < 50:
            print(f"  📷 Page {page.number + 1} is scanned — using Groq Vision...")
            text = extract_text_with_groq_vision(page)
            print(f"  ✅ Vision extracted {len(text)} characters")

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