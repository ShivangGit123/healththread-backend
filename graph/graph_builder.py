from graph.neo4j_client import Neo4jClient
import uuid

def build_graph_from_entities(entities: dict, patient_name: str):
    db = Neo4jClient()

    db.run_query("""
        MERGE (p:Patient {name: $name})
        SET p.age = $age, p.gender = $gender
    """, {
        "name": patient_name,
        "age": entities.get("patient_age", 0),
        "gender": entities.get("patient_gender", "unknown")
    })
    print(f"✅ Patient node created: {patient_name}")

    dates = entities.get("dates", ["unknown"])
    report_date = dates[0] if dates else "unknown"
    report_type = entities.get("report_type", "Unknown Report")
    report_id = str(uuid.uuid4())[:8]

    db.run_query("""
        CREATE (r:Report {
            id: $id,
            type: $type,
            date: $date,
            hospital: $hospital
        })
        WITH r
        MATCH (p:Patient {name: $patient})
        CREATE (p)-[:HAS_REPORT]->(r)
    """, {
        "id": report_id,
        "type": report_type,
        "date": report_date,
        "hospital": entities.get("hospital", ""),
        "patient": patient_name
    })
    print(f"  ✅ Report: {report_type} on {report_date}")

    doctor = entities.get("doctor", "")
    if doctor:
        db.run_query("""
            MERGE (d:Doctor {name: $name})
            WITH d
            MATCH (r:Report {id: $report_id})
            MERGE (r)-[:ATTENDED_BY]->(d)
            WITH d
            MATCH (p:Patient {name: $patient})
            MERGE (p)-[:CONSULTED]->(d)
        """, {
            "name": doctor,
            "report_id": report_id,
            "patient": patient_name
        })
        print(f"  ✅ Doctor: {doctor}")

    hospital = entities.get("hospital", "")
    if hospital:
        db.run_query("""
            MERGE (h:Hospital {name: $name})
            WITH h
            MATCH (r:Report {id: $report_id})
            MERGE (r)-[:PERFORMED_AT]->(h)
        """, {"name": hospital, "report_id": report_id})
        print(f"  ✅ Hospital: {hospital}")

    for lab in entities.get("lab_values", []):
        db.run_query("""
            MATCH (p:Patient {name: $patient})
            MATCH (r:Report {id: $report_id})
            CREATE (l:LabTest {
                name: $name,
                value: $value,
                unit: $unit,
                reference_range: $ref,
                status: $status,
                date: $date
            })
            CREATE (p)-[:HAS_LAB_RESULT]->(l)
            CREATE (r)-[:CONTAINS_LAB]->(l)
        """, {
            "patient": patient_name,
            "report_id": report_id,
            "name": lab.get("name", ""),
            "value": float(lab.get("value", 0)),
            "unit": lab.get("unit", ""),
            "ref": lab.get("reference_range", ""),
            "status": lab.get("status", "UNKNOWN"),
            "date": report_date
        })
        print(f"  ✅ Lab: {lab.get('name')} = {lab.get('value')} ({lab.get('status')})")

    for condition in entities.get("conditions", []):
        db.run_query("""
            MERGE (c:Condition {name: $name})
            WITH c
            MATCH (p:Patient {name: $patient})
            MERGE (p)-[:HAS_CONDITION]->(c)
            WITH c
            MATCH (r:Report {id: $report_id})
            MERGE (r)-[:MENTIONS_CONDITION]->(c)
        """, {
            "name": condition,
            "patient": patient_name,
            "report_id": report_id
        })
        print(f"  ✅ Condition: {condition}")

    for symptom in entities.get("symptoms", []):
        db.run_query("""
            MERGE (s:Symptom {name: $name})
            WITH s
            MATCH (p:Patient {name: $patient})
            MERGE (p)-[:HAS_SYMPTOM]->(s)
        """, {"name": symptom, "patient": patient_name})
        print(f"  ✅ Symptom: {symptom}")

    for finding in entities.get("abnormal_findings", []):
        db.run_query("""
            MERGE (f:Finding {description: $desc})
            WITH f
            MATCH (r:Report {id: $report_id})
            MERGE (r)-[:HAS_FINDING]->(f)
            WITH f
            MATCH (p:Patient {name: $patient})
            MERGE (p)-[:HAS_FINDING]->(f)
        """, {
            "desc": finding,
            "report_id": report_id,
            "patient": patient_name
        })
        print(f"  ⚠️  Finding: {finding}")

    db.close()
    print(f"\n🎉 Graph built for: {report_type} | {report_date}")