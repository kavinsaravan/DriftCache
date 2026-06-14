"""
FAISS-based vector search engine for semantic similarity

Includes autonomous index rebuild infrastructure
"""
from app.vectorstore.index_health import IndexHealthMonitor
from app.vectorstore.index_manager import IndexManager
from app.vectorstore.rebuild import IndexRebuilder

__all__ = [
    "IndexHealthMonitor",
    "IndexManager",
    "IndexRebuilder",
]
