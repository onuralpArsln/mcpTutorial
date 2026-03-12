import subprocess
import time
import threading
import psutil
import glob
import os
from datetime import datetime

# 1. Define the logic tests
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

# Auto-detect the RX 580 path on startup
AMD_GPU_PATH = find_amd_gpu()

class ResourceMonitor:
    """Monitors system CPU, RAM, and AMD GPU in a background thread."""
    def __init__(self):
        self.keep_measuring = True
        self.max_cpu = 0.0
        self.max_ram = 0.0
        self.max_gpu = 0.0
        self.max_vram = 0.0  # Tracked in Megabytes (MB)

    def measure(self):
        # Initialize CPU percent
        psutil.cpu_percent(interval=None)
        
        while self.keep_measuring:
            # 1. Measure System CPU & RAM
            cpu = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory().percent
            
            if cpu > self.max_cpu: self.max_cpu = cpu
            if ram > self.max_ram: self.max_ram = ram

            # 2. Measure AMD GPU & VRAM directly from Linux sysfs
            if AMD_GPU_PATH:
                try:
                    with open(os.path.join(AMD_GPU_PATH, 'gpu_busy_percent'), 'r') as f:
                        gpu_util = float(f.read().strip())
                    
                    with open(os.path.join(AMD_GPU_PATH, 'mem_info_vram_used'), 'r') as f:
                        vram_used_bytes = float(f.read().strip())
                        vram_used_mb = vram_used_bytes / (1024 * 1024)
                        
                    if gpu_util > self.max_gpu: self.max_gpu = gpu_util
                    if vram_used_mb > self.max_vram: self.max_vram = vram_used_mb
                except Exception:
                    pass # Ignore read errors during quick sampling

def get_installed_models():
    """Fetches the list of installed models from Ollama."""
    print("Fetching installed models...")
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')[1:]
        models = [line.split()[0] for line in lines if line.strip()]
        return models
    except subprocess.CalledProcessError:
        print("Error: Could not communicate with Ollama. Is the service running?")
        return []

def run_test(model_name, prompt):
    """Runs a single prompt and tracks resources & time."""
    monitor = ResourceMonitor()
    monitor_thread = threading.Thread(target=monitor.measure)
    monitor_thread.start()

    start_time = time.time()
    try:
        result = subprocess.run(
            ['ollama', 'run', model_name, prompt],
            capture_output=True, text=True, check=True
        )
        output = result.stdout.strip()
    except subprocess.CalledProcessError as e:
        output = f"[ERROR] Model failed to respond. Details: {e.stderr.strip()}"
    
    duration = time.time() - start_time
    
    # Stop the monitor thread
    monitor.keep_measuring = False
    monitor_thread.join()

    return output, duration, monitor

def main():
    models = get_installed_models()
    if not models:
        print("No models found. Exiting.")
        return

    print(f"Found {len(models)} models: {', '.join(models)}")
    log_filename = f"ollama_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    with open(log_filename, 'w', encoding='utf-8') as log_file:
        log_file.write(f"--- Ollama Model Benchmark ---\n")
        log_file.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_file.write(f"AMD GPU Detected: {'Yes' if AMD_GPU_PATH else 'No'}\n\n")
        
        for model in models:
            print(f"\n[{model}] Starting tests...")
            log_file.write(f"=========================================\n")
            log_file.write(f"MODEL: {model}\n")
            log_file.write(f"=========================================\n")
            
            for test_name, prompt in PROMPTS.items():
                print(f"  -> Running: {test_name}")
                
                output, duration, metrics = run_test(model, prompt)
                
                log_file.write(f"Test: {test_name}\n")
                log_file.write(f"Time: {duration:.2f} seconds\n")
                log_file.write(f"Peak CPU: {metrics.max_cpu}%\n")
                log_file.write(f"Peak System RAM: {metrics.max_ram}%\n")
                
                if AMD_GPU_PATH:
                    log_file.write(f"Peak AMD GPU Usage: {metrics.max_gpu}%\n")
                    log_file.write(f"Peak VRAM Used: {metrics.max_vram:.2f} MB\n")
                    
                log_file.write(f"Output:\n{output}\n")
                log_file.write(f"-----------------------------------------\n")
                
    print(f"\nDone! Results saved to {log_filename}")

if __name__ == "__main__":
    main()