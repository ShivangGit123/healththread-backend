import os
import json
from groq import Groq
from dotenv import load_dotenv
from graph.neo4j_client import Neo4jClient
from rag.cypher_generator import generate_cypher

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

ANSWER_PROMPT = """
You are a helpful and friendly health assistant.
The user asked a question about their health records.
You have retrieved data from their personal health knowledge graph.
Explain the data in simple plain English like you're talking to a non-medical person.

Rules:
- Be specific with numbers and dates
- If a lab value is HIGH or LOW mention it clearly
- If something looks concerning say it gently
- Always end with: "Please consult your doctor for medical advice."
- Keep answer to 3-5 sentences max

Patient Question: {question}
Retrieved Health Data: {data}

Your Answer:"""


class GraphRAGEngine:
    def __init__(self):
        self.db = Neo4jClient()

    def answer(self, question: str, patient_name: str) -> dict:

        print(f"\n🔍 Question: {question}")

        # Step 1 — Generate Cypher from question
        cypher = generate_cypher(question)
        print(f"📝 Generated Cypher: {cypher}")

        # Step 2 — Run Cypher on Neo4j
        try:
            graph_data = self.db.run_query(
                cypher,
                {"patient_name": patient_name}
            )
            print(f"📊 Graph Data: {graph_data}")
        except Exception as e:
            return {
                "answer": f"Sorry, I couldn't retrieve that data. Error: {str(e)}",
                "cypher": cypher,
                "data": []
            }

        if not graph_data:
            return {
                "answer": "I couldn't find any matching records in your health history for that question.",
                "cypher": cypher,
                "data": []
            }

        # Step 3 — Generate plain English answer
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": ANSWER_PROMPT.format(
                    question=question,
                    data=json.dumps(graph_data, indent=2)
                )
            }],
            temperature=0.3
        )

        answer = response.choices[0].message.content.strip()

        return {
            "answer": answer,
            "cypher": cypher,
            "data": graph_data
        }