import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

EXTRACTION_PROMPT = """
You are an expert medical document analyzer.
Analyze ANY type of medical report and extract all information.

This could be any type of report:
- Blood test / CBC / Complete Blood Count
- Urine analysis / Urinalysis
- Lipid profile
- Liver function test
- Kidney function test
- Thyroid profile
- Diabetes report
- Discharge summary
- Prescription
- Any other diagnostic report

Return ONLY a valid JSON object in this exact format, nothing else:
{
  "patient_name": "Full name from report",
  "patient_age": 0,
  "patient_gender": "male/female/unknown",
  "doctor": "Doctor name if present",
  "hospital": "Hospital or lab name",
  "report_type": "What type of report this is",
  "dates": ["dates found in report"],
  "conditions": ["any diagnosis or conditions mentioned"],
  "medications": ["any medicines prescribed"],
  "symptoms": ["any symptoms mentioned"],
  "lab_values": [
    {
      "name": "test name",
      "value": 0.0,
      "unit": "unit of measurement",
      "reference_range": "normal range as written in report",
      "status": "HIGH or LOW or NORMAL or NOT DETECTED"
    }
  ],
  "abnormal_findings": ["list any values outside normal range in plain English"],
  "doctor_notes": "any remarks or notes from doctor"
}

Important Rules:
- Extract EVERY test result you find
- For NOT DETECTED results: set value as 0, status as NOT DETECTED
- For numeric results: compare to reference range and set HIGH/LOW/NORMAL
- Always extract patient name, age, gender from report header
- Always extract hospital/lab name
- Fill abnormal_findings with simple English explanations
- If a field is not found use empty string or empty list
- Return ONLY the JSON object, absolutely nothing else, no markdown, no backticks

Medical Document Text:
"""


def extract_entities(text: str) -> dict:
    trimmed_text = text[:4000] if len(text) > 4000 else text

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": EXTRACTION_PROMPT + trimmed_text
        }],
        temperature=0
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print("⚠️ JSON parsing failed. Raw response:")
        print(raw)
        return {
            "conditions": [], "medications": [], "lab_values": [],
            "symptoms": [], "dates": [], "doctor": "", "hospital": "",
            "report_type": "unknown", "abnormal_findings": [],
            "patient_name": "", "patient_age": 0, "patient_gender": "",
            "doctor_notes": ""
        }