import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.pdf_parser import parse_pdf
from ingestion.entity_extractor import extract_entities
from graph.graph_builder import build_graph_from_entities
from graph.neo4j_client import Neo4jClient
from rag.query_engine import GraphRAGEngine
from pyvis.network import Network
import streamlit.components.v1 as components
import tempfile

# ── Page Config ───────────────────────────────────────────
st.set_page_config(
    page_title="HealthThread",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0f0f1a; }
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
    }
    .metric-card {
        background: #1a1a2e;
        border: 1px solid #2d2d44;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }
    .answer-box {
        background: #0d3320;
        border-left: 4px solid #00c853;
        border-radius: 8px;
        padding: 16px;
        margin: 10px 0;
    }
    .warning-box {
        background: #3d1f00;
        border-left: 4px solid #ff6d00;
        border-radius: 8px;
        padding: 16px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ── Initialize ────────────────────────────────────────────
@st.cache_resource
def get_engine():
    return GraphRAGEngine()

engine = get_engine()

# ── Session State ─────────────────────────────────────────
if "question" not in st.session_state:
    st.session_state.question = ""
if "processed" not in st.session_state:
    st.session_state.processed = False

# ═══════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🧬 HealthThread")
    st.caption("Your Personal Health Knowledge Graph")
    st.divider()

    # Patient name
    patient_name = st.text_input(
        "👤 Your Name",
        placeholder="e.g. Avneesh Kumar Mishra"
    )

    st.divider()

    # Upload section
    st.markdown("### 📄 Upload Medical Report")
    uploaded_file = st.file_uploader(
        "Upload any medical PDF",
        type="pdf",
        help="Blood reports, urine analysis, prescriptions, discharge summaries"
    )

    if uploaded_file and patient_name:
        if st.button("⚡ Process Document", use_container_width=True, type="primary"):
            with st.spinner("🔍 Reading report with OCR..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(uploaded_file.read())
                    tmp_path = tmp.name

                parsed = parse_pdf(tmp_path)
                os.unlink(tmp_path)

            with st.spinner("🧠 Extracting medical entities..."):
                entities = extract_entities(parsed["text"])

            with st.spinner("🕸️ Building knowledge graph..."):
                build_graph_from_entities(entities, patient_name)

            st.session_state.processed = True
            st.success("✅ Report processed!")

            # Show summary of what was extracted
            st.markdown("**Extracted:**")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Lab Tests", len(entities.get("lab_values", [])))
                st.metric("Conditions", len(entities.get("conditions", [])))
            with col2:
                st.metric("Medications", len(entities.get("medications", [])))
                st.metric("Findings", len(entities.get("abnormal_findings", [])))

    elif uploaded_file and not patient_name:
        st.warning("⚠️ Enter your name first")

    st.divider()

    # Quick stats from graph
    if patient_name:
        st.markdown("### 📊 Your Health Stats")
        try:
            db = Neo4jClient()
            stats = db.run_query("""
                MATCH (p:Patient {name: $name})
                OPTIONAL MATCH (p)-[:HAS_REPORT]->(r:Report)
                OPTIONAL MATCH (p)-[:HAS_LAB_RESULT]->(l:LabTest)
                OPTIONAL MATCH (p)-[:HAS_CONDITION]->(c:Condition)
                RETURN
                    count(DISTINCT r) as reports,
                    count(DISTINCT l) as labs,
                    count(DISTINCT c) as conditions
            """, {"name": patient_name})
            db.close()

            if stats and stats[0]["reports"] > 0:
                s = stats[0]
                col1, col2, col3 = st.columns(3)
                col1.metric("📋 Reports", s["reports"])
                col2.metric("🔬 Labs", s["labs"])
                col3.metric("🩺 Conditions", s["conditions"])
            else:
                st.info("No data yet. Upload a report!")
        except:
            pass

# ═══════════════════════════════════════════════════════════
# MAIN AREA — TABS
# ═══════════════════════════════════════════════════════════
st.markdown("# 🧬 HealthThread")
st.caption("Ask anything about your health history — powered by GraphRAG")

if not patient_name:
    st.info("👈 Enter your name in the sidebar to get started")
    st.stop()

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "💬 Ask Questions",
    "📋 Health Summary",
    "🕸️ Knowledge Graph",
    "⚠️ Risk Check"
])

# ═══════════════════════════════════════════════════════════
# TAB 1 — ASK QUESTIONS
# ═══════════════════════════════════════════════════════════
with tab1:
    st.markdown("### Ask Anything About Your Health")

    # Example question buttons
    st.caption("Quick questions:")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🩺 My conditions"):
            st.session_state.question = "What conditions do I have?"
    with col2:
        if st.button("🔬 Abnormal labs"):
            st.session_state.question = "Which of my lab results are abnormal?"
    with col3:
        if st.button("👨‍⚕️ My doctor"):
            st.session_state.question = "Who was my doctor in 2025?"
    with col4:
        if st.button("🏥 My reports"):
            st.session_state.question = "What reports do I have?"

    # Question input
    question = st.text_input(
        "Or type your own question:",
        value=st.session_state.question,
        placeholder="e.g. What did my May 2025 report show?"
    )

    if st.button("🔍 Ask", use_container_width=True, type="primary"):
        if question:
            with st.spinner("Searching your health graph..."):
                result = engine.answer(question, patient_name)

            # Display answer
            st.markdown(f"""
            <div class="answer-box">
                <strong>💬 Answer:</strong><br><br>
                {result['answer']}
            </div>
            """, unsafe_allow_html=True)

            # Technical details
            with st.expander("🔬 Technical Details"):
                st.caption("Cypher query generated:")
                st.code(result["cypher"], language="cypher")
                st.caption("Raw data from graph:")
                st.json(result["data"])
        else:
            st.warning("Please type a question first")

# ═══════════════════════════════════════════════════════════
# TAB 2 — HEALTH SUMMARY
# ═══════════════════════════════════════════════════════════
with tab2:
    st.markdown("### Your Complete Health Summary")
    st.caption("AI-generated summary of your entire health history")

    if st.button("🧠 Generate My Health Summary", use_container_width=True, type="primary"):
        with st.spinner("Reading your entire health history..."):

            # Get all data from graph
            db = Neo4jClient()

            reports = db.run_query("""
                MATCH (p:Patient {name: $name})-[:HAS_REPORT]->(r:Report)
                RETURN r.type as type, r.date as date, r.hospital as hospital
                ORDER BY r.date
            """, {"name": patient_name})

            labs = db.run_query("""
                MATCH (p:Patient {name: $name})-[:HAS_LAB_RESULT]->(l:LabTest)
                WHERE l.status IN ['HIGH', 'LOW']
                RETURN l.name as test, l.value as value,
                       l.unit as unit, l.status as status, l.date as date
            """, {"name": patient_name})

            findings = db.run_query("""
                MATCH (p:Patient {name: $name})-[:HAS_FINDING]->(f:Finding)
                RETURN f.description as finding
            """, {"name": patient_name})

            conditions = db.run_query("""
                MATCH (p:Patient {name: $name})-[:HAS_CONDITION]->(c:Condition)
                RETURN c.name as condition
            """, {"name": patient_name})

            db.close()

        # Generate summary with Groq
        from groq import Groq
        import json
        groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        summary_prompt = f"""
        You are a helpful health assistant. Generate a clear, friendly health summary
        for {patient_name} based on their medical records.

        Reports: {json.dumps(reports)}
        Abnormal Lab Results: {json.dumps(labs)}
        Findings: {json.dumps(findings)}
        Conditions: {json.dumps(conditions)}

        Write a 3-4 paragraph summary covering:
        1. Overview of reports and when they were taken
        2. Key findings and what they mean in simple English
        3. What to watch out for or follow up on
        4. General advice

        Be warm, clear and non-alarming. End with reminder to consult a doctor.
        """

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.4
        )

        summary = response.choices[0].message.content

        st.markdown(f"""
        <div class="answer-box">
            {summary.replace(chr(10), '<br>')}
        </div>
        """, unsafe_allow_html=True)

        # Also show what to ask doctor
        st.markdown("### 📝 What to Ask Your Doctor")
        ask_prompt = f"""
        Based on these health findings: {json.dumps(findings + labs)}
        Generate 4-5 specific questions this patient should ask their doctor.
        Format as a numbered list. Be specific, not generic.
        """
        ask_response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": ask_prompt}],
            temperature=0.3
        )
        st.markdown(ask_response.choices[0].message.content)

