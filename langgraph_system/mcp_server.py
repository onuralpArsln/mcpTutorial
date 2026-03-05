# langgraph_system/mcp_server.py
from mcp.server.fastmcp import FastMCP
import os
import difflib
import platform

# Specialized server for LangGraph experimentation
mcp = FastMCP("LangGraph-Experimental-Server")

# --- Mock Product Database ---
PRODUCTS_DB = {
    "P001": {"name": "Eco-Friendly Water Bottle", "category": "Home", "cost": 15, "price": 45},
    "P002": {"name": "Wireless Headphones", "category": "Electronics", "cost": 120, "price": 299},
    "P003": {"name": "Ergonomic Chair", "category": "Office", "cost": 85, "price": 249},
    "P004": {"name": "Solar Charger", "category": "Outdoor", "cost": 35, "price": 89},
    "P005": {"name": "Fitness Tracker", "category": "Health", "cost": 55, "price": 129}
}

# --- Core Tools (copied from original for baseline) ---

@mcp.tool()
def dosya_yaz(dosya_adi: str, icerik: str) -> str:
    """Creates a new file and writes content to it."""
    try:
        # Step out once to reach the root project directory from langgraph_system/
        root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(root_path, dosya_adi)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(icerik)
        return f"{dosya_adi} created successfully in root."
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def notlari_listele() -> str:
    """Lists all .txt files in the root directory."""
    try:
        root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dosyalar = [f for f in os.listdir(root_path) if f.endswith('.txt')]
        if not dosyalar:
            return "No notes found in root."
        return "Notes:\n" + "\n".join(f"- {d}" for d in dosyalar)
    except Exception as e:
        return f"Error: {str(e)}"

# --- Experimental Tools (New!) ---

@mcp.tool()
def get_performance_metrics(range_type: str = "last_7_days") -> str:
    """Returns mock performance metrics (ROAS, Conversion Rate, CPC, etc.) for a given range."""
    # Mock data based on the ReadMe state diagram
    metrics = {
        "ROAS": 3.2,
        "Conversion_Rate": "2.4%",
        "Sales_Count": 150,
        "Revenue": 15000,
        "Ad_Spend": 4687.5,
        "CTR": "1.8%",
        "Range": range_type
    }
    return f"Performance Data: {metrics}"

@mcp.tool()
def list_products() -> str:
    """Lists all products available in the mock database."""
    return "Available Products:\n" + "\n".join([f"[{id}] {p['name']} ({p['category']})" for id, p in PRODUCTS_DB.items()])

@mcp.tool()
def get_product_costs(product_id: str = "P001") -> str:
    """Returns mock cost information for a specific product ID."""
    p = PRODUCTS_DB.get(product_id.upper())
    if not p:
        return f"Error: Product ID {product_id} not found."
    
    margin = ((p['price'] - p['cost']) / p['price']) * 100
    costs = {
        "Product_Name": p['name'],
        "Unit_Cost": p['cost'],
        "Sale_Price": p['price'],
        "Profit_Margin": f"{margin:.1f}%",
        "Product_ID": product_id
    }
    return f"Cost Data: {costs}"

@mcp.tool()
def get_strategy_rules(intent_type: str) -> str:
    """Returns business strategy rules based on the detected intent."""
    rules = {
        "scale_up": [
            "Rule 1: If ROAS > 3.0, increase budget by 20%.",
            "Rule 2: Max daily budget increase is $500.",
            "Rule 3: Maintain CVR above 2%."
        ],
        "optimize": [
            "Rule 1: If ROAS < 2.0, decrease bid by 15%.",
            "Rule 2: Pause keywords with 0 conversions and >$50 spend."
        ]
    }
    selected_rules = rules.get(intent_type.lower(), ["No specific rules found for this intent. Use default cautious optimization."])
    return f"Applicable Rules for {intent_type}: {selected_rules}"

@mcp.tool()
def run_pattern_recognition(data_summary: str) -> str:
    """Simulates an ML tool that identifies patterns/trends in performance data."""
    # Mock pattern detection logic
    if "3.2" in data_summary:
        return "Pattern Detected: Positive trend in ROAS identified. Consistent performance over the weekend. No anomalies found."
    return "Pattern Detected: Fluctuating performance. Recommendation: Collect more data before scaling."

@mcp.tool()
def system_info() -> str:
    """Returns basic system information (OS, Python version)."""
    return f"OS: {platform.system()} {platform.release()} | Python: {platform.python_version()}"

if __name__ == "__main__":
    mcp.run(transport='stdio')
