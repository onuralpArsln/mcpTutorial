# langgraph_system/mcp_server.py
from mcp.server.fastmcp import FastMCP
import os
import difflib
import platform

# Specialized server for LangGraph experimentation
mcp = FastMCP("LangGraph-Experimental-Server")

# --- Mock Product Database ---
PRODUCTS_DB = {
    "XPUFFY4040KAREPUF": {"name": "Puffy Kare Puf 40x40", "category": "Mobilya", "cost": 150, "price": 450},
    "XPUFFY6060KAREPUF": {"name": "Puffy Kare Puf 60x60", "category": "Mobilya", "cost": 220, "price": 600},
    "ZAYNABED120X200": {"name": "Zayna Yatak 120x200", "category": "Yatak", "cost": 1200, "price": 3500},
    "ZAYNABED160X200": {"name": "Zayna Çift Kişilik Yatak 160x200", "category": "Yatak", "cost": 1500, "price": 4200},
    "MINIPUFROUND": {"name": "Mini Yuvarlak Puf", "category": "Mobilya", "cost": 85, "price": 250}
}

# --- Mock Ad Performance Database ---
MOCK_AD_PERFORMANCE_DB = [
    {
        "id": 1,
        "sorgu_tarihi": "2026-02-27",
        "sorgu_saati": "15:40:02.575786",
        "urun_kodu": "XPUFFY4040KAREPUF",
        "harcanan_butce": 372.54,
        "gosterim_sayisi": 10781,
        "tiklanma_sayisi": 193,
        "reklam_cirosu": 0.00,
        "harcama_getirisi": 0.00,
        "gerceklesen_tbm": 1.93,
        "tbm_teklif": 1.79,
        "onerilen_tbm": "Önerilen TBM: 3,28 ₺ (En iyi 5,26 ₺)",
        "satis_adet": 0,
        "net_satis": 0.00,
        "created_at": "2026-02-27 12:40:24.287168",
        "gunluk_butce": 500
    },
    {
        "id": 2,
        "sorgu_tarihi": "2026-02-27",
        "sorgu_saati": "15:40:02.575786",
        "urun_kodu": "ZAYNABED160X200",
        "harcanan_butce": 450.00,
        "gosterim_sayisi": 25000,
        "tiklanma_sayisi": 450,
        "reklam_cirosu": 12600.00,
        "harcama_getirisi": 28.00,
        "gerceklesen_tbm": 1.00,
        "tbm_teklif": 1.20,
        "onerilen_tbm": "Önerilen TBM: 1,50 ₺ (En iyi 2,00 ₺)",
        "satis_adet": 3,
        "net_satis": 12600.00,
        "created_at": "2026-02-20 09:00:00.000000",
        "gunluk_butce": 1000
    },
    {
        "id": 3,
        "sorgu_tarihi": "2026-02-27",
        "sorgu_saati": "15:40:02.575786",
        "urun_kodu": "MINIPUFROUND",
        "harcanan_butce": 120.50,
        "gosterim_sayisi": 5430,
        "tiklanma_sayisi": 85,
        "reklam_cirosu": 500.00,
        "harcama_getirisi": 4.15,
        "gerceklesen_tbm": 1.41,
        "tbm_teklif": 1.50,
        "onerilen_tbm": "Önerilen TBM: 2,10 ₺ (En iyi 3,50 ₺)",
        "satis_adet": 2,
        "net_satis": 500.00,
        "created_at": "2026-02-25 14:30:00.000000",
        "gunluk_butce": 200
    }
]

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
def get_performance_metrics(urun_kodu: str = "") -> str:
    """Returns mock performance metrics (ROAS, TBG, vs) against actual database structures."""
    results = MOCK_AD_PERFORMANCE_DB
    
    if urun_kodu:
        results = [row for row in results if row["urun_kodu"] == urun_kodu.upper()]
        
    if not results:
        return f"Belirtilen ürün kodu ({urun_kodu}) için veri bulunamadı."
        
    # Format the data for the LLM
    formatted = "Performans Verileri:\n"
    for r in results:
        formatted += (
            f"- Urun: {r['urun_kodu']} | Tarih: {r['sorgu_tarihi']}\n"
            f"  Harcama: {r['harcanan_butce']} TL | Ciro: {r['reklam_cirosu']} TL | ROAS: {r['harcama_getirisi']}\n"
            f"  TBM Gerçekleşen: {r['gerceklesen_tbm']} | Teklif Edilen: {r['tbm_teklif']} | {r['onerilen_tbm']}\n"
            f"  Gösterim: {r['gosterim_sayisi']} | Tıklama: {r['tiklanma_sayisi']} | Satış: {r['satis_adet']}\n\n"
        )
    return formatted

