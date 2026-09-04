import os
import sys
import io
import datetime
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from utils import (
    generate_all_synthetic_datasets, validate_csv_schema,
    calculate_cost_impact, DATASET_CONFIGS
)
from database import (
    init_db, seed_db_from_dataframe, seed_db_from_csv,
    get_all_transactions, get_all_audit_logs, get_transaction_by_id,
    add_new_transaction, save_analyst_action, get_latest_analyst_action,
    get_dataset_counts, save_prediction, get_customer_history,
    get_device_history, get_velocity_stats, create_user,
    get_user_by_username, get_user_by_email, get_user_by_id,
    get_all_users, update_user_status, delete_user, save_audit_log,
    get_setting, save_setting,
    get_or_create_conversation, get_conversations_for_admin, send_message,
    get_messages_in_conversation, mark_messages_read, resolve_api_key_request,
    get_unread_notification_count, has_open_api_key_request
)

from ml import engineer_features, train_and_evaluate_models, load_saved_model, score_transaction, get_shap_explanation
from agent import run_ai_investigation, chat_with_copilot, run_post_decision_analysis
from redis_client import (
    is_redis_available, cache_get, cache_set, cache_delete,
    get_redis_telemetry
)
from celery_app import get_celery_telemetry
from tasks import (
    task_process_csv_upload, task_retrain_xgboost_model,
    task_reindex_rag_knowledge, task_dispatch_communication_notification
)
from rag import ingest_knowledge_files
from llm import get_available_models, test_api_connection, DEFAULT_MODELS, validate_model_for_provider, extract_text_from_response
from auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_admin, require_analyst_or_admin,
    require_active_user
)
from seed_users import seed_users

# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI APP & CORS
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="RiskShield AI API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows Vite dev server on http://localhost:5173
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session state for active dataset & AI config
STATE = {
    "selected_dataset": "mixed_risk_transactions.csv",
    "byok_provider": "Google Gemini",
    "byok_key": os.getenv("GEMINI_API_KEY", os.getenv("GROQ_API_KEY", os.getenv("OPENAI_API_KEY", ""))),
    "byok_model": DEFAULT_MODELS["Google Gemini"],
    "byok_status": "Not Tested",
    "byok_status_msg": "",
    "byok_tech_details": "",
    "threshold_approve": 25,
    "threshold_review": 50,
    "risk_score_cutoff_threshold": 50,
    "selected_tx_id": None
}

@app.on_event("startup")
def startup_event():
    init_db()
    seed_users()
    generate_all_synthetic_datasets()
    ingest_knowledge_files()
    
    saved_thresh = get_setting("risk_score_cutoff_threshold", "50")
    try:
        thresh_val = int(saved_thresh)
    except (ValueError, TypeError):
        thresh_val = 50
    STATE["risk_score_cutoff_threshold"] = thresh_val
    STATE["threshold_review"] = thresh_val
    
    default_csv = os.path.join(ROOT_DIR, "data", "datasets", STATE["selected_dataset"])
    if os.path.exists(default_csv):
        df_init = pd.read_csv(default_csv)
        seed_db_from_dataframe(df_init)
        train_and_evaluate_models(df_init, thresh_val)
        df_all = get_all_transactions()
        df_feat = engineer_features(df_all)
        for _, row in df_feat.iterrows():
            sc = score_transaction(row.to_dict(), STATE["threshold_approve"], STATE["threshold_review"])
            save_prediction(sc["transaction_id"], sc["fraud_probability"], sc["risk_score"], sc["risk_level"], sc["status"], sc["risk_signals"])



def switch_dataset_internal(dataset_filename: str):
    target = dataset_filename.strip().lower()
    
    # Map friendly labels or shorthand names to exact dataset CSV filenames
    filename_map = {
        "mixed_risk_transactions.csv": "mixed_risk_transactions.csv",
        "mixed risk (recommended)": "mixed_risk_transactions.csv",
        "mixed risk": "mixed_risk_transactions.csv",
        "mixed": "mixed_risk_transactions.csv",

        "normal_transactions.csv": "normal_transactions.csv",
        "normal traffic": "normal_transactions.csv",
        "normal": "normal_transactions.csv",

        "fraud_transactions.csv": "fraud_transactions.csv",
        "high risk / fraud": "fraud_transactions.csv",
        "high risk": "fraud_transactions.csv",
        "fraud": "fraud_transactions.csv",

        "fraud_spike_transactions.csv": "fraud_spike_transactions.csv",
        "fraud spike": "fraud_spike_transactions.csv",
        "spike": "fraud_spike_transactions.csv",

        "edge_case_transactions.csv": "edge_case_transactions.csv",
        "edge cases": "edge_case_transactions.csv",
        "edge": "edge_case_transactions.csv",
    }

    resolved_fn = filename_map.get(target, dataset_filename)
    path = os.path.join(ROOT_DIR, "data", "datasets", resolved_fn)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Dataset file '{resolved_fn}' not found in data/datasets/.")
    
    df = pd.read_csv(path)
    seed_db_from_dataframe(df)
    STATE["selected_dataset"] = resolved_fn
    cur_thresh = STATE.get("risk_score_cutoff_threshold", 50)
    train_and_evaluate_models(df, cur_thresh)
    df_all = get_all_transactions()
    df_feat = engineer_features(df_all)
    for _, row in df_feat.iterrows():
        sc = score_transaction(row.to_dict(), STATE["threshold_approve"], STATE["threshold_review"])
        save_prediction(sc["transaction_id"], sc["fraud_probability"], sc["risk_score"], sc["risk_level"], sc["status"], sc["risk_signals"])
    
    STATE["selected_tx_id"] = None