# ═══════════════════════════════════════════════════════════
# TAB 3 — KNOWLEDGE GRAPH VISUALIZER
# ═══════════════════════════════════════════════════════════
with tab3:
    st.markdown("### Your Health Knowledge Graph")
    st.caption("Visual representation of your health data and connections")

    if st.button("🕸️ Show My Graph", use_container_width=True, type="primary"):
        db = Neo4jClient()
        results = db.run_query("""
            MATCH (p:Patient {name: $name})-[r]->(n)
            RETURN p, type(r) as rel, n, labels(n) as node_type
        """, {"name": patient_name})
        db.close()

        if results:
            net = Network(
                height="550px",
                width="100%",
                bgcolor="#0f0f1a",
                font_color="white"
            )
            net.set_options("""
            {
                "nodes": {"borderWidth": 2, "shadow": true},
                "edges": {"shadow": true, "smooth": {"type": "continuous"}},
                "physics": {"stabilization": {"iterations": 100}}
            }
            """)

            colors = {
                "Patient":   "#FF6B6B",
                "Report":    "#4ECDC4",
                "Doctor":    "#45B7D1",
                "LabTest":   "#96CEB4",
                "Condition": "#FFEAA7",
                "Hospital":  "#DDA0DD",
                "Finding":   "#FF8C69",
                "Symptom":   "#98FB98",
                "Medication": "#87CEEB",
            }

            added_nodes = set()

            for row in results:
                # Patient node
                p = row['p']
                p_name = p.get('name', 'Patient')
                if p_name not in added_nodes:
                    net.add_node(
                        p_name, label=p_name,
                        color=colors["Patient"],
                        size=35, title="Patient",
                        shape="dot"
                    )
                    added_nodes.add(p_name)

                # Target node
                n = row['n']
                node_type = row['node_type'][0] if row['node_type'] else "Node"
                n_name = (n.get('name') or n.get('type') or
                         n.get('description', 'Unknown'))
                n_name = str(n_name)[:25]

                if n_name and n_name not in added_nodes:
                    # Add extra info as tooltip
                    tooltip = node_type
                    if node_type == "LabTest":
                        tooltip = f"{node_type}: {n.get('value')} {n.get('unit')} ({n.get('status')})"
                    elif node_type == "Report":
                        tooltip = f"{node_type}: {n.get('date')}"

                    net.add_node(
                        n_name, label=n_name,
                        color=colors.get(node_type, "#ffffff"),
                        size=20, title=tooltip,
                        shape="dot"
                    )
                    added_nodes.add(n_name)

                if n_name:
                    net.add_edge(
                        p_name, n_name,
                        label=row['rel'],
                        color="#444466",
                        width=1.5
                    )

            # Save and render
            graph_path = "health_graph.html"
            net.save_graph(graph_path)
            with open(graph_path, "r", encoding="utf-8") as f:
                html = f.read()
            components.html(html, height=570)

            # Legend
            st.markdown("**Legend:**")
            cols = st.columns(len(colors))
            for i, (node_type, color) in enumerate(colors.items()):
                cols[i].markdown(
                    f"<span style='color:{color}'>⬤</span> {node_type}",
                    unsafe_allow_html=True
                )
        else:
            st.info("No graph data found. Upload and process a report first!")

