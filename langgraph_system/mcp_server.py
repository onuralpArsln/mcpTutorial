# langgraph_system/mcp_server.py
from mcp.server.fastmcp import FastMCP
import os
import difflib
import platform

# Specialized server for LangGraph experimentation
mcp = FastMCP("LangGraph-Experimental-Server")

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
def save_product_alias(urun_kodu: str, alias: str) -> str:
    """Ürün koduna yeni bir isimlendirme (alias) öğretmek için kullanılır. Bu isim database_schema.yaml dosyasına kalıcı olarak kaydedilir."""
    import yaml
    
    try:
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge", "database_schema.yaml")
        
        # Dosyayı oku
        with open(schema_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            
        # Eğer product_aliases yoksa oluştur
        if "product_aliases" not in data:
            data["product_aliases"] = {}
            
        # Ismi temizle ve kaydet
        clean_isim = alias.strip().lower()
        data["product_aliases"][urun_kodu.upper()] = clean_isim
        
        # Dosyaya geri yaz
        with open(schema_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
        return f"Başarılı: '{clean_isim}' ismi kalıcı olarak {urun_kodu} için sisteme öğretildi!"
    except Exception as e:
        return f"Hata: İsim öğretilemedi. ({str(e)})"
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

import json
import csv

@mcp.tool()
def compare_metrics(data_json: str, keys_to_compare: list) -> str:
    """
    Compares metrics across multiple product records.
    Input: data_json (JSON string array of DB objects), keys_to_compare (list of strings like ['harcama_getirisi', 'gerceklesen_tbm']).
    """
    try:
        data = json.loads(data_json)
        if not data or not isinstance(data, list):
            return "Error: data_json must be a non-empty JSON array."
        
        result = []
        for key in keys_to_compare:
            # Drop items missing the key
            valid_items = [d for d in data if key in d and d[key] is not None]
            if not valid_items:
                continue
                
            # Convert to float for comparison
            def _to_float(val):
                if isinstance(val, str):
                    val = val.replace(',', '.')
                try:
                    return float(val)
                except:
                    return 0.0

            sorted_items = sorted(valid_items, key=lambda x: _to_float(x[key]), reverse=True)
            top = sorted_items[0]
            bottom = sorted_items[-1]
            
            result.append(f"Metric '{key}':")
            result.append(f"  - LİDER: {top.get('urun_kodu', 'Bilinmeyen')} (Değer: {top[key]})")
            if len(sorted_items) > 1:
                result.append(f"  - EN DÜŞÜK: {bottom.get('urun_kodu', 'Bilinmeyen')} (Değer: {bottom[key]})")
                
        if not result:
            return "No valid metrics found to compare."
            
        return "\n".join(result)
    except Exception as e:
        return f"Error in compare_metrics: {str(e)}"

@mcp.tool()
def calculate_ratio(numerator: float, denominator: float, metric_name: str) -> str:
    """
    Safely calculates a ratio or percentage (numerator / denominator) to prevent LLM math hallucinations.
    """
    try:
        num = float(numerator)
        den = float(denominator)
        if den == 0:
            return f"[{metric_name}] Hesaplama Hatası: Payda (denominator) 0 olamaz!"
            
        ratio = num / den
        percentage = ratio * 100
        return f"{metric_name} Oranı: {ratio:.4f} (Yüzdelik: %{percentage:.2f})"
    except Exception as e:
        return f"Matematik Hatası: {str(e)}"

@mcp.tool()
def forecast_budget_allocation(extra_budget: float, candidate_data_json: str) -> str:
    """
    Simulates budget allocation. Gives the budget to products with ROAS > 1.5 proportionally.
    Input: extra_budget (float), candidate_data_json (JSON string array of DB objects).
    """
    try:
        budget = float(extra_budget)
        data = json.loads(candidate_data_json)
        if not data or not isinstance(data, list):
            return "Error: candidate_data_json must be a JSON array."
            
        # Filter profitable candidates (ROAS > 1.5)
        prof_candidates = []
        for d in data:
            try:
                roas = float(d.get('harcama_getirisi', 0))
                if roas > 1.5:
                    prof_candidates.append((d.get('urun_kodu', 'Bilinmiyor'), roas))
            except:
                pass
                
        if not prof_candidates:
            return f"Uyarı: ROAS'ı 1.5 üzerinde olan kârlı ürün bulunamadı. {budget} TL bütçeyi şu an hiçbirine yatırmamanız tavsiye edilir."
            
        # Distribute budget proportionally based on ROAS
        total_prof_roas = sum(r for _, r in prof_candidates)
        allocations = []
        for code, roas in prof_candidates:
            share = (roas / total_prof_roas) * budget
            allocations.append(f"- {code}: {share:.2f} TL (ROAS: {roas:.2f})")
            
        return f"TAVSİYE EDİLEN BÜTÇE DAĞILIMI ({budget} TL):\n" + "\n".join(allocations)
        
    except Exception as e:
        return f"Forecast Error: {str(e)}"

@mcp.tool()
def export_csv_report(file_name: str, data_json: str) -> str:
    """
    Exports JSON data array to a CSV file in the project root directory.
    Input: file_name (without .csv), data_json (JSON string array).
    """
    try:
        data = json.loads(data_json)
        if not data or not isinstance(data, list):
            return "Hata: Csv export için geçerli bir JSON array gereklidir."
            
        if not file_name.endswith('.csv'):
            file_name += '.csv'
            
        root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(root_path, file_name)
        
        # Get all unique headers
        headers = set()
        for row in data:
            if isinstance(row, dict):
                headers.update(row.keys())
        headers = list(headers)
        
        with open(full_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in data:
                if isinstance(row, dict):
                    writer.writerow(row)
                    
        return f"BAŞARILI: Rapor '{file_name}' adıyla kök dizine kaydedildi. ({len(data)} satır)"
    except Exception as e:
        return f"CSV Export Error: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport='stdio')