# ─────────────────────────────────────────────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ─────────────────────────────────────────────────────────────────────────────
class DatasetSwitchReq(BaseModel):
    dataset_filename: str

class NewTransactionReq(BaseModel):
    transaction_id: str
    customer_id: str
    amount: float
    payment_method: str
    device_id: str
    location: str
    failed_attempts: int = 0
    account_age_days: int = 180
    timestamp: Optional[str] = None

class AnalystDecisionReq(BaseModel):
    decision: str
    remark: Optional[str] = ""
    reason: Optional[str] = ""

class AIConfigReq(BaseModel):
    provider: str
    api_key: Optional[str] = ""
    model: str

class CopilotReq(BaseModel):
    user_query: str
    target_tx_id: Optional[str] = None

class CostCalcReq(BaseModel):
    fp_cost: float = 2000.0
    fn_cost: float = 35000.0
    sim_threshold: int = 50

class ThresholdUpdateReq(BaseModel):
    threshold: int

class SendMessageReq(BaseModel):
    conversation_id: Optional[int] = None
    analyst_id: Optional[int] = None
    message: str
    msg_type: Optional[str] = "NORMAL_MESSAGE"

class ResolveRequestReq(BaseModel):
    message_id: int



class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = ""
    role: Optional[str] = "analyst"


# ─────────────────────────────────────────────────────────────────────────────
# AUTHENTICATION & USER MANAGEMENT ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/auth/login")
def login(req: LoginRequest):
    user = get_user_by_username(req.username)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Unable to log in. Please contact the administrator."
        )
    if not verify_password(req.password, user["hashed_password"]):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password."
        )
    
    user_status = user.get("status", "PENDING_APPROVAL").upper()
    if user_status == "PENDING_APPROVAL":
        raise HTTPException(
            status_code=403,
            detail="Your account is pending administrator approval. Please wait until an administrator approves your registration."
        )
    elif user_status == "REJECTED":
        raise HTTPException(
            status_code=403,
            detail="Unable to log in. Please contact the administrator."
        )
    elif user_status != "ACTIVE":
        raise HTTPException(
            status_code=403,
            detail="Unable to log in. Please contact the administrator."
        )

    access_token = create_access_token(data={
        "sub": user["username"],
        "email": user["email"],
        "role": user["role"].lower(),
        "full_name": user.get("full_name", "")
    })
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "user_id": user["user_id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"].lower(),
            "full_name": user.get("full_name", ""),
            "status": user_status
        }
    }

