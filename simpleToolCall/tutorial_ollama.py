import asyncio
from typing import List, Dict, Any
import datetime
import random

# We use langchain_ollama which is already in the project dependencies
try:
    from langchain_ollama import ChatOllama
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
    from langchain_core.tools import tool
except ImportError:
    print("Hata: 'langchain_ollama' veya 'langchain_core' bulunamadı.")
    print("Lütfen yükleyin: pip install langchain-ollama langchain-core")
    exit(1)

# --- 1. Tool Tanımlamaları ---
# @tool dekoratörü, fonksiyonu LangChain'in anlayabileceği bir formata sokar.
# Docstring (açıklama) LLM'in bu toolu ne zaman kullanacağını anlaması için kritiktir.

@tool
def get_current_time() -> str:
    """Şu anki saati ve tarihi döndürür."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@tool
def get_random_fact() -> str:
    """Rastgele ve ilginç bir bilgi döndürür."""
    facts = [
        "Ahtapotların üç kalbi vardır.",
        "Bal asla bozulmayan tek besindir.",
        "Penguenler diz çöker ama dışarıdan görünmez.",
        "İnsan beyni yaklaşık 20 watt elektrik üretir."
    ]
    return random.choice(facts)

@tool
def calculate_ritchet(s1: float, s2: float) -> str:
    """
    Verilen iki sayı için 'Ritchet' değerini hesaplar.
    Ritchet = (Sayıların Toplamı) * (Sayıların Farkı)
    Formula: (s1 + s2 + s3) * (s1 - s2 - s3)
    """
    toplam = s1 + s2 
    fark = s1 - s2
    sonuc = toplam * fark
    return f"{s1} ve {s2} değerleri için Ritchet sonucu: {sonuc}"

# Kullanacağımız tool listesi
tools = [get_current_time, get_random_fact, calculate_ritchet]

# --- 2. Model Kurulumu ---
# Ollama'nın lokalde çalıştığını varsayıyoruz. 
# Model ismi olarak ReadMe'de önerilen qwen2.5:3b'yi kullanıyoruz.
llm = ChatOllama(
    model="qwen2.5:3b",
    temperature=0,
).bind_tools(tools) # Toolları modele bağlıyoruz

# --- 3. Ana Akış ---
async def main():
    print("--- Ollama Tool Call Tutorial ---")
    print("Toollar: get_current_time, get_random_fact, calculate_ritchet")
    print("Çıkmak için 'q' yazın.\n")

    messages = [
        SystemMessage(content="Sen yardımcı bir asistansın. Soruları cevaplamak için mevcut araçları kullanabilirsin.")
    ]

    while True:
        user_input = input("Siz: ")
        if user_input.lower() == 'q':
            break

        messages.append(HumanMessage(content=user_input))

        # Modelden yanıt al
        response = llm.invoke(messages)
        
        # Eğer model bir tool çağrısı yapmak istiyorsa:
        if response.tool_calls:
            print(f"\n[SİSTEM] Model tool çağrısı yapıyor: {[tc['name'] for tc in response.tool_calls]}")
            
            messages.append(response) # Modelin tool call isteğini geçmişe ekle

            for tool_call in response.tool_calls:
                # Parametrelerin nerede belirlendiğini görmek için yazdıralım
                print(f"   -> Parametreler: {tool_call['args']}")

                # Tool ismine göre ilgili fonksiyonu bul ve çalıştır
                selected_tool = next(t for t in tools if t.name == tool_call["name"])
                tool_output = selected_tool.invoke(tool_call)
                
                # Sonucu ToolMessage olarak ekle
                messages.append(ToolMessage(
                    content=str(tool_output),
                    tool_call_id=tool_call["id"]
                ))
            
            # Tool sonuçlarıyla birlikte modeli tekrar çağır (Nihai yanıt için)
            final_response = llm.invoke(messages)
            print(f"Asistan: {final_response.content}")
            messages.append(final_response)
        else:
            # Tool çağrısı yoksa direkt yanıtı yazdır
            print(f"Asistan: {response.content}")
            messages.append(response)

if __name__ == "__main__":
    asyncio.run(main())
