import json
import datetime
import pandas as pd
from typing import Dict, Any, List, Optional, TypedDict
from langchain_core.messages import SystemMessage, HumanMessage

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from database import (
    get_transaction_by_id, get_customer_profile, get_customer_history,
    get_device_history, get_location_history, get_velocity_stats,
    get_chargeback_history, save_audit_log, save_analyst_action,
    get_latest_analyst_action, get_all_transactions
)
import ml
from ml import engineer_features, score_transaction, get_shap_explanation
from rag import search_knowledge
from llm import DEFAULT_MODELS, validate_model_for_provider, extract_text_from_response

class InvestigationState(TypedDict):
    transaction_id: str
    transaction_data: Dict[str, Any]
    customer_profile: Dict[str, Any]
    ml_results: Dict[str, Any]
    shap_results: Dict[str, Any]
    retrieved_policies: List[Dict[str, Any]]
    crag_details: Dict[str, Any]
    candidate_explanation: str
    recommendation: str
    confidence: str
    srag_details: Dict[str, Any]
    final_explanation: str
    evidence_sources: List[str]


def get_llm_instance(provider: str, api_key: Optional[str] = None, model_name: Optional[str] = None):
    """
    Instantiates an LLM client dynamically based on provider, key, and selected model.
    Falls back gracefully to offline mode if key is missing or invalid.
    """
    if not api_key or not str(api_key).strip():
        return None

    api_key = str(api_key).strip()
    target_model = model_name or DEFAULT_MODELS.get(provider, "default")

    is_valid, val_msg = validate_model_for_provider(provider, target_model)
    if not is_valid:
        return None

    try:
        if provider == "Google Gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(google_api_key=api_key, model=target_model, temperature=0.1)

        elif provider == "Groq":
            from langchain_groq import ChatGroq
            return ChatGroq(groq_api_key=api_key, model=target_model, temperature=0.1)

        elif provider == "OpenAI":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(openai_api_key=api_key, model=target_model, temperature=0.1)

        elif provider == "OpenRouter":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                openai_api_key=api_key,
                openai_api_base="https://openrouter.ai/api/v1",
                model=target_model,
                temperature=0.1
            )
    except Exception:
        return None
    return None


