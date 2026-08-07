from __future__ import annotations
from typing import Any
from neo4j import GraphDatabase
from .config import settings


class Neo4jGraph:
    def __init__(self):
        self.enabled = settings.neo4j_enabled
        self.driver = None
        if self.enabled:
            try:
                self.driver = GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password),
                )
                self.driver.verify_connectivity()
            except Exception:
                self.enabled = False
                self.driver = None

    def sync_artifact(self, artifact: dict[str, Any]):
        if not self.enabled or not self.driver:
            return
        label = {
            "jira": "JiraIssue",
            "endpoint": "Endpoint",
            "document": "Document",
            "test": "TestCase",
            "decision": "Decision",
            "transcript": "Transcript",
        }.get(artifact["artifact_type"], "Artifact")

        query = f"""
        MERGE (n:{label} {{external_id: $external_id, project_id: $project_id}})
        SET n.title=$title, n.content=$content, n.updated_at=$updated_at
        """
        with self.driver.session() as session:
            session.run(query, **artifact)

    def sync_relation(self, source: dict, target: dict, relation: dict):
        if not self.enabled or not self.driver:
            return
        relation_type = relation["relation_type"].replace("-", "_").upper()
        query = f"""
        MATCH (a {{external_id: $source_external_id, project_id: $project_id}})
        MATCH (b {{external_id: $target_external_id, project_id: $project_id}})
        MERGE (a)-[r:{relation_type}]->(b)
        SET r.method=$method, r.confidence=$confidence,
            r.evidence=$evidence, r.status=$status
        """
        with self.driver.session() as session:
            session.run(
                query,
                source_external_id=source["external_id"],
                target_external_id=target["external_id"],
                project_id=source["project_id"],
                **relation,
            )


neo4j_graph = Neo4jGraph()
