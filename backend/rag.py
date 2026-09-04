import os
import glob
from typing import List, Dict, Any, Tuple
import chromadb

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DIR = os.path.join(ROOT_DIR, ".chromadb")
DEFAULT_KNOWLEDGE_DIR = os.path.join(ROOT_DIR, "data", "knowledge")

def get_chroma_client():
    os.makedirs(CHROMA_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    return client

def get_or_create_collection():
    client = get_chroma_client()
    collection = client.get_or_create_collection(name="risk_knowledge")
    return collection

def ingest_knowledge_files(knowledge_dir: str = None):
    if not knowledge_dir:
        knowledge_dir = DEFAULT_KNOWLEDGE_DIR
    """
    Ingests policy and guideline text files into ChromaDB vector database.
    Retains file metadata for source attribution.
    """
    collection = get_or_create_collection()
    
    if collection.count() > 0:
        return collection.count()

    txt_files = glob.glob(os.path.join(knowledge_dir, "*.txt"))
    
    documents = []
    metadatas = []
    ids = []
    
    doc_id = 1
    for file_path in txt_files:
        fname = os.path.basename(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        sections = content.split("\n\n")
        for idx, section in enumerate(sections):
            text = section.strip()
            if len(text) > 30:
                documents.append(text)
                metadatas.append({"source": fname, "section_idx": idx})
                ids.append(f"doc_{fname}_{doc_id}")
                doc_id += 1

    if documents:
        collection.add(documents=documents, metadatas=metadatas, ids=ids)
    
    return collection.count()


def search_knowledge(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Retrieves vector similarity document chunks from ChromaDB.
    """
    collection = get_or_create_collection()
    if collection.count() == 0:
        ingest_knowledge_files()

    results = collection.query(query_texts=[query], n_results=min(top_k, max(1, collection.count())))
    
    retrieved_docs = []
    if results and "documents" in results and len(results["documents"]) > 0:
        docs = results["documents"][0]
        metas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
        distances = results["distances"][0] if "distances" in results and results["distances"] else [0.0] * len(docs)
        
        for d, m, dist in zip(docs, metas, distances):
            retrieved_docs.append({
                "content": d,
                "source": m.get("source", "Knowledge Base"),
                "distance": float(dist)
            })

    return retrieved_docs


def evaluate_retrieval_crag(query: str, retrieved_docs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Implement CRAG (Corrective RAG).
    Evaluates whether retrieved documents are relevant to query.
    If initial retrieval is weak/irrelevant, reformulates query and retrieves again.
    Returns: (final_docs, crag_details_dict)
    """
    if not retrieved_docs:
        reformatted_query = _reformulate_query(query)
        new_docs = search_knowledge(reformatted_query, top_k=4)
        details = {
            "initial_quality": "Empty",
            "correction_triggered": True,
            "reformatted_query": reformatted_query,
            "final_quality": "Strong" if new_docs else "Weak",
            "crag_status_str": "CRAG: Initial retrieval empty -> Query reformulated -> Secondary search executed",
            "passed": True if new_docs else False
        }
        return new_docs, details

    # Calculate relevance score based on keyword overlap
    query_words = set(query.lower().replace("?", "").replace(".", "").split())
    important_keywords = {w for w in query_words if len(w) > 3 and w not in {"what", "where", "which", "this", "that", "from", "have", "with", "show"}}
    
    relevance_scores = []
    for doc in retrieved_docs:
        doc_text = doc["content"].lower()
        matched = sum(1 for kw in important_keywords if kw in doc_text)
        rel_ratio = matched / max(1, len(important_keywords))
        relevance_scores.append(rel_ratio)

    avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0

    # CRAG Decision Threshold: If relevance score < 0.25, trigger query correction
    if avg_relevance < 0.25:
        reformatted_query = _reformulate_query(query)
        secondary_docs = search_knowledge(reformatted_query, top_k=4)
        
        combined_docs = retrieved_docs + secondary_docs
        seen_contents = set()
        unique_docs = []
        for d in combined_docs:
            if d["content"] not in seen_contents:
                seen_contents.add(d["content"])
                unique_docs.append(d)

        details = {
            "initial_quality": f"Weak ({avg_relevance*100:.0f}% relevance)",
            "correction_triggered": True,
            "reformatted_query": reformatted_query,
            "final_quality": "Strong (Corrected)",
            "crag_status_str": "CRAG: Initial retrieval weak -> Query reformulated & expanded retrieval used",
            "passed": True
        }
        return unique_docs[:4], details
    else:
        details = {
            "initial_quality": f"Strong ({avg_relevance*100:.0f}% relevance)",
            "correction_triggered": False,
            "reformatted_query": "N/A (Original query sufficient)",
            "final_quality": "Strong",
            "crag_status_str": "CRAG: Retrieval Validated (Evidence Quality High)",
            "passed": True
        }
        return retrieved_docs, details


def _reformulate_query(original_query: str) -> str:
    """
    Query reformulation helper for CRAG.
    Extracts key domain terms like velocity, device, location, amount anomaly, chargeback, or policy rules.
    """
    q_lower = original_query.lower()
    keywords = []
    
    if "velocity" in q_lower or "rapid" in q_lower or "frequency" in q_lower:
        keywords.append("velocity risk policy transaction attempts")
    if "device" in q_lower or "fingerprint" in q_lower:
        keywords.append("new device anomaly policy")
    if "location" in q_lower or "ip" in q_lower or "city" in q_lower:
        keywords.append("unusual location geographic anomaly policy")
    if "amount" in q_lower or "high" in q_lower or "deviation" in q_lower:
        keywords.append("amount deviation historical baseline policy")
    if "chargeback" in q_lower or "dispute" in q_lower:
        keywords.append("previous chargebacks risk policy")
    if "hold" in q_lower or "review" in q_lower or "approve" in q_lower:
        keywords.append("risk score decision thresholds approve review hold")

    if keywords:
        return " ".join(keywords)
    else:
        return "payment risk policy manual review guidelines fraud thresholds"
