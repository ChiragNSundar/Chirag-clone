
"""
Graph Service - Knowledge Graph management using NetworkX.
Stores entities and relationships for structured reasoning (GraphRAG).
"""
import networkx as nx
import json
import os
import logging
from typing import List, Dict, Any, Tuple
from config import Config

logger = logging.getLogger(__name__)

class GraphService:
    """
    Manages the Knowledge Graph.
    Nodes = Entities (Person, Concept, Project, etc.)
    Edges = Relationships (worked_on, unrelated_to, part_of, etc.)
    """
    
    def __init__(self):
        self.graph_path = os.path.join(Config.DATA_DIR, "memory_graph.json")
        self.graph = nx.MultiDiGraph()
        self._load_graph()
        
    def _load_graph(self):
        """Load graph from JSON file."""
        if os.path.exists(self.graph_path):
            try:
                with open(self.graph_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.graph = nx.node_link_graph(data)
                logger.info(f"Loaded knowledge graph with {self.graph.number_of_nodes()} nodes")
            except Exception as e:
                logger.error(f"Failed to load graph: {e}")
                self.graph = nx.MultiDiGraph()
    
    def _save_graph(self):
        """Save graph to JSON file."""
        try:
            data = nx.node_link_data(self.graph)
            os.makedirs(os.path.dirname(self.graph_path), exist_ok=True)
            with open(self.graph_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save graph: {e}")

    def add_relation(self, source: str, target: str, relation: str, metadata: Dict = None):
        """Add a relationship (edge) between two entities."""
        if not source or not target:
            return
            
        self.graph.add_node(source, type="entity")
        self.graph.add_node(target, type="entity")
        self.graph.add_edge(source, target, relation=relation, **(metadata or {}))
        self._save_graph()

    def add_triples(self, triples: List[Tuple[str, str, str]]):
        """Add multiple triples (source, relation, target)."""
        changed = False
        for src, rel, tgt in triples:
            if src and tgt:
                self.graph.add_edge(src, tgt, relation=rel)
                changed = True
        
        if changed:
            self._save_graph()

    def get_context(self, entities: List[str], depth: int = 1) -> List[Dict]:
        """
        Get graph context for a list of entities (ego graph).
        Returns list of {source, relation, target}.
        """
        context = []
        for entity in entities:
            if entity in self.graph:
                # Get neighbors
                # For depth 1, just outgoing/incoming edges
                try:
                    edges = self.graph.edges(entity, data=True)
                    for src, tgt, data in edges:
                        context.append({
                            "source": src,
                            "target": tgt,
                            "relation": data.get("relation", "subordinate")
                        })
                    
                    # Also incoming
                    in_edges = self.graph.in_edges(entity, data=True)
                    for src, tgt, data in in_edges:
                        context.append({
                            "source": src,
                            "target": tgt,
                            "relation": data.get("relation", "subordinate")
                        })
                except Exception:
                    pass
                    
        return context

    def search_graph(self, query_entities: List[str]) -> str:
        """
        Return a textual representation of the graph context for the query entities.
        """
        context = self.get_context(query_entities)
        if not context:
            return ""
            
        text = "GRAPH KNOWLEDGE:\n"
        seen = set()
        for item in context[:20]: # Limit to avoid flooding context
             s = f"{item['source']} {item['relation']} {item['target']}"
             if s not in seen:
                 text += f"- {s}\n"
                 seen.add(s)
        return text

    def get_relevant_context(self, query: str) -> str:
        """
        Find relevant graph context based on entities found in the query.
        Simple string matching against graph nodes.
        """
        query_lower = query.lower()
        found_entities = []
        
        # Check for presence of known nodes in query
        # This is O(N) where N is nodes. Fine for small/medium graphs.
        for node in self.graph.nodes():
            if str(node).lower() in query_lower:
                found_entities.append(node)
        
        if not found_entities:
            return ""
            
        return self.search_graph(found_entities)
    
    def get_stats(self):
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges()
        }

# Singleton
_graph_service = None

def get_graph_service() -> GraphService:
    global _graph_service
    if _graph_service is None:
        _graph_service = GraphService()
    return _graph_service
