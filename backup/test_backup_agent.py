import asyncio
import os
import sys
from datetime import datetime

# Add the root directory to sys.path so we can import simple_agent
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

from backup.simple_agent import BackupAgent

# --- TEST QUESTIONS ---
QUESTIONS = [
    "Hangi pet (evcil hayvan) ürünlerimiz var?",
    "Peki bunlardan en çok hangisi harcama yaptı? (Bağlam Testi)",
    "Bu harcamayı neye borçlu, gösterim sayısı mı yüksek yoksa tıklanma mı? (Bağlam + Derinlik Testi)",
    "ZAYNABED160X200 ürününü incele.",
    "Bunun ROAS'ı dünden bugüne nasıl değişti? (Bağlam Testi)",
    "Neden böyle bir değişim olmuş olabilir, bütçesi mi artmış? (Bağlam + Analiz Testi)",
    "Cebimde ekstra 500 TL var, sence hangi ürünlerin bütçesine paylaştırmalıyım?",
    "Bu tavsiyeyi verirken neye dikkat ettin? (Sohbet Testi)",
    # --- SON 3'LÜ BAĞLAMSAL SERİ ---
    "XPETMERD4DENYE ürününe odaklanalım. Bu ürünün temel metrikleri nedir?",
    "Şu anki TBM teklifi ile piyasadaki önerilen TBM (onerilen_tbm) arasında ne kadar fark var? (Pekala, bu ürün için)",
    "Bu farkı kapatmak için teklifi artırırsak, mevcut günlük bütçemiz harcamayı karşılar mı?"
]

async def run_backup_tests():
    print("🚀 Starting Contextual Backup Agent Test Suite...")
    agent = BackupAgent()
    history = [] # Mesaj geçmişi burada tutulacak
    active_product = None # Odak ürün kilidi
    
    output_file = os.path.join(root_dir, "backup", "test_log_gem_backup.txt")
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"--- BACKUP AGENT CONTEXTUAL TEST LOG ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---\n")
        f.write(f"Model ID: {agent.model_id}\n\n")

    if await agent.connect():
        try:
            for i, q in enumerate(QUESTIONS, 1):
                print(f"\n--- Question {i}/{len(QUESTIONS)}: {q} ---")
                
                # 1. SQL Üret (History + Product State ile)
                print("⏳ Generating SQL...")
                
                # Yeni ürün tespiti ve kilit güncelleme
                new_product = agent.extract_product_code(q)
                if new_product:
                    active_product = new_product
                    print(f"🔒 Product Lock Updated: {active_product}")

                sql = await agent.generate_sql(q, history=history, active_product=active_product)
                
                if sql.startswith("[DIRECT_ANSWER]"):
                    answer = sql.replace("[DIRECT_ANSWER]", "").strip()
                    db_result = "N/A (Direct Answer)"
                    print(f"💬 Direct Answer: {answer[:50]}...")
                else:
                    print(f"💾 SQL: {sql}")
                    
                    # 2. SQL Çalıştır
                    print("📊 Executing SQL...")
                    db_result = await agent.execute_sql(sql)
                    
                    # 3. Cevap Üret (History + Product State ile)
                    print("🧠 Generating Answer...")
                    answer = await agent.get_answer(q, sql, db_result, history=history, active_product=active_product)
                
                # 4. Geçmişi Güncelle (Streamlit ile aynı yapı)
                history.append({"role": "user", "content": q})
                history.append({"role": "assistant", "content": answer, "sql": sql if "[DIRECT_ANSWER]" not in sql else None})

                # Log yaz
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(f"QUESTION {i}: {q}\n")
                    f.write(f"[SQL SORGUSU]: {sql}\n")
                    f.write(f"[DB SONUCU]: {db_result}\n")
                    f.write(f"[CEVAP]:\n{answer}\n")
                    f.write(f"\n{'='*50}\n\n")
                
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
