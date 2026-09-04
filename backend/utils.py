import os
import random
import datetime
import pandas as pd
import numpy as np
import networkx as nx
import plotly.graph_objects as go
from typing import Tuple, Dict, Any, List, Optional

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASETS_DIR = os.path.join(ROOT_DIR, "data", "datasets")

DATASET_CONFIGS = {
    "mixed_risk_transactions.csv": {
        "label": "Mixed Risk (Recommended)",
        "desc": "Realistic blend of APPROVE, REVIEW, and HOLD decisions (~1,200 transactions). Ideal for overall system demonstration.",
        "num_rows": 1200,
        "fraud_rate": 0.12
    },
    "normal_transactions.csv": {
        "label": "Normal Traffic",
        "desc": "Mostly legitimate payment traffic with consistent customer baselines (~600 transactions). Produces mostly APPROVE decisions.",
        "num_rows": 600,
        "fraud_rate": 0.03
    },
    "fraud_transactions.csv": {
        "label": "High Risk / Fraud",
        "desc": "Heavy anomaly signals including large deviations, rapid velocity, and new device bursts (~600 transactions). Produces mostly HOLD decisions.",
        "num_rows": 600,
        "fraud_rate": 0.55
    },
    "fraud_spike_transactions.csv": {
        "label": "Fraud Spike",
        "desc": "Sudden surge in suspicious transactions, high velocity, repeated device reuse, and location jumps (~600 transactions).",
        "num_rows": 600,
        "fraud_rate": 0.42
    },
    "edge_case_transactions.csv": {
        "label": "Edge Cases",
        "desc": "Complex edge cases including legitimate large purchases, new devices, and borderline risk scores (~600 transactions).",
        "num_rows": 600,
        "fraud_rate": 0.25
    }
}


