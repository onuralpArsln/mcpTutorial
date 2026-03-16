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
    #{"temperature": 0, "num_predict": 100}, # CONCISE: Speed optimized, low token limit for short intents
    #{"temperature": 0.1, "top_p": 0.4} # FOCUSED: Balanced for RAG/Policy extraction, low noise
]

# --- EMBEDDED KNOWLEDGE (ATOMIC RULES) ---
SQL_RULES = """
- DOUBLE AGGREGATION: For historical totals, use SUM(daily_max) from a subquery grouping by (sorgu_tarihi, urun_kodu).
- ONERILEN_TBM: This is a TEXT field. Extract numeric with REGEXP_REPLACE(onerilen_tbm, '[^0-9.]', '', 'g')::NUMERIC.
- ILIKE for product codes. Use ID DESC LIMIT 1 for latest values.
"""

# --- ATOMIC BENCHMARK SUITE (10 Categories x 2 Variations) ---
# --- ATOMIC BENCHMARK SUITE (v3: Structured & Realistic) ---
# Today's Date Context for SQL: 2026-03-14 Saturday
BENCHMARK_SUITE = {
    "1a. Intent Classification (Vague)": {
        "system": "Görevin kullanıcı mesajını inceleyerek intent analizi yapmak. Seçenekler: [reklam_analiz, teknik_destek, kampanya_yonetimi, selamlasma]. Sadece intent ismini döndür.",
        "user": "Dün noldu?",
        "expected": "reklam_analiz",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "1b. Intent Classification (Easy)": {
        "system": "Görevin kullanıcı mesajını inceleyerek intent analizi yapmak. Seçenekler: [reklam_analiz, teknik_destek, kampanya_yonetimi, selamlasma].",
        "user": "Dünkü reklam harcamalarımı ve toplam satış adedimi göster.",
        "expected": "reklam_analiz",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "2a. Tool Selection (Vague)": {
        "system": "Aşağıdaki araçlardan hangisini kullanmalısın? Araçlar: [sql_db: Veritabanı sorgular, calculator: Matematiksel işlem yaparlar, policy_rag: Reklam politikalarını kontrol eder]. Sadece araç adını yaz.",
        "user": "Karlılık hesapla.",
        "expected": "calculator or sql_db",
        "eval_type": "MANUAL_REVIEW"
    },
    "2b. Tool Selection (Easy)": {
        "system": "Kullanıcı sorusuna göre en uygun aracı seç. Araçlar: [sql_db: Veritabanından reklam verisi çeker, calculator: Kar/Zarar/ROAS hesaplar, policy_rag: Trendyol/Amazon kurallarını bilir].",
        "user": "Elimdeki 500 TL bütçe ile en yüksek ROAS'lı ürünlere nasıl dağıtım yapmalıyım?",
        "expected": "sql_db",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "3a. SQL Gen - Double Agg (Vague)": {
        "system": f"Sen bir Senior SQL Engineer'sın. PostgreSQL kullanıyoruz. Bugünün tarihi: 2026-03-14. Kurallar: {SQL_RULES}.",
        "user": "Geçen haftaki (Monday to Sunday) toplam bütçe harcaması nedir?",
        "expected": "SQL with specific week filter (2026-03-02 to 2026-03-08)",
        "eval_type": "MANUAL_REVIEW"
    },
    "3b. SQL Gen - Double Agg (Easy)": {
        "system": f"Sen bir Senior SQL Engineer'sın. Bugünün tarihi: 2026-03-14. Kurallar: {SQL_RULES}. Sadece SQL kodunu ver.",
        "user": "product_report tablosunda son 7 günün 'harcanan_butce' günlük maksimumlarını toplayan SQL'i yaz.",
        "expected": "SELECT SUM(daily_max) FROM (SELECT MAX(harcanan_butce) WHERE date >= '2026-03-07' ...)",
        "eval_type": "PASS/FAIL (SQL Snippet)"
    },
    "4a. SQL Gen - RegEx (Vague)": {
        "system": "onerilen_tbm sütunu 'Önerilen: 3,28 ₺ (En iyi 5,26 ₺)' formatındadır. Görevin 'Önerilen' olan ilk fiyatı çekmektir.",
        "user": "Önerilen TBM (baz rakam) kaç?",
        "expected": "SQL extracting 3.28",
        "eval_type": "MANUAL_REVIEW"
    },
    "4b. SQL Gen - RegEx (Easy)": {
        "system": f"Uzman SQL yazılımcısı olarak, onerilen_tbm içinden 'En iyi' (parantez içindeki) fiyatı Regex ile çekip tbm_teklif ile farkını alan SQL'i oluştur. Kurallar: {SQL_RULES}.",
        "user": "En iyi TBM ile mevcut teklif farkını bulan SQL yaz.",
        "expected": "REGEXP_REPLACE with second capture group or similar",
        "eval_type": "PASS/FAIL (SQL Snippet)"
    },
    "5a. Math - Discount (Vague)": {
        "system": "E-ticaret analisti asistanısın. Ürün Fiyatı: 200 TL. Senaryo: %10 mağaza indirimi ve üzerine 20 TL kupon uygulanacak.",
        "user": "Bu indirimler sonrası ürün kaça gelir? Adım adım açıkla.",
        "expected": "160 TL (200 * 0.9 - 20)",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "5b. Math - Discount (Easy)": {
        "system": "Matematik asistanısın. Şu veriyi hesapla: Ürün 1000 TL. Önce %20 kampanya indirimi, sonra kalan tutar üzerinden %10 sadakat indirimi uygulanıyor.",
        "user": "Müşterinin ödeyeceği nihai fiyat nedir? İşlemleri göster.",
        "expected": "720 TL (1000 * 0.8 * 0.9)",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "6a. Analyst - Risk (Vague)": {
        "system": "Karar Destek Sistemisin. Risk Kuralı: Harcama > 100 ve Satış = 0. Veri: [A: 150 spend/0 sales, B: 50 spend/0 sales, C: 200 spend/2 sales].",
        "user": "Hangi ürünler 'Kritik Risk' altında? Neden?",
        "expected": "Ürün A",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "6b. Analyst - Risk (Easy)": {
        "system": "Ürün Analisti: Üç ürünü karşılaştır: [Puf1: 300 spend/0 sale, Puf2: 300 spend/5 sales, Puf3: 50 spend/0 sales]. Kural: Spend > 100 & Sales=0 ise Risk.",
        "user": "Riskli olanları listele.",
        "expected": "Puf1",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "7a. Policy RAG (Vague)": {
        "system": "Sen bir politika uzmanısın. Kurallar: Standart iade 14 gün. Kampanyalı (indirimli) ürünlerde 7 gün. Kişiselleştirilmiş ürünlerde iade yok.",
        "user": "Kişiselleştirilmiş bir puf aldım, iade edebilir miyim?",
        "expected": "Hayır / İade yok",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "7b. Policy RAG (Easy)": {
        "system": "[Policies_Extract]: 'İade süreci ürün kategorisine göre değişir. Elektronik 14 gündür. Tekstil ürünlerinde hijyen bandı açılmadıysa 14 gündür. Kampanyalı ürünler 7 gündür.'",
        "user": "Kampanyalı bir tekstil ürünü aldım, iade sürem nedir?",
        "expected": "7 gün",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "8a. Explainer - Turkish (Vague)": {
        "system": "Teknik Analist: Veri [Harcama: 500 TL, Satış: 2500 TL, ROAS: 5.0, Satılan Adet: 12]. Teknik terim boğmadan kullanıcıyı tebrik eden bir özet yaz.",
        "user": "Bu performansı bana Türkçe ve arkadaşça açıkla.",
        "expected": "Friendly Turkish, mentions success",
        "eval_type": "MANUAL_REVIEW"
    },
    "8b. Explainer - Turkish (Easy)": {
        "system": "Performans Özeti: [Ürün: X, ROAS: 1.2 (Hedef 4.0), Spend: 1000 TL]. Kullanıcıya durumun ciddiyetini ama çözüm odaklı bir dille anlat.",
        "user": "Kötü giden bu tabloyu kullanıcıya nasıl açıklarsın?",
        "expected": "Serious but solution oriented, Turkish",
        "eval_type": "MANUAL_REVIEW"
    },
    "9a. Comparison - Strategy (Vague)": {
        "system": "Stratejist: Ürün A (ROAS 1.5, Spend 400 TL), Ürün B (ROAS 6.0, Spend 50 TL). Kârlılık için hangisine bütçe kaydırılmalı?",
        "user": "Bir öneri yap ve nedenini söyle.",
        "expected": "Ürün B (Higher ROAS)",
        "eval_type": "MANUAL_REVIEW"
    },
    "9b. Comparison - Strategy (Easy)": {
        "system": "Veri: [ROAS: 1.1, TBM: 2.50 TL, Önerilen TBM: 4.0 TL]. Strateji A: TBM düşür (ROAS artar/Hacim düşer), B: TBM artır (Hacim artar/ROAS düşer).",
        "user": "Mevcut kârsızlığı çözmek için hangi strateji uygulanmalı?",
        "expected": "Strateji A",
        "eval_type": "MANUAL_REVIEW"
    },
    "10a. Data Formatter (Vague)": {
        "system": "Sadece JSON döndüren bir robotsun. Veri: Mavi Puf (ID 1), Kırmızı Puf (ID 2).",
        "user": "Ürünleri {'items': [{'id': ..., 'name': ...}]} formatında ver.",
        "expected": '{"items": [{"id": 1, "name": "Mavi Puf"}, {"id": 2, "name": "Kırmızı Puf"}]}',
        "eval_type": "PASS/FAIL (JSON)"
    },
    "10b. Data Formatter (Easy)": {
        "system": "Metni JSON'a dönüştür: 'Ali'nin 5 elması, Ayşe'nin 3 armudu var.'",
        "user": "{'person': string, 'fruit': string, 'count': int} şemasında bir liste döndür.",
        "expected": '[{"person": "Ali", "fruit": "elma", "count": 5}, {"person": "Ayşe", "fruit": "armut", "count": 3}]',
        "eval_type": "PASS/FAIL (JSON)"
    },
    "11. Contextual - Recall": {
        "system": "Chat History:\nH: Merhaba, reklamlar nasıl?\nA: Merhaba! Son 24 saatte ROAS 4.2 ile stabil gidiyoruz.\nH: Harika. XPET4545 kodlu ürüne odaklanalım.\nA: XPET4545 için harcama 150 TL, satış 0 görünüyor. Dikkatli olmalısın.\nH: Anladım. Peki kuralımız neydi?\nA: 100 TL harcama üstü ve 0 satış ise ürünü kapatıyoruz.",
        "user": "Biz şu an hangi ürünü konuşuyoruz?",
        "expected": "XPET4545",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "12. Contextual - SQL Scope": {
        "system": f"Chat History:\nH: Merhaba, reklamlar nasıl?\nA: Merhaba! Son 24 saatte ROAS 4.2 ile stabil gidiyoruz.\nH: Harika. XPET4545 kodlu ürüne odaklanalım.\nA: XPET4545 için harcama 150 TL, satış 0 görünüyor. Dikkatli olmalısın.\nH: Anladım. Peki kuralımız neydi?\nA: 100 TL harcama üstü ve 0 satış ise ürünü kapatıyoruz.\nRules: {SQL_RULES}",
        "user": "Bu ürün için tüm zamanların cirosunu getiren SQL'i yaz.",
        "expected": "SQL with XPET4545 filter and Double Aggregation",
        "eval_type": "PASS/FAIL (SQL Snippet)"
    },
    "13. Contextual - Decision": {
        "system": "Chat History:\nH: Merhaba, reklamlar nasıl?\nA: Merhaba! Son 24 saatte ROAS 4.2 ile stabil gidiyoruz.\nH: Harika. XPET4545 kodlu ürüne odaklanalım.\nA: XPET4545 için harcama 150 TL, satış 0 görünüyor. Dikkatli olmalısın.\nH: Anladım. Peki kuralımız neydi?\nA: 100 TL harcama üstü ve 0 satış ise ürünü kapatıyoruz.",
        "user": "Bu ürünü şu an kapatmalı mıyım? Neden?",
        "expected": "Evet, harcama 150 TL (> 100) ve satış 0.",
        "eval_type": "MANUAL_REVIEW"
    },
    "14. Contextual - Mode Switch": {
        "system": "Chat History:\nH: Merhaba, reklamlar nasıl?\nA: Merhaba! Son 24 saatte ROAS 4.2 ile stabil gidiyoruz.\nH: Harika. XPET4545 kodlu ürüne odaklanalım.\nA: XPET4545 için harcama 150 TL, satış 0 görünüyor. Dikkatli olmalısın.\nH: Anladım. Peki kuralımız neydi?\nA: 100 TL harcama üstü ve 0 satış ise ürünü kapatıyoruz.",
        "user": "Selam! Bugunun kisa ve arkadas canlisi bir ozetini gecer misin?",
        "expected": "Friendly greeting, summary of activity, no technical SQL.",
        "eval_type": "MANUAL_REVIEW"
    },
    "15. Contextual - Numerical": {
        "system": "Chat History:\nH: Baz fiyat 500 TL.\nA: Kaydedildi.\nH: %20 indirim yap.\nA: Fiyat 400 TL oldu.\nH: 25 TL kargo ekle.\nA: Toplam 425 TL.",
        "user": "Musteri bundan 2 tane alirsa toplam ne oder?",
        "expected": "850",
        "eval_type": "PASS/FAIL (Exact)"
    },
    "16. Contextual - Synthesis": {
        "system": f"Chat History:\nH: Merhaba, reklamlar nasıl?\nA: Merhaba! Son 24 saatte ROAS 4.2 ile stabil gidiyoruz.\nH: Harika. XPET4545 kodlu ürüne odaklanalım.\nA: XPET4545 için harcama 150 TL, satış 0 görünüyor. Dikkatli olmalısın.\nH: Anladım. Peki kuralımız neydi?\nA: 100 TL harcama üstü ve 0 satış ise ürünü kapatıyoruz.\nRules: {SQL_RULES}",
        "user": "Kuralı ve ürünü birleştirerek bir aksiyon önerisi yaz.",
        "expected": "Recommendation to turn off XPET4545 due to rule violation.",
        "eval_type": "MANUAL_REVIEW"
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

def format_timing_table(timing_data, models, tasks):
    """Generates a formatted markdown-style table of average durations."""
    header = "| Task " + "".join([f"| {m} " for m in models]) + "|"
    separator = "| :--- " + "".join(["| :--- " for _ in models]) + "|"
    
    lines = [header, separator]
    
    totals = {m: 0.0 for m in models}
    task_count = len(tasks)
    
    for t_name in tasks:
        line = f"| {t_name} "
        for m_name in models:
            # Average across parameter sets for this model/task
            durations = timing_data.get(m_name, {}).get(t_name, [])
            avg_dur = sum(durations) / len(durations) if durations else 0.0
            line += f"| {avg_dur:.2f}s "
            totals[m_name] += avg_dur
        line += "|"
        lines.append(line)
    
    # Final average footer
    footer_sep = "| " + "-"*20 + "".join(["| " + "-"*10 for _ in models]) + "|"
    lines.append(footer_sep)
    
    footer = "| **GENEL ORTALAMA** "
    for m_name in models:
        gen_avg = totals[m_name] / task_count if task_count > 0 else 0.0
        footer += f"| **{gen_avg:.2f}s** "
    footer += "|"
    lines.append(footer)
    
    return "\n".join(lines)

def run_test(model_name, sys_prompt, usr_prompt, extra_options=None):
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

    # Realistic Agentic Prompt Construction
    full_prompt = f"System: {sys_prompt}\n\nUser: {usr_prompt}"

    payload = {
        "model": model_name,
        "prompt": full_prompt,
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
    
    # To store: {model_name: {test_name: [durations]}}
    timing_stats = {m: {t: [] for t in BENCHMARK_SUITE.keys()} for m in models}

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
                    
                    res, dur, m = run_test(model, test_data['system'], test_data['user'], param_set)
                    timing_stats[model][test_name].append(dur)
                    
                    log_block = (
                        f"    Test: {test_name}\n"
                        f"    Params: {param_desc}\n"
                        f"    System Context: {test_data['system'][:150]}...\n"
                        f"    User Query: {test_data['user']}\n"
                        f"    Eval Type: {test_data['eval_type']}\n"
                        f"    Stats: {dur:.2f}s | CPU: {m.max_cpu:.1f}% | RAM: {m.max_ram_mb:.2f}MB | GPU: {m.max_gpu}%\n"
                        f"    EXPECTED: {test_data['expected']}\n"
                        f"    ACTUAL: {res}\n"
                        f"    {'.'*40}\n"
                    )
                    f.write(log_block)
                    print(f" Done ({dur:.2f}s)")

        # FINAL SUMMARY TABLE
        f.write("\n\n" + "="*80 + "\n")
        f.write("PERFORMANS ÖZETİ (Ortalama Tamamlama Süreleri - Saniye)\n")
        f.write("="*80 + "\n\n")
        table_str = format_timing_table(timing_stats, models, list(BENCHMARK_SUITE.keys()))
        f.write(table_str)
        f.write("\n\nBenchmark complete.\n")

    print(f"\nBenchmark complete. Summary table appended. Logs saved to {log_name}")

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()