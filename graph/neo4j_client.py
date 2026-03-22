from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

class Neo4jClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"),
            auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
        )

    def run_query(self, cypher: str, params: dict = {}):
        with self.driver.session() as session:
            result = session.run(cypher, params)
            return [record.data() for record in result]

    def close(self):
        self.driver.close()