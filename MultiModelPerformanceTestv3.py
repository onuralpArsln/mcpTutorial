import requests
import time
import threading
import psutil
import glob
import os
import re
from datetime import datetime

# --- CONFIGURATION ---
# --- CONFIGURATION ---
OLLAMA_API_URL = "http://localhost:11434/api/generate"
# 999 forces all layers to GPU. Ollama will spill to CPU only if VRAM is full.
FORCE_GPU_LAYERS = 999 
# Reduced context saves VRAM, ensuring more of the model fits on your RX 580.
CONTEXT_WINDOW = 2048 
# Increased timeout (10 mins) to prevent crashes during slow CPU/Hybrid runs.
REQUEST_TIMEOUT = 600 

# MATRIX CONFIGURATION: Multiple parameter sets to test.
# {} means use Ollama defaults.
PARAMETER_GROUPS = [
    {},                          # OLLAMA_DEFAULTS: Baseline comparison
    {"temperature": 0},          # STRICT: Maximum determinism for SQL & Tool Selection
    {"temperature": 0, "num_predict": 100}, # CONCISE: Speed optimized, low token limit for short intents
    {"temperature": 0.1, "top_p": 0.4} # FOCUSED: Balanced for RAG/Policy extraction, low noise
]

# --- EMBEDDED KNOWLEDGE (ATOMIC RULES) ---
SQL_RULES = """
- DOUBLE AGGREGATION: For historical totals, use SUM(daily_max) from a subquery grouping by (sorgu_tarihi, urun_kodu).
- ONERILEN_TBM: This is a TEXT field. Extract numeric with REGEXP_REPLACE(onerilen_tbm, '[^0-9.]', '', 'g')::NUMERIC.
- ILIKE for product codes. Use ID DESC LIMIT 1 for latest values.
"""

