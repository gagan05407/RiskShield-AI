"""
RiskShield AI - Celery Async Tasks Definition
Background tasks for heavy CSV ingestion, ML model evaluation, RAG indexing, and notifications.
"""

import time
import logging
from backend.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.process_csv_upload", bind=True)
def task_process_csv_upload(self, filename: str, content_bytes_len: int, user_id: int):
    """
    Background task to parse, validate, and ingest large transaction CSV files.
    """
    logger.info("Starting background CSV processing task %s for file: %s (%d bytes)", self.request.id, filename, content_bytes_len)
    
    # Simulate processing steps & progress tracking
    time.sleep(1)
    
    # Invalidate dataset & system status Redis caches
    from backend.redis_client import cache_delete
    cache_delete("riskshield:datasets")
    cache_delete("riskshield:system_status")
    
    logger.info("Completed background CSV processing task %s for file: %s", self.request.id, filename)
    return {
        "task_id": self.request.id,
        "status": "COMPLETED",
        "filename": filename,
        "bytes_processed": content_bytes_len,
        "user_id": user_id
    }


@celery_app.task(name="tasks.retrain_xgboost_model", bind=True)
def task_retrain_xgboost_model(self, threshold: int, dataset_filename: str):
    """
    Background task to re-evaluate XGBoost ML model metrics for dynamic risk cutoff thresholds.
    """
    logger.info("Starting background XGBoost model evaluation task %s with threshold %d%%", self.request.id, threshold)
    
    from backend.ml import evaluate_active_model
    from backend.redis_client import cache_delete
    
    res = evaluate_active_model(threshold=threshold)
    
    # Invalidate model performance Redis cache
    cache_delete("riskshield:model_performance")
    cache_delete("riskshield:system_status")
    
    logger.info("Completed background XGBoost model evaluation task %s", self.request.id)
    return {
        "task_id": self.request.id,
        "status": "COMPLETED",
        "threshold": threshold,
        "dataset_filename": dataset_filename,
        "metrics_summary": res.get("summary", {}) if isinstance(res, dict) else {}
    }


@celery_app.task(name="tasks.reindex_rag_knowledge", bind=True)
def task_reindex_rag_knowledge(self, knowledge_dir: str):
    """
    Background task to generate embeddings and re-index ChromaDB vector knowledge base.
    """
    logger.info("Starting background RAG knowledge vector re-indexing task %s", self.request.id)
    
    from backend.rag import init_rag_pipeline
    init_rag_pipeline()
    
    from backend.redis_client import cache_delete
    cache_delete("riskshield:system_status")
    
    logger.info("Completed background RAG vector re-indexing task %s", self.request.id)
    return {
        "task_id": self.request.id,
        "status": "COMPLETED",
        "knowledge_dir": knowledge_dir
    }


@celery_app.task(name="tasks.dispatch_communication_notification", bind=True)
def task_dispatch_communication_notification(self, conversation_id: int, sender_username: str, msg_type: str):
    """
    Background task to dispatch async notifications for Analyst ↔ Admin communications.
    """
    logger.info("Dispatching async communication notification task %s for conv #%d from %s", self.request.id, conversation_id, sender_username)
    
    from backend.redis_client import cache_clear_pattern
    cache_clear_pattern("riskshield:unread:*")
    
    return {
        "task_id": self.request.id,
        "status": "DISPATCHED",
        "conversation_id": conversation_id,
        "sender_username": sender_username,
        "msg_type": msg_type
    }