@app.post("/api/auth/register")
def register(req: RegisterRequest):
    try:
        hashed_pwd = hash_password(req.password)
        # All new registrations require admin approval and start as PENDING_APPROVAL
        new_user = create_user(
            username=req.username,
            email=req.email,
            hashed_password=hashed_pwd,
            role=req.role or "analyst",
            full_name=req.full_name or "",
            status="PENDING_APPROVAL"
        )
        return {
            "status": "PENDING_APPROVAL",
            "message": "Registration submitted successfully. Your account is pending administrator approval. You will be able to log in after an administrator approves your registration.",
            "user": new_user
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    user = get_user_by_username(current_user["username"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"].lower(),
        "full_name": user.get("full_name", ""),
        "status": user.get("status", "ACTIVE"),
        "created_at": user.get("created_at")
    }

# ─────────────────────────────────────────────────────────────────────────────
# ADMIN USER MANAGEMENT & APPROVAL ENDPOINTS (ADMIN ONLY)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/admin/users")
def list_admin_users(admin: dict = Depends(require_admin)):
    """Retrieve all users and their approval statuses."""
    users = get_all_users()
    pending = [u for u in users if u.get("status") == "PENDING_APPROVAL"]
    return {"users": users, "pending_users": pending, "total": len(users), "pending_count": len(pending)}

@app.post("/api/admin/users/{user_id}/approve")
def approve_user_endpoint(user_id: int, admin: dict = Depends(require_admin)):
    """Approve a pending user registration."""
    try:
        updated = update_user_status(user_id, "ACTIVE")
        # Save audit log of admin approval
        save_audit_log(
            tx_id="N/A",
            risk_score=0,
            agent_action=f"User Registration Approved: {updated['username']}",
            tools_used=["admin_user_approval"],
            rag_retrieved=["Access Control Policy"],
            crag_result="Approved",
            srag_result="Active",
            recommendation="APPROVE",
            final_explanation=f"Administrator '{admin['username']}' approved registration for user '{updated['username']}' (Role: {updated['role'].upper()}, Email: {updated['email']}). Status set to ACTIVE."
        )
        return {
            "success": True,
            "status": "ACTIVE",
            "message": f"User '{updated['username']}' ({updated['role']}) approved and activated successfully.",
            "user": updated
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/admin/users/{user_id}/reject")
def reject_user_endpoint(user_id: int, admin: dict = Depends(require_admin)):
    """Reject and delete a user registration."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User #{user_id} not found.")
    
    # Save audit log of admin rejection before deleting
    save_audit_log(
        tx_id="N/A",
        risk_score=0,
        agent_action=f"User Registration Rejected: {user['username']}",
        tools_used=["admin_user_approval"],
        rag_retrieved=["Access Control Policy"],
        crag_result="Rejected",
        srag_result="Account Deleted",
        recommendation="REJECT",
        final_explanation=f"Administrator '{admin['username']}' rejected and removed registration for user '{user['username']}' (Requested Role: {user['role'].upper()}, Email: {user['email']})."
    )
    
    # Delete the user registration completely
    delete_user(user_id)
    return {
        "success": True,
        "status": "REJECTED",
        "message": f"User '{user['username']}' ({user['role']}) registration rejected and removed.",
        "user": user
    }


# ─────────────────────────────────────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/system/status")
def get_system_status(user: dict = Depends(require_active_user)):
    cached_status = cache_get("riskshield:system_status")
    if cached_status:
        return cached_status

    counts = get_dataset_counts()
    active_ds_label = DATASET_CONFIGS.get(STATE["selected_dataset"], {}).get("label", STATE["selected_dataset"])
    redis_info = get_redis_telemetry()
    celery_info = get_celery_telemetry()

    res = {
        "active_dataset": STATE["selected_dataset"],
        "active_dataset_label": active_ds_label,
        "historical_count": counts["historical"],
        "new_count": counts["new"],
        "total_count": counts["total"],
        "provider": STATE["byok_provider"],
        "model": STATE["byok_model"],
        "has_api_key": bool(STATE["byok_key"]),
        "byok_status": STATE["byok_status"],
        "redis_status": redis_info.get("status", "OFFLINE"),
        "celery_status": celery_info.get("status", "OFFLINE"),
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    cache_set("riskshield:system_status", res, ttl_seconds=10)
    return res


@app.get("/api/system/redis-celery-status")
def get_redis_celery_status_endpoint(user: dict = Depends(require_active_user)):
    """
    Returns telemetry metrics for Redis in-memory cache and Celery background task workers.
    """
    redis_info = get_redis_telemetry()
    celery_info = get_celery_telemetry()
    return {
        "redis": redis_info,
        "celery": celery_info,
        "mode": "Distributed Multi-process" if redis_info.get("available") and celery_info.get("available") else "Synchronous Fallback"
    }


@app.get("/api/datasets")
def get_datasets(user: dict = Depends(require_active_user)):
    return {
        "datasets": [
            {"filename": k, "label": v["label"], "description": v.get("description", "")}
            for k, v in DATASET_CONFIGS.items()
        ],
        "active": STATE["selected_dataset"]
    }


@app.post("/api/dataset/switch")
def switch_dataset(req: DatasetSwitchReq, user: dict = Depends(require_analyst_or_admin)):
    switch_dataset_internal(req.dataset_filename)
    return get_system_status(user)


@app.get("/api/overview")
def get_overview(user: dict = Depends(require_analyst_or_admin)):
    df_all = get_all_transactions()
    if df_all.empty:
        return {"summary": {"total": 0, "approve": 0, "review": 0, "hold": 0, "high_risk_rate": 0, "amount_at_risk": 0, "new_count": 0}, "pie_data": [], "scatter_sample": [], "pm_summary": [], "top_locations": [], "high_priority": []}

    total = len(df_all)
    approve_n = int((df_all["effective_status"] == "APPROVE").sum())
    review_n  = int((df_all["effective_status"] == "REVIEW").sum())
    hold_n    = int((df_all["effective_status"] == "HOLD").sum())
    risk_pct  = round((hold_n / max(1, total)) * 100, 1)
    at_risk   = float(df_all[df_all["effective_status"] == "HOLD"]["amount"].sum())

    pie_data = [
        {"name": "APPROVE", "value": approve_n, "color": "#059669"},
        {"name": "REVIEW", "value": review_n, "color": "#D97706"},
        {"name": "HOLD", "value": hold_n, "color": "#DC2626"},
    ]

    scatter_sample = []
    for _, r in df_all.head(300).iterrows():
        scatter_sample.append({
            "transaction_id": r["transaction_id"],
            "customer_id": r["customer_id"],
            "amount": float(r["amount"]),
            "risk_score": int(r["risk_score"]),
            "status": r["effective_status"]
        })

    pm_summary = []
    if "payment_method" in df_all.columns:
        pm_grp = df_all.groupby(["payment_method", "effective_status"]).size().unstack(fill_value=0)
        for pm in pm_grp.index:
            pm_summary.append({
                "payment_method": pm,
                "APPROVE": int(pm_grp.loc[pm].get("APPROVE", 0)),
                "REVIEW": int(pm_grp.loc[pm].get("REVIEW", 0)),
                "HOLD": int(pm_grp.loc[pm].get("HOLD", 0)),
            })

    top_locations = []
    if "location" in df_all.columns:
        loc_df = df_all[df_all["effective_status"].isin(["HOLD", "REVIEW"])].groupby("location").size().reset_index(name="count").sort_values("count", ascending=False).head(8)
        for _, r in loc_df.iterrows():
            top_locations.append({"location": r["location"], "count": int(r["count"])})

    risky_df = df_all[df_all["effective_status"].isin(["HOLD", "REVIEW"])].sort_values("risk_score", ascending=False).head(15)
    high_priority = risky_df[["transaction_id", "customer_id", "amount", "payment_method", "location", "risk_score", "effective_status", "timestamp"]].to_dict(orient="records")

    return {
        "summary": {
            "total": total,
            "approve": approve_n,
            "review": review_n,
            "hold": hold_n,
            "high_risk_rate": risk_pct,
            "amount_at_risk": at_risk,
            "new_count": get_dataset_counts()["new"]
        },
        "pie_data": pie_data,
        "scatter_sample": scatter_sample,
        "pm_summary": pm_summary,
        "top_locations": top_locations,
        "high_priority": high_priority
    }


@app.get("/api/transactions")
def get_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=5, le=100),
    status: Optional[str] = Query(None),
    decision: Optional[str] = Query(None),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
    payment_method: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("timestamp_desc"),
    tx_search: Optional[str] = Query(None),
    cust_search: Optional[str] = Query(None),
    user: dict = Depends(require_active_user)
):
    df_all = get_all_transactions()
    if df_all.empty:
        return {"items": [], "total": 0, "page": 1, "total_pages": 1, "pm_options": []}

    pm_options = sorted(df_all["payment_method"].dropna().unique().tolist())
    max_amt_data = float(df_all["amount"].max())

    filtered = df_all.copy()
    if status:
        st_list = [s.strip() for s in status.split(",") if s.strip()]
        if st_list:
            filtered = filtered[filtered["effective_status"].isin(st_list)]
    
    if payment_method:
        pm_list = [p.strip() for p in payment_method.split(",") if p.strip()]
        if pm_list:
            filtered = filtered[filtered["payment_method"].isin(pm_list)]

    if min_amount is not None:
        filtered = filtered[filtered["amount"] >= min_amount]
    if max_amount is not None:
        filtered = filtered[filtered["amount"] <= max_amount]

    if cust_search:
        filtered = filtered[filtered["customer_id"].astype(str).str.contains(cust_search.strip(), case=False, na=False)]
    if tx_search:
        filtered = filtered[filtered["transaction_id"].astype(str).str.contains(tx_search.strip(), case=False, na=False)]

    if sort_by == "risk_score_desc":
        filtered = filtered.sort_values("risk_score", ascending=False)
    elif sort_by == "risk_score_asc":
        filtered = filtered.sort_values("risk_score", ascending=True)
    elif sort_by == "amount_desc":
        filtered = filtered.sort_values("amount", ascending=False)
    elif sort_by == "timestamp_desc":
        filtered = filtered.sort_values("timestamp", ascending=False)

    total_rows = len(filtered)
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    cur_p = max(1, min(page, total_pages))

    paged = filtered.iloc[(cur_p - 1) * page_size : cur_p * page_size].copy()
    items = paged.to_dict(orient="records")

    return {
        "items": items,
        "total": total_rows,
        "total_working": len(df_all),
        "page": cur_p,
        "total_pages": total_pages,
        "pm_options": pm_options,
        "max_dataset_amount": max_amt_data
    }


@app.get("/api/transactions/{tx_id}")
def get_transaction_detail(tx_id: str, user: dict = Depends(require_active_user)):
    tx_row = get_transaction_by_id(tx_id)
    if not tx_row:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    df_f = engineer_features(pd.DataFrame([tx_row]))
    scored = score_transaction(df_f.iloc[0].to_dict(), STATE["threshold_approve"], STATE["threshold_review"])
    latest_a = get_latest_analyst_action(tx_id)
    shap_data = get_shap_explanation(df_f.iloc[0].to_dict())

    return {
        "transaction": tx_row,
        "ml_score": scored,
        "effective_status": latest_a["new_status"] if latest_a else scored["status"],
        "latest_action": latest_a,
        "shap": shap_data
    }


@app.post("/api/transactions/new")
def create_new_transaction(req: NewTransactionReq, user: dict = Depends(require_analyst_or_admin)):
    ts = req.timestamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_row = {
        "transaction_id": req.transaction_id.strip(),
        "customer_id": req.customer_id.strip(),
        "amount": float(req.amount),
        "payment_method": req.payment_method,
        "device_id": req.device_id.strip(),
        "location": req.location.strip(),
        "failed_attempts": int(req.failed_attempts),
        "account_age_days": int(req.account_age_days),
        "previous_chargebacks": 0,
        "timestamp": ts
    }
    added = add_new_transaction(new_row)
    df_s = pd.DataFrame([added])
    df_sf = engineer_features(df_s)
    sc = score_transaction(df_sf.iloc[0].to_dict(), STATE["threshold_approve"], STATE["threshold_review"])
    save_prediction(sc["transaction_id"], sc["fraud_probability"], sc["risk_score"], sc["risk_level"], sc["status"], sc["risk_signals"])

    return {
        "success": True,
        "transaction": added,
        "ml_score": sc
    }


@app.post("/api/transactions/{tx_id}/decision")
def record_analyst_decision(tx_id: str, req: AnalystDecisionReq, user: dict = Depends(require_analyst_or_admin)):
    tx_row = get_transaction_by_id(tx_id)
    if not tx_row:
        raise HTTPException(status_code=404, detail=f"Transaction '{tx_id}' not found in SQLite database.")

    new_dec = req.decision.strip().upper()
    if new_dec not in ["APPROVE", "REVIEW", "HOLD"]:
        raise HTTPException(status_code=400, detail=f"Invalid decision '{new_dec}'. Must be APPROVE, REVIEW, or HOLD.")

    ai_rec = tx_row.get("ai_decision") or tx_row.get("model_status") or "REVIEW"
    prev_status = tx_row.get("effective_status") or ai_rec
    score = tx_row.get("risk_score", 0)
    
    user_reason = (req.reason or req.remark or "").strip()
    remark_text = user_reason if user_reason else f"Analyst updated decision to {new_dec}"

    res = run_post_decision_analysis(
        transaction_id=tx_id,
        prev_status=prev_status,
        new_status=new_dec,
        risk_score=score,
        ai_recommendation=ai_rec,
        analyst_remark=remark_text,
        provider=STATE.get("byok_provider"),
        api_key=STATE.get("byok_key"),
        model_name=STATE.get("byok_model")
    )
    
    updated_tx = get_transaction_by_id(tx_id)
    latest_a = get_latest_analyst_action(tx_id)

    return {
        "success": True,
        "transaction_id": tx_id,
        "ai_decision": updated_tx.get("ai_decision"),
        "analyst_decision": updated_tx.get("analyst_decision"),
        "analyst_reason": updated_tx.get("analyst_reason"),
        "effective_status": updated_tx.get("effective_status"),
        "analyst_override": updated_tx.get("analyst_override"),
        "risk_score": updated_tx.get("risk_score"),
        "transaction": updated_tx,
        "latest_action": latest_a,
        "analysis": res
    }


@app.post("/api/transactions/upload")
async def upload_transactions_csv(file: UploadFile = File(...), user: dict = Depends(require_analyst_or_admin)):
    contents = await file.read()
    try:
        df_up = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {e}")

    is_valid, missing, meta = validate_csv_schema(df_up)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Missing required CSV columns: {', '.join(missing)}")

    seed_db_from_dataframe(df_up)
    train_and_evaluate_models(df_up)
    df_feat_up = engineer_features(get_all_transactions())
    for _, row in df_feat_up.iterrows():
        sc = score_transaction(row.to_dict(), STATE["threshold_approve"], STATE["threshold_review"])
        save_prediction(sc["transaction_id"], sc["fraud_probability"], sc["risk_score"], sc["risk_level"], sc["status"], sc["risk_signals"])

    return {
        "success": True,
        "meta": meta,
        "imported_rows": len(df_up)
    }


@app.get("/api/export/{export_type}")
def export_data(export_type: str, user: dict = Depends(require_active_user)):
    if export_type == "active":
        df = get_all_transactions()
        fname = f"active_{STATE['selected_dataset']}"
    elif export_type == "filtered":
        df = get_all_transactions()
        fname = "filtered_transactions.csv"
    elif export_type == "audit":
        df = get_all_audit_logs()
        fname = "audit_report.csv"
    else:
        raise HTTPException(status_code=400, detail="Invalid export type")

    csv_buf = io.StringIO()
    df.to_csv(csv_buf, index=False)
    csv_buf.seek(0)
    return StreamingResponse(
        io.BytesIO(csv_buf.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"}
    )


@app.post("/api/investigation/run")
def run_investigation(req: Dict[str, str], user: dict = Depends(require_analyst_or_admin)):
    tx_id = req.get("transaction_id")
    if not tx_id:
        raise HTTPException(status_code=400, detail="transaction_id is required")

    tx_row = get_transaction_by_id(tx_id)
    if not tx_row:
        raise HTTPException(status_code=404, detail=f"Transaction '{tx_id}' was not found in SQLite database.")

    cust_id = tx_row.get("customer_id")
    dev_id = tx_row.get("device_id")
    ts = tx_row.get("timestamp")
    cust_hist = get_customer_history(cust_id, limit=10) if cust_id else []
    dev_hist = get_device_history(dev_id, limit=10) if dev_id else []
    vel_stats = get_velocity_stats(cust_id, ts) if cust_id else {"tx_last_5min": 1, "tx_last_1hour": 1}

    df_f = engineer_features(pd.DataFrame([tx_row]))
    scored = score_transaction(df_f.iloc[0].to_dict(), STATE["threshold_approve"], STATE["threshold_review"])

    res = run_ai_investigation(
        transaction_id=tx_id,
        provider=STATE.get("byok_provider", "Google Gemini"),
        api_key=STATE.get("byok_key"),
        model_name=STATE.get("byok_model")
    )

    sources = list(dict.fromkeys(
        (res.get("evidence_sources") or []) + ["SQLite Database Telemetry", "XGBoost ML Engine"]
    ))

    return {
        "transaction": tx_row,
        "ml_score": scored,
        "customer_history": cust_hist,
        "device_history": dev_hist,
        "velocity": vel_stats,
        "investigation": res,
        "recommendation": res.get("recommendation", scored["status"]),
        "confidence": res.get("confidence", "High"),
        "crag_details": res.get("crag_details", {}),
        "srag_details": res.get("srag_details", {}),
        "final_explanation": res.get("final_explanation", ""),
        "sources": sources
    }


@app.get("/api/model-performance")
def get_model_performance(admin: dict = Depends(require_admin)):
    saved_thresh_str = get_setting("risk_score_cutoff_threshold", str(STATE.get("risk_score_cutoff_threshold", 50)))
    try:
        thresh = int(saved_thresh_str)
    except (ValueError, TypeError):
        thresh = 50

    STATE["risk_score_cutoff_threshold"] = thresh
    STATE["threshold_review"] = thresh

    payload = load_saved_model()
    if not payload or payload.get("threshold") != thresh:
        df_fallback = pd.read_csv(os.path.join(ROOT_DIR, "data", "datasets", STATE["selected_dataset"])) if os.path.exists(os.path.join(ROOT_DIR, "data", "datasets", STATE["selected_dataset"])) else get_all_transactions()
        payload = train_and_evaluate_models(df_fallback, thresh)

    metrics = payload["metrics"]
    all_res = payload.get("all_model_results", {})
    model_name = payload.get("model_name", "XGBoost Classifier")

    comparison = []
    if all_res:
        for n, r in all_res.items():
            comparison.append({
                "model": n,
                "precision": round(r["precision"] * 100, 1),
                "recall": round(r["recall"] * 100, 1),
                "f1": round(r["f1"], 3),
                "pr_auc": round(r["pr_auc"], 3),
                "fp": r["false_positives"],
                "fn": r["false_negatives"]
            })

    impact = calculate_cost_impact(metrics["false_positives"], metrics["false_negatives"], 2000.0, 35000.0)

    return {
        "threshold": thresh,
        "model_name": model_name,
        "metrics": metrics,
        "comparison": comparison,
        "confusion_matrix": metrics["confusion_matrix"],
        "cost_impact": impact
    }


@app.get("/api/model-performance/threshold")
def get_model_performance_threshold(user: dict = Depends(require_active_user)):
    saved_thresh_str = get_setting("risk_score_cutoff_threshold", str(STATE.get("risk_score_cutoff_threshold", 50)))
    try:
        thresh = int(saved_thresh_str)
    except (ValueError, TypeError):
        thresh = 50
    return {"threshold": thresh}


@app.post("/api/model-performance/threshold")
def update_model_performance_threshold(req: ThresholdUpdateReq, admin: dict = Depends(require_admin)):
    new_thresh = max(10, min(90, req.threshold))
    save_setting("risk_score_cutoff_threshold", str(new_thresh))
    STATE["risk_score_cutoff_threshold"] = new_thresh
    STATE["threshold_review"] = new_thresh

    # Re-evaluate current dataset model metrics with new threshold
    df_cur = pd.read_csv(os.path.join(ROOT_DIR, "data", "datasets", STATE["selected_dataset"])) if os.path.exists(os.path.join(ROOT_DIR, "data", "datasets", STATE["selected_dataset"])) else get_all_transactions()
    train_and_evaluate_models(df_cur, new_thresh)

    # Re-score transactions with updated threshold
    df_all = get_all_transactions()
    if not df_all.empty:
        df_feat = engineer_features(df_all)
        for _, row in df_feat.iterrows():
            sc = score_transaction(row.to_dict(), STATE["threshold_approve"], STATE["threshold_review"])
            save_prediction(sc["transaction_id"], sc["fraud_probability"], sc["risk_score"], sc["risk_level"], sc["status"], sc["risk_signals"])

    save_audit_log(
        tx_id="SYSTEM",
        risk_score=new_thresh,
        agent_action="UPDATE_RISK_THRESHOLD",
        tools_used=["Admin Model Performance Config"],
        rag_retrieved=["Risk Policy Configuration"],
        crag_result="Applied",
        srag_result="Updated",
        recommendation=f"Threshold updated to {new_thresh}%",
        final_explanation=f"Admin '{admin.get('username', 'admin')}' updated Fraud Risk Score Cutoff Threshold to {new_thresh}%."
    )


    return {
        "status": "success",
        "threshold": new_thresh,
        "message": f"Fraud Risk Score Cutoff Threshold updated to {new_thresh}%"
    }


@app.post("/api/model-performance/cost")
def calculate_custom_cost(req: CostCalcReq, admin: dict = Depends(require_admin)):
    payload = load_saved_model()
    saved_thresh = STATE.get("risk_score_cutoff_threshold", 50)
    if not payload:
        df_fallback = pd.read_csv(os.path.join(ROOT_DIR, "data", "datasets", STATE["selected_dataset"])) if os.path.exists(os.path.join(ROOT_DIR, "data", "datasets", STATE["selected_dataset"])) else get_all_transactions()
        payload = train_and_evaluate_models(df_fallback, saved_thresh)

    metrics = payload.get("metrics", {"false_positives": 12, "false_negatives": 6})

    base_fp = metrics.get("false_positives", 12)
    base_fn = metrics.get("false_negatives", 6)

    thresh = max(1, min(99, req.sim_threshold))
    
    sim_fp = max(0, int(round(base_fp * ((100 - thresh) / 50.0))))
    sim_fn = max(0, int(round(base_fn * (thresh / 50.0))))

    base_impact = calculate_cost_impact(base_fp, base_fn, req.fp_cost, req.fn_cost)
    sim_impact = calculate_cost_impact(sim_fp, sim_fn, req.fp_cost, req.fn_cost)

    cost_delta = sim_impact["total_risk_cost"] - base_impact["total_risk_cost"]

    return {
        "fp_cost": req.fp_cost,
        "fn_cost": req.fn_cost,
        "threshold": thresh,
        "base_fp": base_fp,
        "base_fn": base_fn,
        "sim_fp": sim_fp,
        "sim_fn": sim_fn,
        "base": base_impact,
        "simulated": sim_impact,
        "cost_delta": round(cost_delta, 2)
    }



@app.get("/api/audit-logs")
def get_audit_logs(admin: dict = Depends(require_admin)):
    df_logs = get_all_audit_logs()
    items = df_logs.to_dict(orient="records") if not df_logs.empty else []
    return {"logs": items}


@app.get("/api/ai/config")
def get_ai_config(admin: dict = Depends(require_admin)):
    cur_key = STATE.get("byok_key", "")
    masked_key = f"••••••••{cur_key[-4:]}" if cur_key and len(cur_key) >= 8 else ("••••" if cur_key else "")
    return {
        "provider": STATE["byok_provider"],
        "model": STATE["byok_model"],
        "masked_key": masked_key,
        "status": STATE["byok_status"],
        "status_msg": STATE["byok_status_msg"],
        "tech_details": STATE["byok_tech_details"]
    }


@app.get("/api/ai/models")
def get_ai_models(provider: str = Query("Google Gemini"), admin: dict = Depends(require_admin)):
    cur_key = STATE.get("byok_key", "")
    models = get_available_models(provider, cur_key)
    return {"provider": provider, "models": models}


@app.post("/api/ai/config")
def save_ai_config(req: AIConfigReq, admin: dict = Depends(require_admin)):
    is_valid, val_msg = validate_model_for_provider(req.provider, req.model)
    if not is_valid:
        raise HTTPException(status_code=400, detail=val_msg)

    STATE["byok_provider"] = req.provider
    if req.api_key is not None:
        STATE["byok_key"] = req.api_key.strip()
    STATE["byok_model"] = req.model

    ok, msg, tech = test_api_connection(req.provider, STATE["byok_key"], req.model)
    STATE["byok_status"] = "Connected" if ok else "Saved (Not Verified)"
    STATE["byok_status_msg"] = msg
    STATE["byok_tech_details"] = tech

    return get_ai_config(admin)


@app.post("/api/ai/test")
def test_ai_config(req: AIConfigReq, admin: dict = Depends(require_admin)):
    key = req.api_key.strip() if req.api_key else STATE.get("byok_key", "")
    ok, msg, tech = test_api_connection(req.provider, key, req.model)

    STATE["byok_provider"] = req.provider
    if req.api_key:
        STATE["byok_key"] = key
    STATE["byok_model"] = req.model
    STATE["byok_status"] = "Connected" if ok else "Connection Failed"
    STATE["byok_status_msg"] = msg
    STATE["byok_tech_details"] = tech

    return {
        "success": ok,
        "message": msg,
        "tech_details": tech,
        "config": get_ai_config(admin)
    }


@app.post("/api/copilot")
def chat_copilot(req: CopilotReq, user: dict = Depends(require_analyst_or_admin)):
    res = chat_with_copilot(
        user_query=req.user_query,
        target_tx_id=req.target_tx_id,
        provider=STATE.get("byok_provider", "Google Gemini"),
        api_key=STATE.get("byok_key"),
        model_name=STATE.get("byok_model")
    )
    return res


# ─────────────────────────────────────────────────────────────────────────────
# MIGRATION ROUTE ALIASES & DIRECT QUERY ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "RiskShield AI FastAPI Engine", "timestamp": datetime.datetime.now().isoformat()}

@app.get("/api/status")
def status_alias(user: dict = Depends(require_active_user)):
    return get_system_status(user)

@app.post("/api/datasets/switch")
def switch_dataset_alias(req: DatasetSwitchReq, user: dict = Depends(require_analyst_or_admin)):
    return switch_dataset(req, user)

@app.get("/api/transactions/{tx_id}/history/customer")
def get_customer_tx_history(tx_id: str, user: dict = Depends(require_active_user)):
    tx = get_transaction_by_id(tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail=f"Transaction '{tx_id}' not found.")
    cust_id = tx.get("customer_id")
    hist = get_customer_history(cust_id, limit=20) if cust_id else []
    return {"transaction_id": tx_id, "customer_id": cust_id, "history": hist}

@app.get("/api/transactions/{tx_id}/history/device")
def get_device_tx_history(tx_id: str, user: dict = Depends(require_active_user)):
    tx = get_transaction_by_id(tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail=f"Transaction '{tx_id}' not found.")
    dev_id = tx.get("device_id")
    hist = get_device_history(dev_id, limit=20) if dev_id else []
    return {"transaction_id": tx_id, "device_id": dev_id, "history": hist}

@app.post("/api/investigations/{tx_id}")
def run_investigation_by_path(tx_id: str, user: dict = Depends(require_analyst_or_admin)):
    return run_investigation({"transaction_id": tx_id}, user)

@app.get("/api/configuration")
def get_config_alias(admin: dict = Depends(require_admin)):
    return get_ai_config(admin)

@app.post("/api/configuration")
def save_config_alias(req: AIConfigReq, admin: dict = Depends(require_admin)):
    return save_ai_config(req, admin)

@app.get("/api/export/transactions")
def export_transactions_alias(user: dict = Depends(require_active_user)):
    return export_data("active", user)

@app.get("/api/export/audit-logs")
def export_audit_alias(admin: dict = Depends(require_admin)):
    return export_data("audit", admin)

@app.post("/api/import/transactions")
async def import_transactions_alias(file: UploadFile = File(...), user: dict = Depends(require_analyst_or_admin)):
    return await upload_transactions_csv(file, user)

@app.get("/api/customers/{customer_id}")
def get_customer_by_id_endpoint(customer_id: str, user: dict = Depends(require_active_user)):
    prof = get_customer_profile(customer_id)
    if not prof:
        raise HTTPException(status_code=404, detail=f"Customer '{customer_id}' not found.")
    txs = get_customer_history(customer_id, limit=20)
    return {"customer": prof, "transactions": txs}

@app.get("/api/customers/{customer_id}/transactions")
def get_customer_transactions_endpoint(customer_id: str, user: dict = Depends(require_active_user)):
    txs = get_customer_history(customer_id, limit=50)
    return {"customer_id": customer_id, "transactions": txs}

@app.get("/api/devices/{device_id}")
def get_device_by_id_endpoint(device_id: str, user: dict = Depends(require_active_user)):
    hist = get_device_history(device_id, limit=50)
    return {"device_id": device_id, "history": hist}

@app.get("/api/devices/{device_id}/transactions")
def get_device_transactions_endpoint(device_id: str, user: dict = Depends(require_active_user)):
    hist = get_device_history(device_id, limit=50)
    return {"device_id": device_id, "transactions": hist}

@app.get("/api/transactions/{tx_id}/customer")
def get_transaction_customer_endpoint(tx_id: str, user: dict = Depends(require_active_user)):
    tx = get_transaction_by_id(tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail=f"Transaction '{tx_id}' not found.")
    cust_id = tx.get("customer_id")
    prof = get_customer_profile(cust_id) if cust_id else None
    return {"transaction_id": tx_id, "customer_id": cust_id, "customer": prof}

@app.get("/api/transactions/{tx_id}/device")
def get_transaction_device_endpoint(tx_id: str, user: dict = Depends(require_active_user)):
    tx = get_transaction_by_id(tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail=f"Transaction '{tx_id}' not found.")
    dev_id = tx.get("device_id")
    hist = get_device_history(dev_id, limit=20) if dev_id else []
    return {"transaction_id": tx_id, "device_id": dev_id, "history": hist}

@app.get("/api/transactions/{tx_id}/audit")
def get_transaction_audit_endpoint(tx_id: str, admin: dict = Depends(require_admin)):
    from database import get_all_audit_logs, get_analyst_override_reason
    df_logs = get_all_audit_logs()
    target_logs = df_logs[df_logs["transaction_id"] == tx_id].to_dict(orient="records") if not df_logs.empty and "transaction_id" in df_logs.columns else []
    reason = get_analyst_override_reason(tx_id)
    return {"transaction_id": tx_id, "audit_logs": target_logs, "analyst_override_reason": reason}


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN ↔ ANALYST COMMUNICATION API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/communication/conversations")
def get_admin_conversations_endpoint(admin: dict = Depends(require_admin)):
    """Admin endpoint to retrieve all Analyst conversation threads."""
    convs = get_conversations_for_admin()
    return {"conversations": convs}


@app.get("/api/communication/conversation")
def get_conversation_messages_endpoint(
    analyst_id: Optional[int] = Query(None),
    user: dict = Depends(require_analyst_or_admin)
):
    """
    Retrieves messages for a conversation.
    Admin can specify analyst_id. Analyst gets their own conversation.
    Automatically marks unread messages as read.
    """
    user_role = user.get("role", "").lower()
    user_id = user.get("user_id")
    username = user.get("username")

    if user_role == "admin":
        target_analyst_id = analyst_id
        if not target_analyst_id:
            # Pick first available analyst
            convs = get_conversations_for_admin()
            if convs:
                target_analyst_id = convs[0]["analyst_id"]
            else:
                return {"conversation": None, "messages": []}
        
        target_user = get_user_by_id(target_analyst_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="Analyst user not found.")
        conv = get_or_create_conversation(target_analyst_id, target_user["username"])
    else: # analyst
        conv = get_or_create_conversation(user_id, username)

    conv_id = conv["conversation_id"]
    mark_messages_read(conv_id, user_role)
    msgs = get_messages_in_conversation(conv_id)

    return {
        "conversation": conv,
        "messages": msgs
    }


@app.post("/api/communication/send")
def send_communication_message_endpoint(
    req: SendMessageReq,
    user: dict = Depends(require_analyst_or_admin)
):
    """
    Sends a message in the Admin ↔ Analyst private conversation thread.
    """
    user_role = user.get("role", "").lower()
    user_id = user.get("user_id")
    username = user.get("username")

    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message text cannot be empty.")

    if user_role == "admin":
        if req.conversation_id:
            conv_id = req.conversation_id
        elif req.analyst_id:
            target_user = get_user_by_id(req.analyst_id)
            if not target_user:
                raise HTTPException(status_code=404, detail="Analyst not found.")
            conv = get_or_create_conversation(req.analyst_id, target_user["username"])
            conv_id = conv["conversation_id"]
        else:
            raise HTTPException(status_code=400, detail="Must specify conversation_id or analyst_id.")
    else: # analyst
        conv = get_or_create_conversation(user_id, username)
        conv_id = conv["conversation_id"]

    msg = send_message(
        conversation_id=conv_id,
        sender_id=user_id,
        sender_username=username,
        sender_role=user_role,
        message=req.message.strip(),
        msg_type=req.msg_type or "NORMAL_MESSAGE"
    )

    return {"status": "success", "message": msg}


@app.post("/api/communication/notify-api-key")
def notify_api_key_endpoint(user: dict = Depends(require_analyst_or_admin)):
    """
    Analyst endpoint to notify Admin that the LLM API key needs to be configured.
    Prevents duplicate spam if an OPEN request already exists.
    """
    user_role = user.get("role", "").lower()
    user_id = user.get("user_id")
    username = user.get("username")
    full_name = user.get("full_name") or username

    if user_role != "analyst":
        raise HTTPException(status_code=400, detail="Only Analyst role can trigger API key requests.")

    if has_open_api_key_request(user_id):
        return {
            "status": "duplicate",
            "message": "Admin has already been notified about this issue."
        }

    conv = get_or_create_conversation(user_id, username)

    msg_text = (
        f"AI Configuration Request\n\n"
        f"From: {full_name} (@{username})\n"
        f"Issue: LLM API key is missing or not configured\n"
        f"Request: Please configure the LLM API key in AI Settings so AI Copilot can be used."
    )

    msg = send_message(
        conversation_id=conv["conversation_id"],
        sender_id=user_id,
        sender_username=username,
        sender_role="analyst",
        message=msg_text,
        msg_type="API_KEY_REQUEST",
        status="OPEN"
    )

    # Save audit log
    save_audit_log(
        tx_id="SYSTEM",
        risk_score=0,
        agent_action="API_KEY_REQUEST_CREATED",
        tools_used=["Analyst AI Copilot Support"],
        rag_retrieved=["API Configuration Policy"],
        crag_result="Submitted",
        srag_result="Open",
        recommendation="NOTIFY_ADMIN",
        final_explanation=f"Analyst '{username}' submitted an API key configuration request to System Administrator."
    )

    return {
        "status": "success",
        "message": "Admin has been notified.",
        "request_message": msg
    }


@app.post("/api/communication/resolve-request")
def resolve_api_key_request_endpoint(
    req: ResolveRequestReq,
    admin: dict = Depends(require_admin)
):
    """
    Admin endpoint to mark an API_KEY_REQUEST as RESOLVED.
    """
    res = resolve_api_key_request(req.message_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"API Key Request #{req.message_id} not found.")

    save_audit_log(
        tx_id="SYSTEM",
        risk_score=0,
        agent_action="API_KEY_REQUEST_RESOLVED",
        tools_used=["Admin Support Center"],
        rag_retrieved=["API Configuration Policy"],
        crag_result="Resolved",
        srag_result="Active",
        recommendation="RESOLVE",
        final_explanation=f"Admin '{admin['username']}' marked API Key Request #{req.message_id} as RESOLVED."
    )

    return {
        "status": "success",
        "message": f"API Key Request #{req.message_id} marked as RESOLVED.",
        "request_message": res
    }


@app.get("/api/communication/unread-count")
def get_unread_count_endpoint(user: dict = Depends(require_active_user)):
    """
    Returns unread notification count for the current user for top bar bell badge.
    """
    cnt = get_unread_notification_count(user["user_id"], user["role"])
    return {"unread_count": cnt}