# ═══════════════════════════════════════════════════════════
# TAB 4 — RISK CHECK
# ═══════════════════════════════════════════════════════════
with tab4:
    st.markdown("### ⚠️ Health Risk Check")
    st.caption("Scans your health graph for potential concerns")

    if st.button("🔍 Run Risk Check", use_container_width=True, type="primary"):
        db = Neo4jClient()

        # Get abnormal labs
        abnormal = db.run_query("""
            MATCH (p:Patient {name: $name})-[:HAS_LAB_RESULT]->(l:LabTest)
            WHERE l.status IN ['HIGH', 'LOW']
            RETURN l.name as test, l.value as value,
                   l.unit as unit, l.status as status, l.date as date
        """, {"name": patient_name})

        # Get findings
        findings = db.run_query("""
            MATCH (p:Patient {name: $name})-[:HAS_FINDING]->(f:Finding)
            RETURN f.description as finding
        """, {"name": patient_name})

        # Get medications
        meds = db.run_query("""
            MATCH (p:Patient {name: $name})-[:TAKES_MEDICATION]->(m:Medication)
            RETURN m.name as medication
        """, {"name": patient_name})

        db.close()

        # Show abnormal labs
        if abnormal:
            st.markdown("#### 🔬 Abnormal Lab Results")
            for lab in abnormal:
                color = "🔴" if lab['status'] == 'HIGH' else "🔵"
                st.markdown(f"""
                <div class="warning-box">
                    {color} <strong>{lab['test']}</strong>:
                    {lab['value']} {lab['unit']} —
                    <strong>{lab['status']}</strong>
                    (from {lab['date']})
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ All lab results are within normal range!")

        # Show findings
        if findings:
            st.markdown("#### ⚠️ Medical Findings")
            for f in findings:
                st.warning(f"⚠️ {f['finding']}")

        # Drug conflict check
        if meds and len(meds) > 1:
            st.markdown("#### 💊 Drug Interaction Check")
            import requests
            med_list = [m['medication'] for m in meds]
            conflicts_found = False

            for i in range(len(med_list)):
                for j in range(i+1, len(med_list)):
                    try:
                        resp = requests.get(
                            "https://api.fda.gov/drug/event.json",
                            params={
                                "search": f'patient.drug.medicinalproduct:{med_list[i]} AND patient.drug.medicinalproduct:{med_list[j]}',
                                "count": "patient.reaction.reactionmeddrapt.exact",
                                "limit": 3
                            },
                            timeout=5
                        )
                        data = resp.json()
                        if "results" in data:
                            reactions = [r['term'] for r in data['results'][:3]]
                            st.markdown(f"""
                            <div class="warning-box">
                                ⚠️ <strong>{med_list[i]}</strong> +
                                <strong>{med_list[j]}</strong>
                                may cause: {', '.join(reactions)}
                            </div>
                            """, unsafe_allow_html=True)
                            conflicts_found = True
                    except:
                        pass

            if not conflicts_found:
                st.success("✅ No known drug interactions found!")
        elif len(meds) <= 1:
            st.info("ℹ️ Need at least 2 medications to check interactions.")

        if not abnormal and not findings:
            st.balloons()
            st.success("🎉 Everything looks good! No major concerns found.")