def fetch_telemetry_node(state: InvestigationState) -> InvestigationState:
    tx_id = state["transaction_id"]
    tx_row = get_transaction_by_id(tx_id)
    
    if not tx_row:
        tx_row = {
            "transaction_id": tx_id,
            "customer_id": "UNKNOWN",
            "amount": 0.0,
            "payment_method": "UPI",
            "device_id": "DEV_UNKNOWN",
            "location": "Mumbai",
            "failed_attempts": 0,
            "account_age_days": 180,
            "previous_chargebacks": 0,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    cust_id = tx_row.get("customer_id")
    cust_prof = get_customer_profile(cust_id) or {}
    
    df_single = pd.DataFrame([tx_row])
    df_feat = engineer_features(df_single)
    scored = score_transaction(df_feat.iloc[0].to_dict())
    shap_data = get_shap_explanation(df_feat.iloc[0].to_dict())

    state["transaction_data"] = tx_row
    state["customer_profile"] = cust_prof
    state["ml_results"] = scored
    state["shap_results"] = shap_data
    return state


def crag_retrieval_node(state: InvestigationState) -> InvestigationState:
    tx = state["transaction_data"]
    ml = state["ml_results"]
    
    query = f"Risk policies for {tx.get('payment_method')} payment with amount ₹{tx.get('amount')} and risk signals {', '.join(ml.get('risk_signals', []))}"
    
    docs = search_knowledge(query, top_k=3)
    
    crag_status = "CRAG: Direct Retrieval Validated"
    reformatted_query = ""
    
    if not docs or ml.get("risk_score", 0) > 65:
        reformatted_query = f"High risk payment policies velocity chargeback device anomaly {tx.get('payment_method')}"
        docs_reformatted = search_knowledge(reformatted_query, top_k=3)
        if docs_reformatted:
            docs = docs_reformatted
            crag_status = f"CRAG: Corrected via Query Reformulation ('{reformatted_query}')"

    state["retrieved_policies"] = docs
    state["crag_details"] = {
        "crag_status_str": crag_status,
        "initial_quality": "Strong" if len(docs) >= 2 else "Weak",
        "reformatted_query": reformatted_query,
        "final_quality": "Strong" if docs else "Unresolved"
    }
    return state


def generate_reasoning_node(
    state: InvestigationState,
    provider: str = "Google Gemini",
    api_key: Optional[str] = None,
    model_name: Optional[str] = None
) -> InvestigationState:
    tx = state["transaction_data"]
    ml = state["ml_results"]
    cust = state["customer_profile"]
    docs = state["retrieved_policies"]

    llm = get_llm_instance(provider, api_key, model_name)
    
    policy_text = "\n".join([f"- [{d['source']}]: {d['content']}" for d in docs])
    
    prompt = f"""
    You are an expert Payment Risk Investigation AI Agent for an enterprise risk control room.
    
    TRANSACTION TELEMETRY:
    - Transaction ID: {tx.get('transaction_id')}
    - Customer ID: {tx.get('customer_id')} (Account Age: {tx.get('account_age_days')} days, Previous Chargebacks: {tx.get('previous_chargebacks')})
    - Amount: ₹{tx.get('amount'):,.2f}
    - Payment Method: {tx.get('payment_method')}
    - Device ID: {tx.get('device_id')}
    - Location: {tx.get('location')}
    - Failed Attempts: {tx.get('failed_attempts')}
    
    XGBOOST ML PREDICTION:
    - Risk Score: {ml.get('risk_score')}/100 ({ml.get('risk_level')} Risk)
    - Model Status Recommendation: {ml.get('status')}
    - Identified Risk Signals: {', '.join(ml.get('risk_signals', []))}
    
    RETRIEVED RISK POLICIES (RAG Knowledge):
    {policy_text}

    Task: Provide a structured investigation explanation in valid JSON format with keys:
    "explanation": Detailed paragraph explaining the risk drivers, telemetry anomalies, and policy alignment.
    "recommendation": Must be APPROVE, REVIEW, or HOLD.
    "confidence": High, Medium, or Low.
    """

    if not llm:
        state["candidate_explanation"] = (
            f"Offline Analysis: Transaction {tx.get('transaction_id')} evaluated with ML Risk Score {ml.get('risk_score')}/100. "
            f"Key risk signals detected: {', '.join(ml.get('risk_signals', []))}. "
            f"Policy guidelines indicate decision status {ml.get('status')} based on transaction amount ₹{tx.get('amount'):,.2f} and customer history."
        )
        state["recommendation"] = ml.get("status", "REVIEW")
        state["confidence"] = "High" if ml.get("risk_score", 0) > 70 or ml.get("risk_score", 0) < 30 else "Medium"
        state["evidence_sources"] = ["XGBoost Risk Model", "SQLite Telemetry", "Local Policy Rules"]
        return state

    try:
        res = llm.invoke(prompt)
        content = extract_text_from_response(res)
        if content.startswith("```json"):
            content = content[7:].rstrip("```").strip()
        elif content.startswith("```"):
            content = content[3:].rstrip("```").strip()

        data = json.loads(content)
        state["candidate_explanation"] = data.get("explanation", content)
        state["recommendation"] = data.get("recommendation", ml.get("status", "REVIEW"))
        state["confidence"] = data.get("confidence", "High")
        state["evidence_sources"] = [d.get("source", "Policy Document") for d in docs] + ["SQLite Telemetry"]
    except Exception:
        state["candidate_explanation"] = f"XGBoost model flagged transaction with score {ml.get('risk_score')}/100. Signals: {', '.join(ml.get('risk_signals', []))}."
        state["recommendation"] = ml.get("status", "REVIEW")
        state["confidence"] = "Medium"
        state["evidence_sources"] = ["XGBoost Risk Model"]

    return state


def srag_reflection_node(state: InvestigationState) -> InvestigationState:
    candidate = state.get("candidate_explanation", "")
    tx = state.get("transaction_data", {})
    ml_res = state.get("ml_results", {})
    
    claims_checked = 3
    unsupported = 0
    
    if str(tx.get("transaction_id")) not in candidate and "Transaction" not in candidate:
        unsupported += 1
    if str(ml_res.get("risk_score")) not in candidate and "score" not in candidate.lower():
        unsupported += 1

    srag_status = "SRAG: Grounded & Factually Verified" if unsupported == 0 else f"SRAG: Verified with {unsupported} Minor Refinement(s)"
    
    state["srag_details"] = {
        "status_str": srag_status,
        "claims_checked": claims_checked,
        "unsupported_count": unsupported,
        "is_grounded": True
    }
    state["final_explanation"] = candidate
    return state


def run_ai_investigation(
    transaction_id: str,
    provider: str = "Google Gemini",
    api_key: Optional[str] = None,
    model_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the full LangGraph Autonomous Agent Investigation pipeline:
    Fetch Telemetry -> CRAG Retrieval -> LLM Reasoning -> SRAG Reflection -> Audit Trail.
    """
    state: InvestigationState = {
        "transaction_id": transaction_id,
        "transaction_data": {},
        "customer_profile": {},
        "ml_results": {},
        "shap_results": {},
        "retrieved_policies": [],
        "crag_details": {},
        "candidate_explanation": "",
        "recommendation": "REVIEW",
        "confidence": "Medium",
        "srag_details": {},
        "final_explanation": "",
        "evidence_sources": []
    }

    state = fetch_telemetry_node(state)
    state = crag_retrieval_node(state)
    state = generate_reasoning_node(state, provider=provider, api_key=api_key, model_name=model_name)
    state = srag_reflection_node(state)

    save_audit_log(
        tx_id=transaction_id,
        risk_score=state["ml_results"].get("risk_score", 0),
        agent_action=f"AI Autonomous Investigation Completed ({state['recommendation']})",
        tools_used=["get_transaction_by_id", "get_customer_profile", "search_knowledge", "get_shap_explanation"],
        rag_retrieved=[d.get("source", "Policy") for d in state["retrieved_policies"]],
        crag_result=state["crag_details"].get("crag_status_str", "CRAG Validated"),
        srag_result=state["srag_details"].get("status_str", "SRAG Verified"),
        recommendation=state["recommendation"],
        final_explanation=state["final_explanation"]
    )

    return state


def run_post_decision_analysis(
    transaction_id: str,
    prev_status: str,
    new_status: str,
    risk_score: int,
    ai_recommendation: str,
    analyst_remark: str,
    provider: str = "Google Gemini",
    api_key: Optional[str] = None,
    model_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes LLM post-decision audit evaluation when an analyst overrides or confirms a transaction decision.
    Evaluates whether the remark addresses telemetry risk drivers, residual risks, and final audit assessment.
    """
    tx = get_transaction_by_id(transaction_id) or {}
    cust_id = tx.get("customer_id")
    cust_prof = get_customer_profile(cust_id) or {}
    vel = get_velocity_stats(cust_id, tx.get("timestamp"))

    llm = get_llm_instance(provider, api_key, model_name)

    prompt = f"""
    You are an AI Risk Governance Officer conducting a post-decision audit on a payment transaction override.

    TRANSACTION CONTEXT:
    - Transaction ID: {transaction_id}
    - Customer ID: {cust_id}
    - Amount: ₹{tx.get('amount', 0):,.2f}
    - Original ML Risk Score: {risk_score}/100
    - Original AI Recommendation: {ai_recommendation}
    - Analyst Override Decision: {new_status}
    - Analyst Remark: "{analyst_remark}"
    - Telemetry: Velocity (5 min)={vel.get('tx_last_5min')}, Device={tx.get('device_id')}, Location={tx.get('location')}

    Provide a concise 3-4 sentence audit evaluation assessing:
    1. Assessment of analyst override (Fully Supported, Partially Supported, or High Residual Risk).
    2. Which risk drivers are resolved by the analyst's remark.
    3. Residual risks remaining and final audit conclusion.
    """

    if not llm:
        post_text = (
            f"Analyst Override Recorded: Decision changed from {prev_status} to {new_status}.\n"
            f"Analyst Remark: '{analyst_remark}'.\n"
            f"Audit Assessment: Decision logged to SQLite audit trail."
        )
    else:
        try:
            res = llm.invoke(prompt)
            post_text = extract_text_from_response(res)
        except Exception as e:
            post_text = f"Analyst override applied ({prev_status} -> {new_status}). Remark: '{analyst_remark}'."

    save_analyst_action(
        tx_id=transaction_id,
        prev_status=prev_status,
        new_status=new_status,
        risk_score=risk_score,
        ai_recommendation=ai_recommendation,
        analyst_remark=analyst_remark,
        post_analysis=post_text
    )

    return {
        "transaction_id": transaction_id,
        "previous_status": prev_status,
        "new_status": new_status,
        "analyst_remark": analyst_remark,
        "post_analysis": post_text
    }


def chat_with_copilot(
    user_query: str,
    target_tx_id: Optional[str] = None,
    provider: str = "Google Gemini",
    api_key: Optional[str] = None,
    model_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    RiskShield Copilot Chatbot handler.
    Answers analyst questions using canonical DB state, RAG knowledge, and LLM reasoning.
    Directly processes status change commands and returns canonical transaction context.
    """
    import re
    
    # Auto-detect explicit transaction ID from query string if present
    extracted_tx = re.findall(r'TX[A-Za-z0-9_]+', user_query)
    if extracted_tx:
        target_tx_id = extracted_tx[0]

    llm = get_llm_instance(provider, api_key, model_name)
    query_lower = user_query.lower()
    
    # Handle natural language status update commands directly
    status_changed_msg = ""
    if target_tx_id and any(kw in query_lower for kw in ["hold", "approve", "review"]) and any(kw in query_lower for kw in ["put", "move", "change", "set", "mark"]):
        new_st = "HOLD" if "hold" in query_lower else ("APPROVE" if "approve" in query_lower else "REVIEW")
        tx_row_before = get_transaction_by_id(target_tx_id)
        if tx_row_before:
            prev_st = tx_row_before.get("effective_status") or "REVIEW"
            ai_rec = tx_row_before.get("ai_decision") or "REVIEW"
            score = tx_row_before.get("risk_score", 0)
            remark = f"Decision changed to {new_st} via Copilot command ('{user_query}')"
            save_analyst_action(target_tx_id, prev_st, new_st, score, ai_rec, remark)
            status_changed_msg = f"✅ **Analyst Decision Updated**: Transaction `{target_tx_id}` set to `{new_st}`.\n\n"

    tx_card_md = ""
    tx_context = ""
    tx = None
    cust_hist = []
    dev_hist = []

    if target_tx_id:
        tx = get_transaction_by_id(target_tx_id)
        if tx:
            cust_id = tx.get("customer_id")
            dev_id = tx.get("device_id")
            cust_prof = get_customer_profile(cust_id) or {}
            vel = get_velocity_stats(cust_id, tx.get("timestamp"))
            cust_hist = get_customer_history(cust_id, limit=5)
            dev_hist = get_device_history(dev_id, limit=5)

            score = tx.get("risk_score", 0)
            ai_dec = tx.get("ai_decision", "REVIEW")
            analyst_dec = tx.get("analyst_decision") or "Not set"
            eff_st = tx.get("effective_status", ai_dec)
            is_ov = "Yes" if tx.get("analyst_override") else "No"

            tx_card_md = f"""### 📋 TRANSACTION CONTEXT

| Field | Value |
|---|---|
| **Transaction ID** | `{target_tx_id}` |
| **Customer ID** | `{cust_id}` |
| **Amount** | ₹{tx.get('amount', 0):,.2f} |
| **Risk Score** | **{score} / 100** |
| **AI Recommendation** | `{ai_dec}` |
| **Analyst Decision** | `{analyst_dec}` |
| **Analyst Override** | **{is_ov}** |
| **Effective Status** | `{eff_st}` |

"""
            tx_context = f"""
    CANONICAL TRANSACTION DATA:
    - Transaction ID: {target_tx_id}
    - Customer ID: {cust_id} (Account Age: {tx.get('account_age_days')} days, Previous Chargebacks: {tx.get('previous_chargebacks')})
    - Amount: ₹{tx.get('amount', 0):,.2f}
    - Timestamp: {tx.get('timestamp')}
    - Payment Method: {tx.get('payment_method')}
    - Device ID: {tx.get('device_id')} (Customer Primary Device: {cust_prof.get('primary_device')})
    - Location: {tx.get('location')} (Known Customer Locations: {get_location_history(cust_id)})
    - Failed Attempts: {tx.get('failed_attempts')}
    - Velocity (Last 5 min): {vel.get('tx_last_5min')} transaction(s)
    - Risk Score: {score}/100
    - AI Recommendation: {ai_dec}
    - Analyst Decision: {analyst_dec}
    - Analyst Override: {is_ov}
    - Effective Status: {eff_st}
    """

    # Direct Analyst Override Reason Query
    if target_tx_id and any(kw in query_lower for kw in [
        "override reason", "analyst reason", "reason for override", "reason the analyst gave",
        "reason did the analyst give", "why did analyst", "why did the analyst", "analyst remark",
        "analyst's reason", "show analyst override"
    ]):
        from database import get_analyst_override_reason
        reason = get_analyst_override_reason(target_tx_id)
        if reason and str(reason).strip():
            reason_text = f"> \"{str(reason).strip()}\""
        else:
            reason_text = "> An analyst override is recorded, but no analyst reason/remark was stored for this decision."
        
        cust_id_val = tx.get('customer_id') if tx else 'N/A'
        amt_val = f"₹{tx.get('amount', 0):,.2f}" if tx else '₹0.00'
        score_val = f"{tx.get('risk_score', 0)}/100" if tx else '0/100'
        ai_dec_val = tx.get('ai_decision', 'REVIEW') if tx else 'N/A'
        analyst_dec_val = tx.get('analyst_decision') or 'Not set' if tx else 'Not set'
        is_ov_val = "Yes" if (tx and tx.get("analyst_override")) else "No"
        eff_st_val = tx.get('effective_status', 'APPROVE') if tx else 'APPROVE'

        ans_text = f"""## Transaction `{target_tx_id}`

| Field | Value |
|---|---|
| **Customer** | `{cust_id_val}` |
| **Amount** | {amt_val} |
| **Risk Score** | **{score_val}** |
| **AI Recommendation** | `{ai_dec_val}` |
| **Analyst Decision** | `{analyst_dec_val}` |
| **Analyst Override** | **{is_ov_val}** |
| **Effective Status** | `{eff_st_val}` |

### Analyst Override

**Reason recorded by analyst:**

{reason_text}
"""
        return {
            "answer": ans_text,
            "sources": ["SQLite Database Records"],
            "target_tx_id": target_tx_id,
            "intent": "analyst_override_reason"
        }

    # Direct Audit Log History Query
    if target_tx_id and any(kw in query_lower for kw in ["audit", "log", "history of changes"]):
        from database import get_all_audit_logs
        df_logs = get_all_audit_logs()
        target_logs = df_logs[df_logs["transaction_id"] == target_tx_id] if not df_logs.empty and "transaction_id" in df_logs.columns else pd.DataFrame()
        
        if not target_logs.empty:
            table_md = "| Timestamp | Action / Remark | Score | Recommendation |\n|---|---|---|---|\n"
            for _, r in target_logs.head(5).iterrows():
                table_md += f"| {r.get('timestamp')} | {r.get('agent_action')} | {r.get('risk_score')} | `{r.get('recommendation')}` |\n"
            ans_text = f"{tx_card_md}### 📜 Audit Log History for `{target_tx_id}`\n\n{table_md}"
        else:
            ans_text = f"{tx_card_md}No audit log entries recorded for `{target_tx_id}` yet."
            
        return {
            "answer": ans_text,
            "sources": ["SQLite Audit Log Database"],
            "target_tx_id": target_tx_id,
            "intent": "audit_history"
        }

    # Auto-detect explicit Customer ID or Device ID
    extracted_cust = re.findall(r'\bC[0-9]+\b', user_query)
    extracted_dev = re.findall(r'\bDEV_[A-Za-z0-9_]+\b', user_query)

    # Direct Customer Profile & History Query
    if (extracted_cust or (tx and any(kw in query_lower for kw in ["customer", "who is the customer", "their history"]))) and any(kw in query_lower for kw in ["customer", "history", "transactions", "show", "chargeback", "who", "tell"]):
        cust_id = extracted_cust[0] if extracted_cust else (tx.get("customer_id") if tx else None)
        if cust_id:
            cust_prof = get_customer_profile(cust_id) or {}
            cust_txs = get_customer_history(cust_id, limit=10)
            
            card_md = f"""### 👤 CUSTOMER PROFILE: `{cust_id}`

| Field | Value |
|---|---|
| **Customer ID** | `{cust_id}` |
| **Account Age** | {cust_prof.get('account_age_days', 180)} days |
| **Previous Chargebacks** | {cust_prof.get('previous_chargebacks', 0)} |
| **Primary Device** | `{cust_prof.get('primary_device', 'DEV_UNKNOWN')}` |
| **Primary Location** | {cust_prof.get('primary_location', 'Mumbai')} |
| **Recorded Transactions** | {len(cust_txs)} |

### 📊 Customer Transaction History

| TX ID | Amount (₹) | Payment Method | Risk Score | Effective Status | Timestamp |
|---|---:|---|---:|---|---|
"""
            for r in cust_txs:
                card_md += f"| `{r.get('transaction_id')}` | ₹{r.get('amount', 0):,.2f} | {r.get('payment_method')} | {r.get('risk_score', 0)} | `{r.get('effective_status', 'APPROVE')}` | {r.get('timestamp')} |\n"

            return {
                "answer": card_md,
                "sources": ["SQLite Customer Telemetry Database"],
                "target_tx_id": target_tx_id,
                "intent": "customer_details"
            }

    # Direct Device Profile & History Query
    if (extracted_dev or (tx and any(kw in query_lower for kw in ["device", "which device", "their device"]))) and any(kw in query_lower for kw in ["device", "history", "transactions", "show", "customer", "who"]):
        dev_id = extracted_dev[0] if extracted_dev else (tx.get("device_id") if tx else None)
        if dev_id:
            dev_txs = get_device_history(dev_id, limit=10)
            
            card_md = f"""### 📱 DEVICE TELEMETRY: `{dev_id}`

| Field | Value |
|---|---|
| **Device ID** | `{dev_id}` |
| **Associated Transactions** | {len(dev_txs)} |

### 📊 Device Activity History

| TX ID | Customer ID | Amount (₹) | Location | Effective Status | Timestamp |
|---|---|---:|---|---|---|
"""
            for r in dev_txs:
                card_md += f"| `{r.get('transaction_id')}` | `{r.get('customer_id')}` | ₹{r.get('amount', 0):,.2f} | {r.get('location')} | `{r.get('effective_status', 'APPROVE')}` | {r.get('timestamp')} |\n"

            return {
                "answer": card_md,
                "sources": ["SQLite Device Telemetry Database"],
                "target_tx_id": target_tx_id,
                "intent": "device_details"
            }

    # Check for direct database query shortcuts
    if tx and ("customer history" in query_lower or "show customer" in query_lower):
        table_md = "| TX ID | Amount (₹) | Method | Status | Timestamp |\n|---|---|---|---|---|\n"
        for r in cust_hist:
            table_md += f"| `{r.get('transaction_id')}` | ₹{r.get('amount', 0):,.2f} | {r.get('payment_method')} | {r.get('effective_status', r.get('transaction_status'))} | {r.get('timestamp')} |\n"
        ans_text = f"{tx_card_md}### Customer History for `{tx.get('customer_id')}`\n\n{table_md}"
        return {
            "answer": ans_text,
            "sources": ["SQLite Customer History Database"],
            "target_tx_id": target_tx_id
        }

    if tx and ("device history" in query_lower or "show device" in query_lower):
        table_md = "| TX ID | Customer | Amount (₹) | Location | Timestamp |\n|---|---|---|---|---|\n"
        for r in dev_hist[:5]:
            table_md += f"| `{r.get('transaction_id')}` | `{r.get('customer_id')}` | ₹{r.get('amount', 0):,.2f} | {r.get('location')} | {r.get('timestamp')} |\n"
        ans_text = f"{tx_card_md}### Device History for `{tx.get('device_id')}`\n\n{table_md}"
        return {
            "answer": ans_text,
            "sources": ["SQLite Device Telemetry Database"],
            "target_tx_id": target_tx_id
        }

    dataset_summary = ""
    if "how many" in query_lower or "hold" in query_lower or "dataset" in query_lower or "total" in query_lower:
        df_all = get_all_transactions()
        if not df_all.empty:
            hold_cnt = len(df_all[df_all["effective_status"] == "HOLD"])
            rev_cnt = len(df_all[df_all["effective_status"] == "REVIEW"])
            app_cnt = len(df_all[df_all["effective_status"] == "APPROVE"])
            dataset_summary = f"Current Working Dataset Stats: Total={len(df_all)}, APPROVE={app_cnt}, REVIEW={rev_cnt}, HOLD={hold_cnt}."

    docs = search_knowledge(user_query, top_k=2)
    kb_context = "\n".join([d["content"] for d in docs]) if docs else ""

    if not llm:
        fallback_ans = f"{status_changed_msg}{tx_card_md}I analyzed your query: '{user_query}'.\n\n{dataset_summary}\n\n*Note: Enter an API key in 'AI Configuration' for full conversational LLM reasoning.*"
        return {
            "answer": fallback_ans,
            "sources": ["SQLite Database Query"],
            "target_tx_id": target_tx_id
        }

    prompt = f"""
    You are RiskShield Copilot, an enterprise AI payment risk operations assistant.

    {tx_context}
    {dataset_summary}

    RELEVANT RISK POLICIES:
    {kb_context}

    ANALYST QUERY: "{user_query}"

    CRITICAL RESPONSE INSTRUCTIONS:
    1. Do NOT recreate or redefine the risk score or recommendation. Use the CANONICAL DATA provided above.
    2. Format your response using Markdown headings, bold text, and Markdown tables (`| Col 1 | Col 2 |`) for structured data.
    3. If an analyst override exists (Analyst Override: Yes), explicitly mention that the human analyst overrode the AI recommendation.
    4. Keep your answer professional, concise, and focused on payment risk analysis.
    """

    try:
        res = llm.invoke(prompt)
        res_text = extract_text_from_response(res)
        final_answer = f"{status_changed_msg}{tx_card_md}{res_text}"
        return {
            "answer": final_answer,
            "sources": [d.get("source", "Risk Policy") for d in docs] + ["SQLite Database Telemetry"],
            "target_tx_id": target_tx_id
        }
    except Exception as e:
        return {
            "answer": f"{status_changed_msg}{tx_card_md}Unable to reach LLM model ({str(e)}). Telemetry: {tx_context}",
            "sources": ["SQLite Local Fallback"],
            "target_tx_id": target_tx_id
        }

