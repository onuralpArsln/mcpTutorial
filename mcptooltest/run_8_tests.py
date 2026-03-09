import asyncio
import sys
import os
import json
from langchain_core.messages import HumanMessage, AIMessage

# Ensure python can find langgraph_system modules
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "langgraph_system"))

from main import initialize_agent

questions = [
    "Hangi puf modellerimiz var?",
    "Tüm ürünleri listeler misin?",
    "ZAYNABED160X200 kodlu ürünün harcama getirisi (ROAS) ve ciro nedir?",
    "XPUFFY4040KAREPUF için harcanan net bütçe kaç?",
    "ZAYNABED160X200 ile MINIPUFROUND'u kıyasla, hangisinin ROAS'ı (harcama_getirisi) daha yüksek?",
    "ZAYNABED160X200'ün ROAS'ı nedir ve bu sayı 1'den büyük mü? (Matematik testi)",
    "Cebimde ekstra 500 TL var, sence hangi ürünlerin bütçesine paylaştırmalıyım?",
    "XPUFFY için strateji kuralları nelerdir ve şu an uygulanan teklifle kıyaslandığında ne yapılmalı?"
]

async def run_tests():
    print("Testing 8 progressive questions...")
    app, exit_stack = await initialize_agent()
    if not app:
        print("Agent initialization failed.")
        return

    output_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "text.txt")
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("--- MCP LANGGRAPH 8-QUESTION TEST LOG ---\n\n")

    try:
        chat_history = []
        context_summary = ""

        for i, q in enumerate(questions, 1):
            print(f"\n--- Soru {i}/{len(questions)}: {q} ---")
            
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(f"SORU {i}: {q}\n")

            new_human_msg = HumanMessage(content=q)
            # Only append the new question to history to prevent context overflow in small models
            # We'll keep basic history but truncate to last 4 messages to be safe
            chat_history.append(new_human_msg)
            if len(chat_history) > 4:
                chat_history = chat_history[-4:]

            inputs = {
                "messages": chat_history,
                "intent": "unknown",
                "context_summary": context_summary,
            }

            final_response_text = ""
            intent_found = "unknown"
            
            async for output in app.astream(inputs, stream_mode="updates"):
                for node, data in output.items():
                    if node == "intent":
                        intent_found = data.get('intent', 'unknown')
                        print(f"  -> Niyet Anlaşıldı: {intent_found}")
                        with open(output_file, "a", encoding="utf-8") as f:
                            f.write(f"[NİYET (INTENT)]: {intent_found}\n")
                    elif node == "tool_selection":
                        if "messages" in data:
                            m = data["messages"][-1]
                            if hasattr(m, 'tool_calls') and m.tool_calls:
                                tool_names = [tc['name'] for tc in m.tool_calls]
                                with open(output_file, "a", encoding="utf-8") as f:
                                    f.write(f"[SEÇİLEN ARAÇLAR]: {', '.join(tool_names)}\n")
                                
                                for tc in m.tool_calls:
                                    if tc['name'] == "query":
                                        args = tc.get('args', {})
                                        query_str = args.get('sql') or args.get('query') or str(args)
                                        with open(output_file, "a", encoding="utf-8") as f:
                                            f.write(f"[SQL SORGUSU]: {query_str}\n")
                    elif node == "explainer":
                        if "messages" in data:
                            m = data["messages"][-1]
                            content = m.content
                            if isinstance(content, list):
                                text_parts = [part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
                                final_response_text = "".join(text_parts).strip()
                            else:
                                final_response_text = str(content).strip()
                        if "context_summary" in data:
                            context_summary = data["context_summary"]

            if final_response_text:
                chat_history.append(AIMessage(content=final_response_text))
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(f"[CEVAP]:\n{final_response_text}\n\n{'='*50}\n\n")
                print(f"  -> Cevap alındı ve text.txt dosyasına yazıldı.")
            else:
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(f"[HATA]: Cevap oluşturulamadı.\n\n{'='*50}\n\n")
                    
    finally:
        await exit_stack.aclose()
        print(f"\nTest tamamlandı. Sonuçlar '{output_file}' dosyasına kaydedildi.")

if __name__ == "__main__":
    asyncio.run(run_tests())
