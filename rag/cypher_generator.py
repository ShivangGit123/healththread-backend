import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

CYPHER_PROMPT = """
You are a Neo4j Cypher expert. Convert the user health question into a Cypher query.

Graph Schema:
- (Patient {name, age, gender})
- (Report {id, type, date, hospital})
- (Condition {name})
- (Medication {name})
- (LabTest {name, value, unit, status, reference_range, date})
- (Symptom {name})
- (Doctor {name})
- (Hospital {name})
- (Finding {description})

Relationships:
- (Patient)-[:HAS_REPORT]->(Report)
- (Patient)-[:HAS_CONDITION]->(Condition)
- (Patient)-[:TAKES_MEDICATION]->(Medication)
- (Patient)-[:HAS_LAB_RESULT]->(LabTest)
- (Patient)-[:HAS_SYMPTOM]->(Symptom)
- (Patient)-[:CONSULTED]->(Doctor)
- (Report)-[:ATTENDED_BY]->(Doctor)
- (Report)-[:CONTAINS_LAB]->(LabTest)
- (Report)-[:PERFORMED_AT]->(Hospital)
- (Report)-[:MENTIONS_CONDITION]->(Condition)
- (Report)-[:HAS_FINDING]->(Finding)
- (Patient)-[:HAS_FINDING]->(Finding)

Rules:
- ALWAYS start with: MATCH (p:Patient {name: $patient_name})
- For medications: use (p)-[:TAKES_MEDICATION]->(m:Medication)
- For lab results: use (p)-[:HAS_LAB_RESULT]->(l:LabTest)
- For abnormal labs: WHERE l.status IN ['HIGH', 'LOW']
- For findings: use (p)-[:HAS_FINDING]->(f:Finding)
- For conditions: use (p)-[:HAS_CONDITION]->(c:Condition)
- For date questions: use (p)-[:HAS_REPORT]->(r:Report) WHERE r.date CONTAINS '2025'
- For doctor questions: use (p)-[:HAS_REPORT]->(r:Report)-[:ATTENDED_BY]->(d:Doctor)
- Use toLower() for case-insensitive search
- Return ONLY the Cypher query, nothing else, no backticks, no explanation

Examples:
Question: What conditions do I have?
Cypher: MATCH (p:Patient {name: $patient_name})-[:HAS_CONDITION]->(c:Condition) RETURN c.name as condition

Question: Which medications am I taking?
Cypher: MATCH (p:Patient {name: $patient_name})-[:TAKES_MEDICATION]->(m:Medication) RETURN m.name as medication

Question: Which lab results are abnormal?
Cypher: MATCH (p:Patient {name: $patient_name})-[:HAS_LAB_RESULT]->(l:LabTest) WHERE l.status IN ['HIGH', 'LOW'] RETURN l.name as test, l.value as value, l.unit as unit, l.status as status

Question: What are my abnormal findings?
Cypher: MATCH (p:Patient {name: $patient_name})-[:HAS_FINDING]->(f:Finding) RETURN f.description as finding

Question: What are all my lab results?
Cypher: MATCH (p:Patient {name: $patient_name})-[:HAS_LAB_RESULT]->(l:LabTest) RETURN l.name as test, l.value as value, l.unit as unit, l.status as status

Question: Who was my doctor in 2025?
Cypher: MATCH (p:Patient {name: $patient_name})-[:HAS_REPORT]->(r:Report)-[:ATTENDED_BY]->(d:Doctor) WHERE r.date CONTAINS '2025' RETURN d.name as doctor, r.date as date, r.type as report_type

Question: What reports do I have?
Cypher: MATCH (p:Patient {name: $patient_name})-[:HAS_REPORT]->(r:Report) RETURN r.type as report, r.date as date, r.hospital as hospital

Question: {question}
Cypher:"""


def generate_cypher(question: str) -> str:
    prompt = CYPHER_PROMPT.replace("{question}", question)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    cypher = response.choices[0].message.content.strip()
    cypher = cypher.replace("```cypher", "").replace("```", "").strip()
    return cypher