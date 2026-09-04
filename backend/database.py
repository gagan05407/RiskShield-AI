import sqlite3
import os
import pandas as pd
import datetime
from typing import Dict, Any, List, Optional

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT_DIR, "riskshield.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Creates SQLite tables for customers, transactions, predictions, investigations, audit_logs, and analyst_actions.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        customer_id TEXT PRIMARY KEY,
        account_age_days INTEGER,
        previous_chargebacks INTEGER,
        primary_device TEXT,
        primary_location TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id TEXT PRIMARY KEY,
        customer_id TEXT,
        timestamp TEXT,
        amount REAL,
        payment_method TEXT,
        device_id TEXT,
        location TEXT,
        failed_attempts INTEGER,
        account_age_days INTEGER,
        previous_chargebacks INTEGER,
        transaction_status TEXT,
        is_fraud INTEGER,
        is_new_tx INTEGER DEFAULT 0,
        analyst_decision TEXT,
        analyst_remark TEXT,
        analyst_action_timestamp TEXT
    )
    """)

    cursor.execute("PRAGMA table_info(transactions)")
    existing_cols = [row["name"] for row in cursor.fetchall()]
    
    if "is_new_tx" not in existing_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN is_new_tx INTEGER DEFAULT 0")
    if "analyst_decision" not in existing_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN analyst_decision TEXT")
    if "analyst_remark" not in existing_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN analyst_remark TEXT")
    if "analyst_action_timestamp" not in existing_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN analyst_action_timestamp TEXT")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        transaction_id TEXT PRIMARY KEY,
        fraud_probability REAL,
        risk_score INTEGER,
        risk_level TEXT,
        status TEXT,
        risk_signals TEXT,
        predicted_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS investigations (
        investigation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id TEXT,
        risk_score INTEGER,
        recommendation TEXT,
        summary TEXT,
        full_explanation TEXT,
        evidence_sources TEXT,
        crag_status TEXT,
        srag_status TEXT,
        created_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        transaction_id TEXT,
        risk_score INTEGER,
        agent_action TEXT,
        tools_used TEXT,
        rag_retrieved TEXT,
        crag_result TEXT,
        srag_result TEXT,
        recommendation TEXT,
        final_explanation TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS analyst_actions (
        action_id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id TEXT,
        timestamp TEXT,
        previous_status TEXT,
        new_status TEXT,
        risk_score INTEGER,
        ai_recommendation TEXT,
        analyst_action TEXT,
        analyst_remark TEXT,
        post_analysis TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'analyst',
        full_name TEXT,
        status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL',
        created_at TEXT
    )
    """)

    cursor.execute("PRAGMA table_info(users)")
    user_cols = [row["name"] for row in cursor.fetchall()]
    if "status" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL'")

    # Ensure admin user is always ACTIVE
    cursor.execute("UPDATE users SET status = 'ACTIVE' WHERE username = 'admin' OR role = 'admin'")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conversations (
        conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        analyst_id INTEGER NOT NULL UNIQUE,
        analyst_username TEXT NOT NULL,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        sender_id INTEGER NOT NULL,
        sender_username TEXT NOT NULL,
        sender_role TEXT NOT NULL,
        message TEXT NOT NULL,
        msg_type TEXT NOT NULL DEFAULT 'NORMAL_MESSAGE',
        status TEXT DEFAULT NULL,
        is_read INTEGER NOT NULL DEFAULT 0,
        created_at TEXT,
        resolved_at TEXT DEFAULT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()
    conn.close()


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row and row["value"] is not None:
        return str(row["value"])
    return default


def save_setting(key: str, value: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO settings (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, str(value)))
    conn.commit()
    conn.close()



def seed_db_from_dataframe(df: pd.DataFrame):
    """
    Populates SQLite database directly from a pandas DataFrame.
    Preserves any user-created new transactions across re-seeds.
    """
    init_db()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM transactions WHERE is_new_tx = 0 OR is_new_tx IS NULL")
    cursor.execute("DELETE FROM customers")

    transactions_data = []
    for _, row in df.iterrows():
        transactions_data.append((
            str(row["transaction_id"]),
            str(row["customer_id"]),
            str(row["timestamp"]),
            float(row["amount"]),
            str(row["payment_method"]),
            str(row["device_id"]),
            str(row["location"]),
            int(row.get("failed_attempts", 0)),
            int(row.get("account_age_days", 180)),
            int(row.get("previous_chargebacks", 0)),
            str(row.get("transaction_status", "current")),
            int(row.get("is_fraud", 0)),
            0, # is_new_tx
            None, # analyst_decision
            None, # analyst_remark
            None  # analyst_action_timestamp
        ))

    cursor.executemany("""
    INSERT OR REPLACE INTO transactions (
        transaction_id, customer_id, timestamp, amount, payment_method, device_id, location,
        failed_attempts, account_age_days, previous_chargebacks, transaction_status, is_fraud,
        is_new_tx, analyst_decision, analyst_remark, analyst_action_timestamp
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, transactions_data)

    cursor.execute("SELECT * FROM transactions")
    all_rows = cursor.fetchall()
    df_all = pd.DataFrame([dict(r) for r in all_rows]) if all_rows else df

    cust_groups = df_all.groupby("customer_id")
    cust_data = []
    for c_id, group in cust_groups:
        mode_dev = group["device_id"].mode()[0] if not group["device_id"].mode().empty else group["device_id"].iloc[0]
        mode_loc = group["location"].mode()[0] if not group["location"].mode().empty else group["location"].iloc[0]
        age = int(group["account_age_days"].iloc[0]) if "account_age_days" in group else 180
        cb = int(group["previous_chargebacks"].iloc[0]) if "previous_chargebacks" in group else 0
        cust_data.append((str(c_id), age, cb, str(mode_dev), str(mode_loc)))

    cursor.executemany("""
    INSERT OR REPLACE INTO customers VALUES (?, ?, ?, ?, ?)
    """, cust_data)

    conn.commit()
    conn.close()


def seed_db_from_csv(csv_path: str):
    """
    Populates SQLite database from a transactions CSV dataset path.
    """
    if not os.path.exists(csv_path):
        return

    df = pd.read_csv(csv_path)
    seed_db_from_dataframe(df)


def add_new_transaction(tx_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inserts a newly created transaction into SQLite and updates customer profile.
    """
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    tx_id = str(tx_dict["transaction_id"])
    cust_id = str(tx_dict["customer_id"])
    ts = str(tx_dict.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    amt = float(tx_dict["amount"])
    pm = str(tx_dict.get("payment_method", "UPI"))
    dev = str(tx_dict.get("device_id", "DEV_NEW"))
    loc = str(tx_dict.get("location", "Mumbai"))
    failed_att = int(tx_dict.get("failed_attempts", 0))
    
    cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (cust_id,))
    cust_row = cursor.fetchone()
    if cust_row:
        age_days = int(cust_row["account_age_days"])
        prev_cb = int(cust_row["previous_chargebacks"])
    else:
        age_days = int(tx_dict.get("account_age_days", 90))
        prev_cb = int(tx_dict.get("previous_chargebacks", 0))
        cursor.execute("""
        INSERT INTO customers VALUES (?, ?, ?, ?, ?)
        """, (cust_id, age_days, prev_cb, dev, loc))

    cursor.execute("""
    INSERT OR REPLACE INTO transactions (
        transaction_id, customer_id, timestamp, amount, payment_method, device_id, location,
        failed_attempts, account_age_days, previous_chargebacks, transaction_status, is_fraud,
        is_new_tx, analyst_decision, analyst_remark, analyst_action_timestamp
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (tx_id, cust_id, ts, amt, pm, dev, loc, failed_att, age_days, prev_cb, "current", 0, 1, None, None, None))

    conn.commit()
    conn.close()

    return get_transaction_by_id(tx_id)


def get_transaction_by_id(transaction_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT t.*, p.fraud_probability, p.risk_score, p.risk_level, p.status as model_status, p.risk_signals
    FROM transactions t
    LEFT JOIN predictions p ON t.transaction_id = p.transaction_id
    WHERE t.transaction_id = ?
    """, (transaction_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    
    ai_dec = d.get("model_status") or "REVIEW"
    analyst_dec = d.get("analyst_decision")
    eff_status = analyst_dec if (analyst_dec and str(analyst_dec).strip() != "") else ai_dec
    is_override = bool(analyst_dec and str(analyst_dec).strip() != "" and analyst_dec != ai_dec)
    
    d["ai_decision"] = ai_dec
    d["analyst_decision"] = analyst_dec
    d["analyst_override"] = is_override
    d["analyst_reason"] = d.get("analyst_remark") or ""
    d["effective_status"] = eff_status
    d["risk_score"] = int(d.get("risk_score")) if (d.get("risk_score") is not None and str(d.get("risk_score")).isdigit()) else 0
    return d


def get_customer_profile(customer_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_customer_history(customer_id: str, limit: int = 15) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT t.*, p.risk_score, p.status as model_status
    FROM transactions t
    LEFT JOIN predictions p ON t.transaction_id = p.transaction_id
    WHERE t.customer_id = ?
    ORDER BY t.timestamp DESC
    LIMIT ?
    """, (customer_id, limit))
    rows = cursor.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["effective_status"] = d.get("analyst_decision") or d.get("model_status") or "APPROVE"
        result.append(d)
    return result


def get_device_history(device_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT t.transaction_id, t.customer_id, t.timestamp, t.amount, t.payment_method, t.location, t.is_fraud, t.analyst_decision, p.risk_score, p.status as model_status
    FROM transactions t
    LEFT JOIN predictions p ON t.transaction_id = p.transaction_id
    WHERE t.device_id = ?
    ORDER BY t.timestamp DESC
    LIMIT ?
    """, (device_id, limit))
    rows = cursor.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["effective_status"] = d.get("analyst_decision") or d.get("model_status") or "APPROVE"
        result.append(d)
    return result


def get_location_history(customer_id: str) -> List[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT location FROM transactions WHERE customer_id = ?",
        (customer_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [r["location"] for r in rows]


def get_velocity_stats(customer_id: str, timestamp_str: str = None) -> Dict[str, int]:
    conn = get_connection()
    cursor = conn.cursor()
    
    if not timestamp_str:
        cursor.execute("SELECT COUNT(*) as cnt FROM transactions WHERE customer_id = ?", (customer_id,))
        total_cnt = cursor.fetchone()["cnt"]
        conn.close()
        return {"tx_last_5min": max(1, total_cnt // 15), "tx_last_1hour": max(1, total_cnt // 5)}

    try:
        ref_dt = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        ref_dt = datetime.datetime.now()

    dt_5min_ago = (ref_dt - datetime.timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    dt_1hr_ago = (ref_dt - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        "SELECT COUNT(*) as cnt FROM transactions WHERE customer_id = ? AND timestamp >= ? AND timestamp <= ?",
        (customer_id, dt_5min_ago, timestamp_str)
    )
    cnt_5m = cursor.fetchone()["cnt"]

    cursor.execute(
        "SELECT COUNT(*) as cnt FROM transactions WHERE customer_id = ? AND timestamp >= ? AND timestamp <= ?",
        (customer_id, dt_1hr_ago, timestamp_str)
    )
    cnt_1h = cursor.fetchone()["cnt"]
    
    conn.close()
    return {"tx_last_5min": int(cnt_5m), "tx_last_1hour": int(cnt_1h)}


def get_chargeback_history(customer_id: str) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT previous_chargebacks FROM customers WHERE customer_id = ?", (customer_id,))
    row = cursor.fetchone()
    conn.close()
    cb_count = row["previous_chargebacks"] if row else 0
    return {"customer_id": customer_id, "previous_chargebacks": cb_count}


def save_prediction(tx_id: str, prob: float, score: int, level: str = "Medium", status: str = "REVIEW", signals: List[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    signals_str = "; ".join(signals) if isinstance(signals, list) else str(signals or "")
    
    if not level:
        level = "High" if score >= 70 else ("Medium" if score >= 40 else "Low")

    cursor.execute("""
    INSERT OR REPLACE INTO predictions VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (tx_id, float(prob), int(score), level, status, signals_str, now_str))
    
    conn.commit()
    conn.close()


def save_analyst_action(
    tx_id: str,
    prev_status: str,
    new_status: str,
    risk_score: int,
    ai_recommendation: str,
    analyst_remark: str,
    post_analysis: str = ""
) -> Dict[str, Any]:
    """
    Persists manual analyst decision override and post-decision analysis to SQLite.
    Updates transactions table and audit_logs table.
    """
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    UPDATE transactions
    SET analyst_decision = ?, analyst_remark = ?, analyst_action_timestamp = ?
    WHERE transaction_id = ?
    """, (new_status, analyst_remark, now_str, tx_id))

    action_type = "MANUAL OVERRIDE" if prev_status != new_status else "MANUAL CONFIRMATION"
    cursor.execute("""
    INSERT INTO analyst_actions (transaction_id, timestamp, previous_status, new_status, risk_score, ai_recommendation, analyst_action, analyst_remark, post_analysis)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (tx_id, now_str, prev_status, new_status, risk_score, ai_recommendation, action_type, analyst_remark, post_analysis))

    audit_msg = f"Analyst Action: Changed from {prev_status} to {new_status} | Reason: {analyst_remark}"
    cursor.execute("""
    INSERT INTO audit_logs (timestamp, transaction_id, risk_score, agent_action, tools_used, rag_retrieved, crag_result, srag_result, recommendation, final_explanation)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        now_str, tx_id, risk_score, audit_msg, "analyst_manual_override",
        "Analyst Decision Policy", "CRAG: Verified", "SRAG: Override Applied",
        new_status, f"Analyst Reason: {analyst_remark}\nPost Analysis: {post_analysis}"
    ))

    conn.commit()
    conn.close()
    return get_latest_analyst_action(tx_id)


def get_latest_analyst_action(tx_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM analyst_actions WHERE transaction_id = ? ORDER BY action_id DESC LIMIT 1
    """, (tx_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_dataset_counts() -> Dict[str, int]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total_cnt FROM transactions")
    total_cnt = cursor.fetchone()["total_cnt"]

    cursor.execute("SELECT COUNT(*) as new_cnt FROM transactions WHERE is_new_tx = 1")
    new_cnt = cursor.fetchone()["new_cnt"]
    conn.close()

    hist_cnt = total_cnt - new_cnt
    return {"total": total_cnt, "historical": hist_cnt, "new": new_cnt}


def get_all_transactions() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("""
    SELECT t.*, p.fraud_probability, p.risk_score, p.risk_level, p.status as model_status, p.risk_signals
    FROM transactions t
    LEFT JOIN predictions p ON t.transaction_id = p.transaction_id
    ORDER BY t.timestamp DESC
    """, conn)
    conn.close()
    
    if not df.empty:
        if "analyst_decision" not in df.columns:
            df["analyst_decision"] = None
        df["effective_status"] = df["analyst_decision"].fillna(df["model_status"])
    return df


def save_audit_log(
    tx_id: str,
    risk_score: int,
    agent_action: str,
    tools_used: List[str],
    rag_retrieved: List[str],
    crag_result: str,
    srag_result: str,
    recommendation: str,
    final_explanation: str
):
    """
    Saves an audit trail log entry for an AI investigation.
    NEVER stores API keys or confidential credentials.
    """
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    tools_str = ", ".join(tools_used) if isinstance(tools_used, list) else str(tools_used)
    rag_str = " | ".join(rag_retrieved[:3]) if isinstance(rag_retrieved, list) else str(rag_retrieved)

    cursor.execute("""
    INSERT INTO audit_logs (timestamp, transaction_id, risk_score, agent_action, tools_used, rag_retrieved, crag_result, srag_result, recommendation, final_explanation)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (now_str, tx_id, risk_score, agent_action, tools_str, rag_str, crag_result, srag_result, recommendation, final_explanation))

    conn.commit()
    conn.close()


def get_all_audit_logs() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM audit_logs ORDER BY log_id DESC", conn)
    conn.close()
    return df


def get_analyst_override_reason(tx_id: str) -> Optional[str]:
    """
    Retrieves the actual stored analyst override reason/remark for a transaction.
    Returns exact stored string or None (NEVER fabricates/infers a reason).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Check analyst_actions table for specific analyst_remark
    cursor.execute("""
    SELECT analyst_remark FROM analyst_actions 
    WHERE transaction_id = ? AND analyst_remark IS NOT NULL AND analyst_remark != ''
    ORDER BY action_id DESC LIMIT 1
    """, (tx_id,))
    action_row = cursor.fetchone()
    if action_row and action_row["analyst_remark"] and str(action_row["analyst_remark"]).strip():
        remark = str(action_row["analyst_remark"]).strip()
        if not remark.startswith("Analyst set decision to") and not remark.startswith("Decision changed to"):
            conn.close()
            return remark

    # 2. Check transactions table
    cursor.execute("SELECT analyst_remark FROM transactions WHERE transaction_id = ?", (tx_id,))
    row = cursor.fetchone()
    if row and row["analyst_remark"] and str(row["analyst_remark"]).strip():
        remark = str(row["analyst_remark"]).strip()
        if not remark.startswith("Analyst set decision to") and not remark.startswith("Decision changed to"):
            conn.close()
            return remark

    # 3. Fallback to any non-empty remark if present
    if action_row and action_row["analyst_remark"] and str(action_row["analyst_remark"]).strip():
        conn.close()
        return str(action_row["analyst_remark"]).strip()
    if row and row["analyst_remark"] and str(row["analyst_remark"]).strip():
        conn.close()
        return str(row["analyst_remark"]).strip()

    conn.close()
    return None


# ─────────────────────────────────────────────────────────────────────────────
# USER AUTHENTICATION & MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def create_user(username: str, email: str, hashed_password: str, role: str = "analyst", full_name: str = "", status: str = "PENDING_APPROVAL") -> Dict[str, Any]:
    """Create a new user in the database with given status."""
    conn = get_connection()
    cursor = conn.cursor()
    created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    # Normalize role
    role_norm = role.lower().strip()
    # If registering admin, require explicit approval unless pre-seeded
    status_norm = status.upper().strip()
    try:
        cursor.execute(
            "INSERT INTO users (username, email, hashed_password, role, full_name, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (username.lower().strip(), email.lower().strip(), hashed_password, role_norm, full_name, status_norm, created_at)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return {
            "user_id": user_id,
            "username": username.lower().strip(),
            "email": email.lower().strip(),
            "role": role_norm,
            "full_name": full_name,
            "status": status_norm,
            "created_at": created_at
        }
    except sqlite3.IntegrityError as e:
        conn.close()
        if "users.username" in str(e) or "username" in str(e):
            raise ValueError("Username already exists")
        elif "users.email" in str(e) or "email" in str(e):
            raise ValueError("Email already registered")
        else:
            raise ValueError(f"User registration error: {str(e)}")

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve user record by user_id."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Retrieve user record by username."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username.lower().strip(),))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Retrieve user record by email."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_all_users() -> List[Dict[str, Any]]:
    """Get list of all registered users (excluding hashed_password)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, email, role, full_name, status, created_at FROM users ORDER BY user_id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_user_status(user_id: int, new_status: str) -> Dict[str, Any]:
    """Update user account status (ACTIVE, REJECTED, PENDING_APPROVAL)."""
    valid_statuses = ["ACTIVE", "REJECTED", "PENDING_APPROVAL"]
    status_clean = new_status.upper().strip()
    if status_clean not in valid_statuses:
        raise ValueError(f"Invalid status: {new_status}. Must be one of {valid_statuses}")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = ? WHERE user_id = ?", (status_clean, user_id))
    conn.commit()
    conn.close()

    user = get_user_by_id(user_id)
    if not user:
        raise ValueError(f"User #{user_id} not found")
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "full_name": user["full_name"],
        "status": user["status"],
        "created_at": user["created_at"]
    }

def delete_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Delete a user record from the database (used when rejecting registrations)."""
    user = get_user_by_id(user_id)
    if not user:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return user


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN ↔ ANALYST COMMUNICATION DATABASE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_or_create_conversation(analyst_id: int, analyst_username: str) -> Dict[str, Any]:
    """
    Finds existing conversation for analyst_id or creates a new one.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM conversations WHERE analyst_id = ?", (analyst_id,))
    row = cursor.fetchone()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if row:
        conv = dict(row)
        conn.close()
        return conv

    cursor.execute("""
    INSERT INTO conversations (analyst_id, analyst_username, created_at, updated_at)
    VALUES (?, ?, ?, ?)
    """, (analyst_id, analyst_username, now_str, now_str))
    conn.commit()
    conv_id = cursor.lastrowid
    conn.close()

    return {
        "conversation_id": conv_id,
        "analyst_id": analyst_id,
        "analyst_username": analyst_username,
        "created_at": now_str,
        "updated_at": now_str
    }


def get_conversations_for_admin() -> List[Dict[str, Any]]:
    """
    Retrieves all analyst conversations for Admin with unread count and open API key request indicators.
    Includes all registered users with role 'analyst'.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get all analysts
    cursor.execute("SELECT user_id, username, full_name, role, status FROM users WHERE LOWER(role) = 'analyst' ORDER BY user_id ASC")
    analysts = [dict(r) for r in cursor.fetchall()]

    result = []
    for analyst in analysts:
        a_id = analyst["user_id"]
        a_name = analyst["username"]
        
        # Ensure conversation exists
        cursor.execute("SELECT * FROM conversations WHERE analyst_id = ?", (a_id,))
        c_row = cursor.fetchone()
        if not c_row:
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO conversations (analyst_id, analyst_username, created_at, updated_at) VALUES (?, ?, ?, ?)",
                           (a_id, a_name, now_str, now_str))
            conn.commit()
            c_id = cursor.lastrowid
        else:
            c_id = c_row["conversation_id"]

        # Count unread messages sent by analyst
        cursor.execute("""
        SELECT COUNT(*) as unread FROM messages
        WHERE conversation_id = ? AND LOWER(sender_role) = 'analyst' AND is_read = 0
        """, (c_id,))
        unread_cnt = cursor.fetchone()["unread"]

        # Check for open API key request
        cursor.execute("""
        SELECT COUNT(*) as open_req FROM messages
        WHERE conversation_id = ? AND msg_type = 'API_KEY_REQUEST' AND status = 'OPEN'
        """, (c_id,))
        open_req_cnt = cursor.fetchone()["open_req"]

        # Get latest message
        cursor.execute("""
        SELECT message, sender_role, created_at, msg_type, status FROM messages
        WHERE conversation_id = ? ORDER BY message_id DESC LIMIT 1
        """, (c_id,))
        latest_row = cursor.fetchone()
        latest_msg = dict(latest_row) if latest_row else None

        result.append({
            "conversation_id": c_id,
            "analyst_id": a_id,
            "analyst_username": a_name,
            "analyst_full_name": analyst.get("full_name") or a_name,
            "analyst_status": analyst.get("status", "ACTIVE"),
            "unread_count": unread_cnt,
            "has_open_api_request": open_req_cnt > 0,
            "latest_message": latest_msg
        })

    conn.close()
    return result


def send_message(
    conversation_id: int,
    sender_id: int,
    sender_username: str,
    sender_role: str,
    message: str,
    msg_type: str = "NORMAL_MESSAGE",
    status: Optional[str] = None
) -> Dict[str, Any]:
    """
    Inserts a new message into a conversation thread.
    """
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    default_status = "OPEN" if msg_type == "API_KEY_REQUEST" else status

    cursor.execute("""
    INSERT INTO messages (conversation_id, sender_id, sender_username, sender_role, message, msg_type, status, is_read, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
    """, (conversation_id, sender_id, sender_username, sender_role.lower(), message, msg_type, default_status, now_str))
    
    msg_id = cursor.lastrowid

    # Update conversation updated_at timestamp
    cursor.execute("UPDATE conversations SET updated_at = ? WHERE conversation_id = ?", (now_str, conversation_id))
    conn.commit()
    conn.close()

    return {
        "message_id": msg_id,
        "conversation_id": conversation_id,
        "sender_id": sender_id,
        "sender_username": sender_username,
        "sender_role": sender_role.lower(),
        "message": message,
        "msg_type": msg_type,
        "status": default_status,
        "is_read": 0,
        "created_at": now_str,
        "resolved_at": None
    }


def get_messages_in_conversation(conversation_id: int) -> List[Dict[str, Any]]:
    """
    Fetches all messages in a conversation sorted by timestamp.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT message_id, conversation_id, sender_id, sender_username, sender_role, message, msg_type, status, is_read, created_at, resolved_at
    FROM messages
    WHERE conversation_id = ?
    ORDER BY message_id ASC
    """, (conversation_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_messages_read(conversation_id: int, reader_role: str):
    """
    Marks unread messages in conversation sent by opposite role as read.
    """
    conn = get_connection()
    cursor = conn.cursor()
    target_role = "analyst" if reader_role.lower() == "admin" else "admin"
    cursor.execute("""
    UPDATE messages SET is_read = 1
    WHERE conversation_id = ? AND LOWER(sender_role) = ? AND is_read = 0
    """, (conversation_id, target_role))
    conn.commit()
    conn.close()


def resolve_api_key_request(message_id: int) -> Optional[Dict[str, Any]]:
    """
    Marks an API_KEY_REQUEST message as RESOLVED.
    """
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    UPDATE messages SET status = 'RESOLVED', resolved_at = ? WHERE message_id = ? AND msg_type = 'API_KEY_REQUEST'
    """, (now_str, message_id))
    conn.commit()

    cursor.execute("SELECT * FROM messages WHERE message_id = ?", (message_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def get_unread_notification_count(user_id: int, user_role: str) -> int:
    """
    Returns count of unread notifications for the user.
    For admin: unread analyst messages across all conversations + open API requests.
    For analyst: unread admin messages in their conversation + resolved API requests.
    """
    conn = get_connection()
    cursor = conn.cursor()
    role_clean = user_role.lower().strip()

    if role_clean == "admin":
        cursor.execute("SELECT COUNT(*) as cnt FROM messages WHERE LOWER(sender_role) = 'analyst' AND is_read = 0")
        cnt = cursor.fetchone()["cnt"]
    elif role_clean == "analyst":
        # Find conversation for this analyst
        cursor.execute("SELECT conversation_id FROM conversations WHERE analyst_id = ?", (user_id,))
        c_row = cursor.fetchone()
        if not c_row:
            conn.close()
            return 0
        c_id = c_row["conversation_id"]
        cursor.execute("SELECT COUNT(*) as cnt FROM messages WHERE conversation_id = ? AND LOWER(sender_role) = 'admin' AND is_read = 0", (c_id,))
        cnt = cursor.fetchone()["cnt"]
    else:
        cnt = 0

    conn.close()
    return cnt


def has_open_api_key_request(analyst_id: int) -> bool:
    """
    Checks if an analyst already has an open API_KEY_REQUEST to prevent duplicate spamming.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT COUNT(*) as open_cnt
    FROM messages m
    JOIN conversations c ON m.conversation_id = c.conversation_id
    WHERE c.analyst_id = ? AND m.msg_type = 'API_KEY_REQUEST' AND m.status = 'OPEN'
    """, (analyst_id,))
    cnt = cursor.fetchone()["open_cnt"]
    conn.close()
    return cnt > 0

