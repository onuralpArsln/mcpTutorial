import asyncio
import os
import sys
from datetime import datetime

# Add the root directory to sys.path so we can import simple_agent
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

from backup.simple_agent import BackupAgent

questions = [
    "Hangi puf modellerimiz var?",
    "Tüm ürünleri listeler misin?",
    "XSANDMIN4514BISDENY kodlu ürünün harcama getirisi (ROAS) ve ciro nedir?",
    "XPUFFY4040KAREPUF için harcanan net bütçe kaç?",
    "ZAYNABED160X200 ile MINIPUFROUND'u kıyasla, hangisinin ROAS'ı (harcama_getirisi) daha yüksek?",
    "XSANDMIN04DENY6'ün ROAS'ı nedir ve bu sayı 1'den büyük mü? (Matematik testi)",
    "Cebimde ekstra 500 TL var, sence hangi ürünlerin bütçesine paylaştırmalıyım?",
    "XPUFFY için strateji kuralları nelerdir ve şu an uygulanan teklifle kıyaslandığında ne yapılmalı?",
    # --- TRICKY QUESTIONS ---
    "Reklam getirisi (ROAS) en yüksek olan ilk 3 ürünü listele.",
    "Bütçesi olmasına rağmen hiç harcama yapmayan (tıkanmış) ürünleri bul.",
    "İçinde 'PUF' geçen ürünlerin toplam reklam cirosu nedir?",
    "ZAYNABED160X200 ürünündeki net satış cirosu ile reklam cirosu arasındaki fark nedir?"
]

async def run_backup_tests():
    print("🚀 Starting Backup Agent Test Suite...")
    agent = BackupAgent()
    
    output_file = os.path.join(root_dir, "backup", "test_log_gem_backup.txt")
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"--- BACKUP AGENT TEST LOG ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---\n")
        f.write(f"Model ID: {agent.model_id}\n\n")

    if await agent.connect():
        try:
            for i, q in enumerate(questions, 1):
                print(f"\n--- Question {i}/{len(questions)}: {q} ---")
                
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(f"QUESTION {i}: {q}\n")

                print("⏳ Generating SQL...")
                sql = await agent.generate_sql(q)
                print(f"💾 SQL: {sql}")
                
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(f"[SQL SORGUSU]: {sql}\n")

                print("📊 Executing SQL...")
                db_result = await agent.execute_sql(sql)
                
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(f"[DB SONUCU]: {db_result}\n")

                print("🧠 Generating Answer...")
                answer = await agent.get_answer(q, sql, db_result)
                
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(f"[CEVAP]:\n{answer}\n\n{'='*50}\n\n")
                
                print(f"✅ Finished Question {i}")

        except Exception as e:
            print(f"❌ Error during tests: {e}")
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(f"\n[CRITICAL ERROR]: {e}\n")
        finally:
            await agent.close()
            print(f"\n🏁 Tests completed. Results saved to '{output_file}'.")
    else:
        print("❌ Failed to connect to MCP servers.")

if __name__ == "__main__":
    asyncio.run(run_backup_tests())
