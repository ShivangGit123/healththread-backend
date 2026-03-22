from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys, os, tempfile
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.pdf_parser import parse_pdf
from ingestion.entity_extractor import extract_entities
from graph.graph_builder import build_graph_from_entities
from graph.neo4j_client import Neo4jClient
from rag.query_engine import GraphRAGEngine
from groq import Groq
import json

app = FastAPI(title="HealthThread API")

# ── CORS — allows Vercel frontend to talk to this API ────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = GraphRAGEngine()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── Health check ─────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "HealthThread API running"}

# ── Upload & Process PDF ─────────────────────────────────
@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    patient_name: str = Form(...)
):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    parsed = parse_pdf(tmp_path)
    os.unlink(tmp_path)

    entities = extract_entities(parsed["text"])
    build_graph_from_entities(entities, patient_name)

    return {
        "status": "success",
        "report_type": entities.get("report_type", "Unknown"),
        "date": entities.get("dates", ["unknown"])[0],
        "summary": {
            "labs": len(entities.get("lab_values", [])),
            "conditions": len(entities.get("conditions", [])),
            "medications": len(entities.get("medications", [])),
            "findings": len(entities.get("abnormal_findings", []))
        },
        "entities": entities
    }

# ── Ask Question ─────────────────────────────────────────
class QuestionRequest(BaseModel):
    question: str
    patient_name: str

@app.post("/ask")
def ask_question(req: QuestionRequest):
    result = engine.answer(req.question, req.patient_name)
    return result

# ── Health Summary ───────────────────────────────────────
@app.get("/summary/{patient_name}")
def get_summary(patient_name: str):
    db = Neo4jClient()

    reports = db.run_query("""
        MATCH (p:Patient {name: $name})-[:HAS_REPORT]->(r:Report)
        RETURN r.type as type, r.date as date, r.hospital as hospital
    """, {"name": patient_name})

    labs = db.run_query("""
        MATCH (p:Patient {name: $name})-[:HAS_LAB_RESULT]->(l:LabTest)
        WHERE l.status IN ['HIGH', 'LOW']
        RETURN l.name as test, l.value as value,
               l.unit as unit, l.status as status
    """, {"name": patient_name})

    findings = db.run_query("""
        MATCH (p:Patient {name: $name})-[:HAS_FINDING]->(f:Finding)
        RETURN f.description as finding
    """, {"name": patient_name})

    db.close()

    summary_prompt = f"""
    Generate a clear friendly health summary for {patient_name}.
    Reports: {json.dumps(reports)}
    Abnormal Labs: {json.dumps(labs)}
    Findings: {json.dumps(findings)}
    Write 3 paragraphs: overview, key findings, what to watch for.
    End with reminder to consult a doctor.
    """

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": summary_prompt}],
        temperature=0.4
    )

    ask_prompt = f"""
    Based on: {json.dumps(findings + labs)}
    Generate 4 specific questions this patient should ask their doctor.
    Numbered list only.
    """

    ask_response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": ask_prompt}],
        temperature=0.3
    )

    return {
        "summary": response.choices[0].message.content,
        "doctor_questions": ask_response.choices[0].message.content,
        "reports": reports,
        "abnormal_labs": labs,
        "findings": findings
    }

# ── Stats ────────────────────────────────────────────────
@app.get("/stats/{patient_name}")
def get_stats(patient_name: str):
    db = Neo4jClient()
    stats = db.run_query("""
        MATCH (p:Patient {name: $name})
        OPTIONAL MATCH (p)-[:HAS_REPORT]->(r:Report)
        OPTIONAL MATCH (p)-[:HAS_LAB_RESULT]->(l:LabTest)
        OPTIONAL MATCH (p)-[:HAS_CONDITION]->(c:Condition)
        OPTIONAL MATCH (p)-[:TAKES_MEDICATION]->(m:Medication)
        RETURN
            count(DISTINCT r) as reports,
            count(DISTINCT l) as labs,
            count(DISTINCT c) as conditions,
            count(DISTINCT m) as medications
    """, {"name": patient_name})
    db.close()
    return stats[0] if stats else {}

# ── Risk Check ───────────────────────────────────────────
@app.get("/risks/{patient_name}")
def get_risks(patient_name: str):
    db = Neo4jClient()

    abnormal = db.run_query("""
        MATCH (p:Patient {name: $name})-[:HAS_LAB_RESULT]->(l:LabTest)
        WHERE l.status IN ['HIGH', 'LOW']
        RETURN l.name as test, l.value as value,
               l.unit as unit, l.status as status, l.date as date
    """, {"name": patient_name})

    findings = db.run_query("""
        MATCH (p:Patient {name: $name})-[:HAS_FINDING]->(f:Finding)
        RETURN f.description as finding
    """, {"name": patient_name})

    meds = db.run_query("""
        MATCH (p:Patient {name: $name})-[:TAKES_MEDICATION]->(m:Medication)
        RETURN m.name as medication
    """, {"name": patient_name})

    db.close()
    return {
        "abnormal_labs": abnormal,
        "findings": findings,
        "medications": meds
    }
@app.get("/graph/{patient_name}")
def get_graph(patient_name: str):
    db = Neo4jClient()
    results = db.run_query("""
        MATCH (p:Patient {name: $name})-[r]->(n)
        RETURN p, type(r) as rel, n, labels(n) as node_type
    """, {"name": patient_name})
    db.close()

    nodes = {}
    edges = []
    node_counter = [0]

    def add_node(name, node_type):
        if name not in nodes:
            nodes[name] = {
                "id": node_counter[0],
                "label": name[:20],
                "type": node_type
            }
            node_counter[0] += 1
        return nodes[name]["id"]

    for row in results:
        p = row['p']
        p_name = p.get('name', 'Patient')
        p_id = add_node(p_name, "Patient")

        n = row['n']
        node_type = row['node_type'][0] if row['node_type'] else "Node"
        n_name = str(
            n.get('name') or n.get('type') or
            n.get('description', 'Unknown')
        )[:25]

        if n_name:
            n_id = add_node(n_name, node_type)
            edges.append({
                "from": p_id,
                "to": n_id,
                "label": row['rel']
            })

    return {
        "nodes": list(nodes.values()),
        "edges": edges
    }    