@mcp.tool()
def list_products() -> str:
    """Lists all products available in the mock database."""
    return "Mevcut Ürünler:\n" + "\n".join([f"[{id}] {p['name']} ({p['category']})" for id, p in PRODUCTS_DB.items()])

@mcp.tool()
def get_product_costs(urun_kodu: str) -> str:
    """Returns mock cost information for a specific product ID (urun_kodu)."""
    p = PRODUCTS_DB.get(urun_kodu.upper())
    if not p:
        return f"Error: Ürün Kodu {urun_kodu} bulunamadı."
    
    margin = ((p['price'] - p['cost']) / p['price']) * 100
    costs = {
        "Urun_Adi": p['name'],
        "Maliyet": p['cost'],
        "Satis_Fiyati": p['price'],
        "Kar_Marji": f"{margin:.1f}%",
        "Urun_Kodu": urun_kodu
    }
    return f"Maliyet Verisi: {costs}"

@mcp.tool()
def get_strategy_rules(intent_type: str) -> str:
    """Reads business strategy rules from the knowledge base (rules.txt) for the given intent type."""
    try:
        rules_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge", "rules.txt")
        
        with open(rules_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Parse the file: find the [intent_type] section
        tag = f"[{intent_type.lower()}]"
        if tag not in content:
            return f"No rules found for intent: '{intent_type}'. Available: [analiz], [reklam_acma], [indirim_kupon], [scale_up], [optimize]"
        
        # Extract the block between this tag and the next tag
        start = content.index(tag) + len(tag)
        next_tag = content.find("[", start)
        block = content[start:next_tag].strip() if next_tag != -1 else content[start:].strip()
        
        return f"Strateji Kuralları [{intent_type}]:\n{block}"
    
    except FileNotFoundError:
        return "Error: rules.txt bulunamadı. Lütfen langgraph_system/knowledge/rules.txt dosyasının mevcut olduğundan emin olun."
    except Exception as e:
        return f"Error reading rules: {str(e)}"

@mcp.tool()
def run_pattern_recognition(data_summary: str) -> str:
    """Simulates an ML tool that identifies patterns/trends in performance data."""
    # Mock pattern detection logic using the new terms
    if "ROAS: 0.0" in data_summary or "harcama_getirisi: 0" in data_summary.lower():
        return "Pattern Detected: Kritik Durum. Harcama yapılıyor ancak hiç ciro (ROAS 0) gelmemiş. Reklamın acilen durdurulması veya hedeflerin gözden geçirilmesi önerilir."
    elif "ROAS: 28.0" in data_summary or "harcama_getirisi" in data_summary and "28" in data_summary:
         return "Pattern Detected: Mükemmel Performans. ROAS çok yüksek, TBM düşük. SCALE UP (Bütçe Artırımı) stratejisi uygulanmalıdır."
    return "Pattern Detected: Dalgalı performans. Daha fazla veri toplanması önerilir."

@mcp.tool()
def system_info() -> str:
    """Returns basic system information (OS, Python version)."""
    return f"OS: {platform.system()} {platform.release()} | Python: {platform.python_version()}"

if __name__ == "__main__":
    mcp.run(transport='stdio')
