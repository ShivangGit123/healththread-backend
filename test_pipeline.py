import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ingestion.pdf_parser import parse_pdf
from ingestion.entity_extractor import extract_entities
from graph.graph_builder import build_graph_from_entities
import json

# Use the real PDF path
pdf_path = r"C:\Users\Dell\Desktop\AVNEESH KUMAR MISHRA.pdf"

print("Step 1: Parsing PDF...")
parsed = parse_pdf(pdf_path)
print("Text preview:", parsed['text'][:300])

print("\nStep 2: Extracting entities...")
entities = extract_entities(parsed['text'])
print(json.dumps(entities, indent=2))
print("Step 1: Parsing PDF...")
parsed = parse_pdf(pdf_path)
print("Text length:", len(parsed['text']))
print("Text preview:\n", parsed['text'][:500])
print("\nStep 3: Building graph...")
build_graph_from_entities(entities, "Avneesh Kumar Mishra")