# --- ATOMIC BENCHMARK SUITE (10 Categories x 2 Variations) ---
BENCHMARK_SUITE = {
    "1a. Intent Classification (Vague)": {
        "prompt": "Dün noldu?",
        "expected": "intent: reklam_analiz or similar (performance summary)",
        "eval_type": "MANUAL_REVIEW"
    },
    "1b. Intent Classification (Easy)": {
        "prompt": "Dünkü reklam harcamalarımı ve toplam satış adedimi göster. (Context: User is asking for performance metrics).",
        "expected": "intent: reklam_analiz",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "2a. Tool Selection (Vague)": {
        "prompt": "Karlılık hesapla.",
        "expected": "tool: calculator or sql_db",
        "eval_type": "MANUAL_REVIEW"
    },
    "2b. Tool Selection (Easy)": {
        "prompt": "Elimdeki 500 TL bütçe ile en yüksek ROAS'lı ürünlere nasıl dağıtım yapmalıyım? (Available Tools: [sql_db, calculator, policy_rag]). Answer with one tool name.",
        "expected": "sql_db",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "3a. SQL Gen - Double Agg (Vague)": {
        "prompt": "Geçen haftaki toplam bütçe.",
        "expected": "Must use SUM(MAX(...)) pattern",
        "eval_type": "MANUAL_REVIEW"
    },
    "3b. SQL Gen - Double Agg (Easy)": {
        "prompt": f"Rules: {SQL_RULES}\nTask: 'product_report' tablosunda 2026-03-01 ile 2026-03-07 arası 'harcanan_butce' günlük maksimumlarını toplayan SQL'i yaz.",
        "expected": "SELECT SUM(daily_max) FROM (SELECT MAX(harcanan_butce) as daily_max ... GROUP BY sorgu_tarihi, urun_kodu)",
        "eval_type": "PASS/FAIL (SQL Snippet)"
    },
    "4a. SQL Gen - String Extract (Vague)": {
        "prompt": "Önerilen TBM kaç?",
        "expected": "SQL involving onerilen_tbm",
        "eval_type": "MANUAL_REVIEW"
    },
    "4b. SQL Gen - String Extract (Easy)": {
        "prompt": f"Rules: {SQL_RULES}\nTask: 'onerilen_tbm' text sütunundan RegEx ile sayı çekip 'tbm_teklif' ile farkını bulan SQL'i yaz.",
        "expected": "REGEXP_REPLACE(onerilen_tbm, '[^0-9.]', '', 'g')::NUMERIC",
        "eval_type": "PASS/FAIL (SQL Snippet)"
    },
    "5a. Math - Discount (Vague)": {
        "prompt": "İndirim yapınca ne olur?",
        "expected": "Needs context",
        "eval_type": "MANUAL_REVIEW"
    },
    "5b. Math - Discount (Easy)": {
        "prompt": "Ürün 100 TL. Önce %15 kupon, sonra kalan tutar üzerinden %10 sepet indirimi uygulanıyor. Nihai fiyat nedir? (Step by step math).",
        "expected": "76.5 (Calculation: 100 * 0.85 * 0.90)",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "6a. Analyst - Risk (Vague)": {
        "prompt": "Kötü gidenleri bul.",
        "expected": "Needs data",
        "eval_type": "MANUAL_REVIEW"
    },
    "6b. Analyst - Risk (Easy)": {
        "prompt": "Veri: [{'name': 'A', 'spend': 150, 'sales': 0}]. 'Kritik Risk' kuralı: Spend > 100 ve Sales = 0. Hangi ürün riskli?",
        "expected": "Ürün A",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "7a. Policy RAG (Vague)": {
        "prompt": "Kural ne?",
        "expected": "Needs policy",
        "eval_type": "MANUAL_REVIEW"
    },
    "7b. Policy RAG (Easy)": {
        "prompt": "Politika: 'İadeler 14 gün, kampanyalı ürünler 7 gündür.' Kampanyalı ürün aldım, iade sürem kaç gün?",
        "expected": "7 gün",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "8a. Explainer - Turkish (Vague)": {
        "prompt": "Bunu anlat.",
        "expected": "Needs data",
        "eval_type": "MANUAL_REVIEW"
    },
    "8b. Explainer - Turkish (Easy)": {
        "prompt": "Veri: [{'avg_roas': 4.5}]. Bu veriyi teknik terimsiz, arkadaş canlısı bir Türkçe ile kullanıcıya açıkla.",
        "expected": "Turkish language, friendly tone, mentions 4.5 ROAS success.",
        "eval_type": "MANUAL_REVIEW"
    },
    "9a. Comparison - Strategy (Vague)": {
        "prompt": "Hangisi iyi?",
        "expected": "Needs options",
        "eval_type": "MANUAL_REVIEW"
    },
    "9b. Comparison - Strategy (Easy)": {
        "prompt": "A: TBM düşür (ROAS artar/Hacim düşer), B: Bütçe artır (Hacim artar/ROAS düşer). ROAS 1.1 (çok düşük) iken hangisi güvenli?",
        "expected": "Seçenek A (Protecting profitability over volume)",
        "eval_type": "MANUAL_REVIEW"
    },
    "10a. Data Formatter (Vague)": {
        "prompt": "JSON yap.",
        "expected": "Needs list",
        "eval_type": "MANUAL_REVIEW"
    },
    "10b. Data Formatter (Easy)": {
        "prompt": "Aşağıdaki listeyi [{'id': int, 'name': str}] formatında JSON'a dönüştür: 1-Mavi Puf, 2-Kırmızı Puf.",
        "expected": '[{"id": 1, "name": "Mavi Puf"}, {"id": 2, "name": "Kırmızı Puf"}]',
        "eval_type": "PASS/FAIL (JSON)"
    },
    # --- CONTEXTUAL AWARENESS SUITE (6 Multi-turn Scenarios) ---
    "11. Contextual - Simple Recall": {
        "prompt": "CHAT_HISTORY: H: 'XPUFFY4040 inceleyelim.' A: 'Tamam, ROAS 4.5.' H: 'Gosterim?' A: '12,000.' H: 'Tiklama?' A: '400.'\nUSER_QUERY: Hangi urun kodu uzerinde calisiyoruz?",
        "expected": "XPUFFY4040",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "12. Contextual - Scope Continuity (SQL)": {
        "prompt": f"Rules: {SQL_RULES}\nCHAT_HISTORY: H: 'XPET4545 performansina bakalim.' A: 'XPET4545 bugun 100 TL harcadı.' H: 'Satis var mi?' A: 'Hayir.'\nUSER_QUERY: Bu urun icin tum zamanlarin cirosunu getiren SQL'i yaz.",
        "expected": "Must use Double Aggregation and filter for XPET4545",
        "eval_type": "PASS/FAIL (SQL Snippet)"
    },
    "13. Contextual - Numerical Memory": {
        "prompt": "CHAT_HISTORY: H: 'Baz fiyat 500 TL.' A: 'Kaydedildi.' H: '%20 indirim yap.' A: 'Fiyat 400 TL oldu.' H: '25 TL kargo ekle.'\nUSER_QUERY: Musteri bundan 2 tane alirsa toplam ne oder?",
        "expected": "850 (425 * 2)",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "14. Contextual - Intent Switching": {
        "prompt": "CHAT_HISTORY: H: 'SELECT * FROM product_report...' A: '[Data List]'. H: 'Bu verileri nasil okumaliyim?' A: '[Analysis]'.\nUSER_QUERY: Selam! Bugunun kisa ve arkadas canlisi bir ozetini gecer misin?",
        "expected": "Friendly Turkish summary, No SQL/JSON",
        "eval_type": "MANUAL_REVIEW"
    },
    "15. Contextual - Multi-Turn Rule Logic": {
        "prompt": "CHAT_HISTORY: H: 'ROAS 2 altiysa kapat.' A: 'Not alindi.' H: 'Ama harcama 100 TL ustu olmali.' A: 'Kural: ROAS < 2 & Spend >= 100 -> KAPAT.' H: 'ROAS 10 ustu ise Harika de.'\nUSER_QUERY: Urun A: Harcama 80, ROAS 1.5. Urun B: Harcama 120, ROAS 15. Durumlari nedir?",
        "expected": "A: Aktif (Harcama < 100), B: Harika (ROAS > 10)",
        "eval_type": "MANUAL_REVIEW"
    },
    "16. Contextual - Complex SQL Synthesis": {
        "prompt": f"Rules: {SQL_RULES}\nCHAT_HISTORY: H: 'RegEx hatirla: REGEXP_REPLACE(onerilen_tbm, \"[^0-9.]\", \"\", \"g\")::NUMERIC.' A: 'Sistem güncellendi.' H: 'Urun kodu \"KARE\" icerenleri al.' A: 'Filtre eklendi.' H: 'Sadece bugunun verisi olsun.'\nUSER_QUERY: Bu filtrelerle temizlenmis onerilen TBM ortalamasini getiren SQL'i yaz.",
        "expected": "AVG(REGEXP_REPLACE), KARE filter, Latest Date filter",
        "eval_type": "PASS/FAIL (SQL Snippet)"
    }
}


def find_amd_gpu():
    """Finds the Linux sysfs path for the AMD GPU."""
    for path in glob.glob('/sys/class/drm/card*/device/gpu_busy_percent'):
        return os.path.dirname(path)
    return None

AMD_GPU_PATH = find_amd_gpu()

class ResourceMonitor:
    def __init__(self):
        self.keep_measuring = True
        self.max_cpu = 0.0
        self.max_ram = 0.0
        self.max_ram_mb = 0.0
        self.max_gpu = 0.0
        self.max_vram = 0.0

    def measure(self):
        psutil.cpu_percent(interval=None)
        while self.keep_measuring:
            cpu = psutil.cpu_percent(interval=0.1)
            virtual_mem = psutil.virtual_memory()
            ram_pct = virtual_mem.percent
            ram_mb = virtual_mem.used / (1024 * 1024)
            if cpu > self.max_cpu: self.max_cpu = cpu
            if ram_pct > self.max_ram: self.max_ram = ram_pct
            if ram_mb > self.max_ram_mb: self.max_ram_mb = ram_mb
            if AMD_GPU_PATH:
                try:
                    with open(os.path.join(AMD_GPU_PATH, 'gpu_busy_percent'), 'r') as f:
                        gpu_util = float(f.read().strip())
                    with open(os.path.join(AMD_GPU_PATH, 'mem_info_vram_used'), 'r') as f:
                        vram_used_bytes = float(f.read().strip())
                        vram_used_mb = vram_used_bytes / (1024 * 1024)
                    if gpu_util > self.max_gpu: self.max_gpu = gpu_util
                    if vram_used_mb > self.max_vram: self.max_vram = vram_used_mb
                except:
                    pass

def get_installed_models():
    """Fetches model list from API."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        return [m['name'] for m in response.json().get('models', [])]
    except:
        return []

def run_test(model_name, prompt, extra_options=None):
    """Runs prompt with merged options and resource monitoring."""
    monitor = ResourceMonitor()
    monitor_thread = threading.Thread(target=monitor.measure)
    monitor_thread.start()

    # Base options
    options = {
        "num_gpu": FORCE_GPU_LAYERS,
        "num_ctx": CONTEXT_WINDOW
    }
    
    # Merge extra options (like temperature) if provided
    if extra_options:
        options.update(extra_options)

    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": options
    }

    start_time = time.time()
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        full_res = response.json().get('response', '')
        # Remove <think>...</think> blocks
        clean_output = re.sub(r'<think>.*?</think>', '', full_res, flags=re.DOTALL).strip()
    except Exception as e:
        clean_output = f"[ERROR] {str(e)}"
    
    duration = time.time() - start_time
    monitor.keep_measuring = False
    monitor_thread.join()

    return clean_output, duration, monitor

def main():
    models = get_installed_models()
    if not models:
        print("Error: No models found. Check if 'ollama serve' is active.")
        return

    log_name = f"ad_manager_benchmark_matrix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    total_runs = len(models) * len(PARAMETER_GROUPS) * len(BENCHMARK_SUITE)
    
    print(f"Starting Atomic Ad-Manager Matrix Benchmark.")
    print(f"Models: {len(models)} | Configs: {len(PARAMETER_GROUPS)} | Tasks: {len(BENCHMARK_SUITE)}")
    print(f"Total Generations: {total_runs}")
    print(f"Saving to {log_name}")

    with open(log_name, 'w', encoding='utf-8') as f:
        f.write(f"Ollama Atomic Ad-Manager Matrix Benchmark - {datetime.now()}\n")
        f.write(f"Total Scheduled Runs: {total_runs}\n\n")
        
        run_count = 0
        for model in models:
            print(f"\nMODEL: {model}")
            f.write(f"\nMODEL: {model}\n" + "="*80 + "\n")
            
            for param_set in PARAMETER_GROUPS:
                param_desc = str(param_set) if param_set else "OLLAMA_DEFAULTS"
                print(f"  > Parameters: {param_desc}")
                f.write(f"\n  CONFIGURATION: {param_desc}\n  " + "-"*40 + "\n")
                
                for test_name, test_data in BENCHMARK_SUITE.items():
                    run_count += 1
                    print(f"    [{run_count}/{total_runs}] {test_name}...", end="", flush=True)
                    
                    res, dur, m = run_test(model, test_data['prompt'], param_set)
                    
                    log_block = (
                        f"    Test: {test_name}\n"
                        f"    Params: {param_desc}\n"
                        f"    Eval Type: {test_data['eval_type']}\n"
                        f"    Stats: {dur:.2f}s | CPU: {m.max_cpu:.1f}% | RAM: {m.max_ram_mb:.2f}MB | GPU: {m.max_gpu}%\n"
                        f"    EXPECTED: {test_data['expected']}\n"
                        f"    ACTUAL: {res}\n"
                        f"    {'.'*40}\n"
                    )
                    f.write(log_block)
                    print(f" Done ({dur:.2f}s)")

    print(f"\nBenchmark complete. Logs saved to {log_name}")

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()