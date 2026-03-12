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

PROMPTS = {
    "Intent Detection": "Classify the intent of the following user query into exactly one of these three categories: [SQL, RAG, CHAT]. User Query: 'How many active carriers bid on jobs last week?' Rule: Output ONLY the category name. Do not add any other words.",
    "Tool Selection": "I have two tools: 'sql_db' and 'vector_rag'. Which tool should I use for this query: 'What is the standard company policy for handling delayed cargo?' Answer in exactly one sentence.",
    "SQL Generation": "Given the database table 'cargo_jobs' with columns 'id', 'status', and 'carrier_id', write a PostgreSQL query to count how many jobs currently have the status 'bidding_open'. Output ONLY the SQL query, no markdown or explanations."
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
        self.max_gpu = 0.0
        self.max_vram = 0.0

    def measure(self):
        psutil.cpu_percent(interval=None)
        while self.keep_measuring:
            cpu = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory().percent
            if cpu > self.max_cpu: self.max_cpu = cpu
            if ram > self.max_ram: self.max_ram = ram
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

    log_name = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    print(f"Starting benchmark on {len(models)} models. Saving to {log_name}")

    with open(log_name, 'w', encoding='utf-8') as f:
        f.write(f"Ollama GPU Benchmark - {datetime.now()}\n\n")
        for model in models:
            print(f"Testing: {model}")
            f.write(f"MODEL: {model}\n" + "="*30 + "\n")
            for name, prompt in PROMPTS.items():
                res, dur, m = run_test(model, prompt)
                log_line = (f"Test: {name}\nTime: {dur:.2f}s | "
                            f"GPU: {m.max_gpu}% | VRAM: {m.max_vram:.2f}MB\n"
                            f"Verdict: {res}\n" + "-"*30 + "\n")
                f.write(log_line)
                print(f"  - {name}: {dur:.2f}s")

if __name__ == "__main__":
    main()