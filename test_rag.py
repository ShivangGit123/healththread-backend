import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rag.query_engine import GraphRAGEngine

engine = GraphRAGEngine()
patient = "John Doe"

# Test different questions
questions = [
    "What conditions do I have?",
    "Which medications am I taking?",
    "Which of my lab results are abnormal?",
    "What symptoms do I have?",
    "Which doctor have I consulted?"
]

for q in questions:
    result = engine.answer(q, patient)
    print("\n" + "="*50)
    print(f"Q: {q}")
    print(f"A: {result['answer']}")