def generate_synthetic_dataset(
    filename: str,
    num_rows: int = 1000,
    fraud_rate: float = 0.08,
    seed: int = 42
) -> pd.DataFrame:
    """
    Generates a deterministic synthetic payment transaction dataset representing MULTIPLE CUSTOMERS.
    Contains realistic telemetry: amounts, devices, locations, velocity spikes, and failed attempts.
    """
    np.random.seed(seed)
    random.seed(seed)

    output_path = os.path.join(DATASETS_DIR, filename)
    os.makedirs(DATASETS_DIR, exist_ok=True)

    num_customers = max(40, num_rows // 25)
    customers = [f"C{1000 + i}" for i in range(num_customers)]
    
    devices_pool = [f"DEV_{random.randint(1000, 9999)}" for _ in range(num_customers * 2)]
    locations = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Gurugram", "Noida", "London", "New York"]
    payment_methods = ["UPI", "Credit Card", "Debit Card", "Netbanking", "Wallet"]

    customer_profiles = {}
    for c_id in customers:
        customer_profiles[c_id] = {
            "account_age_days": random.randint(3, 900),
            "primary_device": random.choice(devices_pool),
            "primary_location": random.choice(locations[:11]),
            "avg_amount": round(float(np.random.gamma(shape=3.0, scale=1100.0)), 2),
            "chargeback_history": 1 if random.random() < 0.08 else (2 if random.random() < 0.02 else 0),
        }

    fraud_shared_device = "DEV_FRAUD_BURST_99"
    start_date = datetime.datetime.now() - datetime.timedelta(days=90)
    records = []
    tx_counter = 10000

    for i in range(num_rows):
        c_id = random.choice(customers)
        prof = customer_profiles[c_id]
        
        is_current = (i >= int(num_rows * 0.88))
        status = "current" if is_current else "historical"
        
        r_val = random.random()
        tx_id = f"TX{tx_counter}"
        tx_counter += 1
        
        if not is_current:
            random_minutes = random.randint(0, 90 * 24 * 60)
            timestamp = start_date + datetime.timedelta(minutes=random_minutes)
        else:
            random_minutes = random.randint(0, 24 * 60)
            timestamp = datetime.datetime.now() - datetime.timedelta(minutes=random_minutes)

        if r_val < fraud_rate:
            pattern = random.choice(["amount_spike", "velocity_burst", "shared_device", "location_jump"])
            
            if pattern == "amount_spike":
                amount = round(prof["avg_amount"] * np.random.uniform(4.5, 9.0), 2)
                device_id = prof["primary_device"]
                location = prof["primary_location"]
                failed_attempts = random.randint(2, 5)
            elif pattern == "velocity_burst":
                amount = round(prof["avg_amount"] * np.random.uniform(2.0, 4.0), 2)
                device_id = random.choice(devices_pool)
                location = prof["primary_location"]
                failed_attempts = random.randint(1, 3)
            elif pattern == "shared_device":
                amount = round(prof["avg_amount"] * np.random.uniform(3.0, 6.0), 2)
                device_id = fraud_shared_device
                location = random.choice(locations[11:])
                failed_attempts = 2
            else: # location jump
                amount = round(prof["avg_amount"] * np.random.uniform(3.5, 7.0), 2)
                device_id = random.choice(devices_pool)
                location = random.choice(locations[11:])
                failed_attempts = random.randint(1, 4)
                
            is_fraud = 1
        elif r_val < (fraud_rate + 0.15):
            # Borderline / Review case scenario (moderate amount deviation, new device, or 1 failed attempt)
            pattern = random.choice(["mod_dev", "new_dev_normal", "loc_shift", "failed_att_1"])
            if pattern == "mod_dev":
                amount = round(prof["avg_amount"] * np.random.uniform(2.2, 3.2), 2)
                device_id = prof["primary_device"]
                location = prof["primary_location"]
                failed_attempts = 1
            elif pattern == "new_dev_normal":
                amount = round(prof["avg_amount"] * np.random.uniform(1.2, 2.0), 2)
                device_id = random.choice(devices_pool)
                location = prof["primary_location"]
                failed_attempts = 0
            elif pattern == "loc_shift":
                amount = round(prof["avg_amount"] * np.random.uniform(1.5, 2.5), 2)
                device_id = prof["primary_device"]
                location = random.choice(locations[:11])
                failed_attempts = 1
            else:
                amount = round(prof["avg_amount"] * np.random.uniform(1.8, 2.8), 2)
                device_id = prof["primary_device"]
                location = prof["primary_location"]
                failed_attempts = 1
            is_fraud = 0
        else:
            # Clean / Approve case scenario
            amount = max(15.0, round(prof["avg_amount"] * np.random.uniform(0.45, 1.6), 2))
            device_id = prof["primary_device"] if random.random() < 0.92 else random.choice(devices_pool)
            location = prof["primary_location"] if random.random() < 0.94 else random.choice(locations[:11])
            failed_attempts = 0 if random.random() < 0.96 else 1
            is_fraud = 0

        method = random.choice(payment_methods)

        records.append({
            "transaction_id": tx_id,
            "customer_id": c_id,
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "amount": amount,
            "payment_method": method,
            "device_id": device_id,
            "location": location,
            "failed_attempts": failed_attempts,
            "account_age_days": prof["account_age_days"],
            "previous_chargebacks": prof["chargeback_history"],
            "transaction_status": status,
            "is_fraud": is_fraud
        })

    df = pd.DataFrame(records)
    df["dt"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("dt").drop(columns=["dt"])
    df.to_csv(output_path, index=False)
    
    if filename == "mixed_risk_transactions.csv":
        os.makedirs("data", exist_ok=True)
        df.to_csv("data/sample_transactions.csv", index=False)

    return df


def generate_all_synthetic_datasets():
    """
    Generates all 5 required synthetic datasets in data/datasets/
    """
    for fname, cfg in DATASET_CONFIGS.items():
        generate_synthetic_dataset(
            filename=fname,
            num_rows=cfg["num_rows"],
            fraud_rate=cfg["fraud_rate"],
            seed=abs(hash(fname)) % 10000
        )


def validate_csv_schema(df: pd.DataFrame) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Validates CSV schema against required transaction columns.
    Returns: (is_valid: bool, missing_columns: list, metadata_summary: dict)
    """
    required_cols = [
        "transaction_id", "customer_id", "timestamp", "amount",
        "payment_method", "device_id", "location"
    ]
    
    missing = [col for col in required_cols if col not in df.columns]
    
    if missing:
        return False, missing, {}

    if "failed_attempts" not in df.columns:
        df["failed_attempts"] = 0
    if "account_age_days" not in df.columns:
        df["account_age_days"] = 180
    if "previous_chargebacks" not in df.columns:
        df["previous_chargebacks"] = 0
    if "transaction_status" not in df.columns:
        df["transaction_status"] = "current"
    if "is_fraud" not in df.columns:
        df["is_fraud"] = 0

    meta = {
        "num_rows": len(df),
        "num_customers": df["customer_id"].nunique(),
        "num_devices": df["device_id"].nunique(),
        "total_amount": float(df["amount"].sum()),
        "start_date": str(df["timestamp"].min()),
        "end_date": str(df["timestamp"].max())
    }
    
    return True, [], meta


def calculate_cost_impact(
    fp_count: int,
    fn_count: int,
    fp_cost_per_tx: float = 2000.0,
    fn_cost_avg_amount: float = 35000.0
) -> Dict[str, float]:
    """
    Calculates financial impact of false positives (analyst review cost)
    and false negatives (actual unrecovered fraud loss).
    """
    total_fp_cost = fp_count * fp_cost_per_tx
    total_fn_cost = fn_count * fn_cost_avg_amount
    total_risk_exposure = total_fp_cost + total_fn_cost
    
    return {
        "false_positive_cost": round(total_fp_cost, 2),
        "false_negative_exposure": round(total_fn_cost, 2),
        "total_risk_cost": round(total_risk_exposure, 2)
    }


def create_risk_network_graph(df: pd.DataFrame, target_customer_id: Optional[str] = None) -> go.Figure:
    """
    Builds a NetworkX entity graph connecting Customer -> Device / Location / Payment Method.
    Visualizes connected suspicious entities in Plotly.
    """
    G = nx.Graph()
    
    if target_customer_id and target_customer_id in df["customer_id"].values:
        sub_df = df[df["customer_id"] == target_customer_id]
        devices = sub_df["device_id"].unique()
        connected_customers = df[df["device_id"].isin(devices)]["customer_id"].unique()
        plot_df = df[df["customer_id"].isin(connected_customers)].head(150)
    else:
        plot_df = df.head(120)

    for _, row in plot_df.iterrows():
        c_node = f"Cust:{row['customer_id']}"
        d_node = f"Dev:{row['device_id']}"
        l_node = f"Loc:{row['location']}"
        
        G.add_node(c_node, type="Customer", label=str(row['customer_id']))
        G.add_node(d_node, type="Device", label=str(row['device_id']))
        G.add_node(l_node, type="Location", label=str(row['location']))
        
        G.add_edge(c_node, d_node, weight=1)
        G.add_edge(c_node, l_node, weight=1)

    pos = nx.spring_layout(G, k=0.35, iterations=30, seed=42)

    edge_x, edge_y = [], []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=1, color="#94A3B8"),
        hoverinfo="none",
        mode="lines"
    )

    node_x, node_y, node_text, node_color, node_size = [], [], [], [], []

    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        ntype = G.nodes[node]["type"]
        label = G.nodes[node]["label"]
        node_text.append(f"{ntype}: {label}")

        if ntype == "Customer":
            node_color.append("#0F172A") # Deep Navy
            node_size.append(14)
        elif ntype == "Device":
            node_color.append("#D97706") # Amber
            node_size.append(10)
        else:
            node_color.append("#0284C7") # Fintech Blue
            node_size.append(8)

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        hoverinfo="text",
        text=[G.nodes[n]["label"] if G.nodes[n]["type"] == "Customer" else "" for n in G.nodes()],
        textposition="top center",
        hovertext=node_text,
        marker=dict(
            color=node_color,
            size=node_size,
            line=dict(width=1.5, color="#FFFFFF")
        )
    )

    fig = go.Figure(
        data=[edge_trace, node_trace],
        layout=go.Layout(
            title=dict(text="Entity Relationship Risk Network (Customer - Device - Location)", font=dict(size=14, color="#0F172A")),
            showlegend=False,
            hovermode="closest",
            margin=dict(b=20, l=20, r=20, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor="#F8FAFC",
            paper_bgcolor="#FFFFFF"
        )
    )
    return fig
