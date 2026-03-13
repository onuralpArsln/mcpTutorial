import requests
import time
import threading
import psutil
import glob
import os
import re
from datetime import datetime

# --- CONFIGURATION ---
OLLAMA_API_URL = "http://localhost:11434/api/generate"
# 999 forces all layers to GPU. Ollama will spill to CPU only if VRAM is full.
FORCE_GPU_LAYERS = 999 
# Reduced context saves VRAM, ensuring more of the model fits on your RX 580.
CONTEXT_WINDOW = 2048 
# Increased timeout (10 mins) to prevent crashes during slow CPU/Hybrid runs.
REQUEST_TIMEOUT = 600 

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

def run_test(model_name, prompt):
    """Runs prompt with thinking-filter and long timeout."""
    monitor = ResourceMonitor()
    monitor_thread = threading.Thread(target=monitor.measure)
    monitor_thread.start()

    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_gpu": FORCE_GPU_LAYERS,
            "num_ctx": CONTEXT_WINDOW,
            "temperature": 0
        }
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

    log_name = f"ad_manager_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    print(f"Starting Atomic Ad-Manager Benchmark on {len(models)} models.")
    print(f"Saving to {log_name}")

    with open(log_name, 'w', encoding='utf-8') as f:
        f.write(f"Ollama Atomic Ad-Manager Benchmark - {datetime.now()}\n")
        f.write("Mode: Dependency-Free Atomic Test (rules/context embedded)\n\n")
        
        for model in models:
            print(f"\nMODEL: {model}")
            f.write(f"\nMODEL: {model}\n" + "="*50 + "\n")
            
            for test_name, test_data in BENCHMARK_SUITE.items():
                print(f"  Running: {test_name}...", end="", flush=True)
                res, dur, m = run_test(model, test_data['prompt'])
                
                log_block = (
                    f"Test: {test_name}\n"
                    f"Eval Type: {test_data['eval_type']}\n"
                    f"Time: {dur:.2f}s | CPU: {m.max_cpu:.1f}% | RAM: {m.max_ram_mb:.2f}MB | GPU: {m.max_gpu}%\n"
                    f"EXPECTED: {test_data['expected']}\n"
                    f"ACTUAL: {res}\n"
                    f"{'-'*50}\n"
                )
                f.write(log_block)
                print(f" Done ({dur:.2f}s)")

    print(f"\nBenchmark complete. Logs saved to {log_name}")

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()