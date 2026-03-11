import sys
import os
import json
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Watch the directory where streamlit_app.py saves history
HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_history")

class HistoryHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.last_counts = {}
        # Initial scan to know the baseline
        self._initialize_counts()

    def _initialize_counts(self):
        if not os.path.exists(HISTORY_DIR):
            return
        
        for filename in os.listdir(HISTORY_DIR):
            if filename.endswith(".json"):
                path = os.path.join(HISTORY_DIR, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            self.last_counts[filename] = len(data)
                except Exception:
                    self.last_counts[filename] = 0

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith(".json"):
            return
        
        filename = os.path.basename(event.src_path)
        # Small delay to ensure the file is completely written
        time.sleep(0.1)
        self.process_file(event.src_path, filename)

    def process_file(self, path, filename):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                return

            new_count = len(data)
            old_count = self.last_counts.get(filename, 0)
            
            if new_count > old_count:
                new_messages = data[old_count:]
                username = filename.replace(".json", "").capitalize()
                
                for msg in new_messages:
                    role = msg.get("role", "unknown").upper()
                    content = msg.get("content", "")
                    
                    if role == "USER":
                        print(f"\n[👤 {username}] NEW USER QUESTION:")
                        print(f"   {content}")
                    elif role == "ASSISTANT":
                        print(f"\n[🤖 {username}] NEW BOT ANSWER:")
                        print(f"   {content}")
                        if "sql" in msg:
                            print(f"   (📊 SQL: {msg['sql'].splitlines()[0]}...)")
                    
                    print("-" * 40)
                
                self.last_counts[filename] = new_count
        except Exception:
            # Silent fail for read errors (often concurrent access)
            pass

def main():
    if not os.path.exists(HISTORY_DIR):
        print(f"Creating missing directory: {HISTORY_DIR}")
        os.makedirs(HISTORY_DIR, exist_ok=True)

    event_handler = HistoryHandler()
    observer = Observer()
    observer.schedule(event_handler, HISTORY_DIR, recursive=False)
    
    print("=" * 50)
    print(f"👀 ROB Monitor started")
    print(f"📂 Watching: {HISTORY_DIR}")
    print("=" * 50)
    
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n👋 Monitor stopping...")
    observer.join()

if __name__ == "__main__":
    main()
