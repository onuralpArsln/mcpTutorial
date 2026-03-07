# Başlangıç

Pipenv sanal ortama yükle:

```bash
pip install pipenv
python -m pipenv install mcp google-genai pydantic python-dotenv
python -m pipenv install langgraph langchain-google-genai
python -m pipenv install langchain-ollama

```

## GEt Ollama 

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

```bash
ollama run llama3.1
ollama run qwen2.5:3b
```



# 🚀 Kullanım (Draft Final Target)

Sistemi başlatmadan önce `.env` dosyasını oluşturduğunuzdan ve `mcp_config.json` dosyasında sunucularınızın tanımlı olduğundan emin olun.

**Sistemi Çalıştır:**

```bash
python3 -m pipenv run python3 langgraph_system/main.py
```

---

# 📚 Proje Yapısı

Bu repo iki aşamalı bir öğrenme süreci sunar:

1.  **SimpleMCPClient (Başlangıç):** Gemini ile doğrudan iletişim kuran basit bir istemci. (`client.py`)
2.  **LangGraph System (Final Target):** Çoklu LLM desteği, Çoklu MCP sunucu desteği ve Niyet Analizi (Intent Registry) içeren gelişmiş ajan sistemi.

---

# SimpleMCPClient

## client.py
Gemini ile sohbet eder. Toolları MCP'den dinamik olarak çeker ve Gemini'ye iletir:

```python
response = gemini_client.models.generate_content(
    model='gemini-2.5-flash',
    contents=user_input,
    config=types.GenerateContentConfig(
        tools=[tool_config],
    )
)
```

## server.py
MCP sunucusu burada çalışır. Yeni toollar buraya eklenir.



# LangGraphMCP+RagClient
### LangGraph + MCP + RAG Nasıl Çalışır?

Bu sistem, yapay zekanın yerel araçlarla nasıl etkileşime girdiğini üç katmanda yönetir:

1.  **LangGraph:** İş akışını ve "karar verme" sürecini yönetir. Kullanıcının ne istediğini anlar ve hangi aracın ne zaman kullanılacağına karar verir.
2.  **MCP Adapter:** MCP sunucusundan gelen ham araçları, LangGraph'ın (Gemini/Claude) anlayabileceği "LangChain Tool" formatına otomatik olarak dönüştürür.
3.  **MCP Server:** Gerçek işi yapan kısımdır. Dosya yazma, okuma veya RAG (Bilgi tabanı) araması gibi işlemleri gerçekleştirir.

####  Tool Seçimi
Niyet anlaşıldıktan sonra, LLM hangi araçların (Performance, Rules, Pattern vb.) kullanılacağına karar verir.



## workflow

```mermaid
graph TD
    %% Stil ve Renk Tanımlamaları
    classDef default font-family:sans-serif,font-size:14px;
    classDef blueBox fill:#E1F0FF,stroke:#0052CC,stroke-width:2px,color:#172B4D,rx:8px,ry:8px;
    classDef pinkDiamond fill:#FFEBE6,stroke:#FF5630,stroke-width:2px,color:#172B4D;
    classDef finalBox fill:#E3FCEF,stroke:#00875A,stroke-width:2px,color:#172B4D,rx:8px,ry:8px;

    %% Süreçleri Gruplama
    subgraph Asama 1: Girdi
        A["👤 Kullanıcı İstemi"]
        B["🧠 Kullanıcı Niyeti<br>anlaşılması"]
    end

    subgraph Asama 2: Veri ve Hazırlık
        C["🗄️ Data Toplanması<br>(Tool seçimi)"]
        D["📜 Duruma uygun<br>strateji kuralının<br>okunması"]
        E["🛠️ MCP Dataların<br>toollar ile çekilmesi"]
    end

    subgraph Asama 3: Yapay Zeka Analizi
        F["🤖 Analiz 1 MCP<br>ile ML Toolu"]
        G["⚡ Analiz 2 LLM<br>Analizi (ML verisinden<br>faydalanarak)"]
    end

    subgraph Asama 4: Karar ve Sonuç
        H{"⚖️ Conf<br>Puanlaması"}
        I["💡 Çözüm Önerisi"]
        J{"🔍 Kural<br>Kontrolü"}
        K["🎯 Açıklama ve<br>Kullanıcıya Sunum"]
    end

    %% Ana Akış Bağlantıları
    A ==> B ==> C
    
    C ==> D
    C ==> E
    
    D ==> F
    E ==> F
    F ==> G
    G ==> H
    
    H ==>|Yüksek| I
    I ==> J
    J ==>|Uygun| K

    %% Geri Dönüş / Döngü Bağlantıları
    F -.->|Daha fazla veri lazımsa<br>state güncelle ve dön| E
    H -.->|Düşük| C
    J -.->|Uygun Değil| I

    %% Sınıfların Düğümlere Atanması
    class A,B,C,D,E,F,G,I blueBox;
    class H,J pinkDiamond;
    class K finalBox;
```

## State


```mermaid
flowchart LR
    %% --- Stil ve Tema Tanımlamaları ---
    classDef mainStep fill:#1A365D,stroke:#2B6CB0,stroke-width:3px,color:#FFFFFF,rx:8px,ry:8px,font-weight:bold;
    classDef subCategory fill:#EBF8FF,stroke:#3182CE,stroke-width:2px,color:#2C5282,rx:5px,ry:5px;
    classDef metricItem fill:#F0FFF4,stroke:#38A169,stroke-width:1px,color:#22543D,rx:20px,ry:20px;

    %% --- KATMANLAR ---
    A["📥 GİRDİ<br>(İstem, Zaman, Rol)"]:::mainStep
    B["🧠 NİYET<br>(Intent Seçimi)"]:::mainStep
    C["🗄️ VERİ KATMANI"]:::mainStep
    D["📊 ANALİZ<br>(Özet ve Risk)"]:::mainStep
    E["💡 ÖNERİLER<br>(Strateji)"]:::mainStep
    F["💬 AÇIKLAMA"]:::mainStep

    %% --- GİZLİ BAĞLANTILAR (KUTULARI DÜZENLİ TUTMAK İÇİN) ---
    A ==> B ==> C ==> D ==> E ==> F

    %% --- VERİ KATMANI DETAYLARI (Alt Alta) ---
    C --> C1["📜 Kurallar"]:::subCategory
    C --> C2["📈 Performans (ROAS, Ciro, TBM)"]:::subCategory
    C --> C3["💰 Maliyet (Kar Marjı)"]:::subCategory
    C --> C4["📉 Trendler"]:::subCategory

    %% --- AÇIKLAMA DETAYLARI ---
    F -.-> F1["Karar Gerekçesi"]:::subCategory
    F -.-> F2["Kullanılan Veri"]:::subCategory
```

---

---

# 🚀 Yeni Bir Özellik Nasıl Eklenir? 



### 1. Adım: Yeni Yeteneği Tanımla (Python)
`langgraph_system/mcp_server.py` dosyasına git ve yeni fonksiyonunu ekle:

```python
@mcp.tool()
def stok_durumu() -> str:
    """Depodaki ürünlerin sayısını söyler."""
    return "iPhone 15: 10 adet, Samsung S24: 5 adet"
```

### 2. Adım: Yeteneği Yapay Zekaya Bağla (YAML)
`langgraph_system/intents.yaml` dosyasına git ve yeni fonksiyonunu bir **Niyete (Intent)** bağla:

```yaml
# Örnek: 'info_only' niyetine yeni tool'u bağladık
info_only:
  description: "Ürün ve stok bilgilerini verir"
  tools:
    - list_products
    - stok_durumu  # ← Buraya eklediğin an yapay zeka bunu kullanmaya başlar!
```

---

## 🎨 Sisteme Yeni Bir "Niyet" (Grup) Eklemek
Örnek: sisteme **"Raporlama"** adında tamamen yeni bir kategori eklemek:

`intents.yaml` içine şu bloğu yapıştırın:

```yaml
reporting:
  description: "Satış raporları oluşturur ve özetler"
  examples:
    - "bugünkü satış raporunu çıkar"
    - "bu ay ne kadar sattık"
  tools:
    - get_sales_data  # (Bu isimde bir tool'u mcp_server.py'ye eklemiş olmalısın)
```

**Sonuç:** Yapay zeka artık "bugünkü satış raporunu çıkar" dendiğinde otomatik olarak `reporting` kategorisine gidecek ve sadece oradaki araçları kullanacaktır!

---

# 🔌 Çoklu Sunucu (Multi-Server) Yönetimi

Sistem artık aynı anda birden fazla MCP sunucusuna bağlanabilir. Tüm ayarlar projenin kök dizinindeki `mcp_config.json` dosyasından yönetilir.

### Yeni Sunucu Ekleme

`mcp_config.json` dosyasını açın ve `mcpServers` altına yeni bir giriş ekleyin:

```json
{
  "mcpServers": {
    "yerel-analiz": {
      "type": "stdio",
      "command": "python3",
      "args": ["langgraph_system/mcp_server.py"]
    },
    "uzak-veritabani": {
      "type": "stdio",
      "command": "/usr/bin/mcp-server-postgres",
      "args": ["postgresql://user:pass@host:port/db"]
    }
  }
}
```

### Sunucuyu Kapatma (Geçici)
Bir sunucuyu silmeden devre dışı bırakmak için `"disabled": true` eklemeniz yeterlidir.

---

## 💡 Özet: Hangi Dosya Ne İşe Yarar?

| Dosya | Görevi | Ne Zaman Düzenlenir? |
|---|---|---|
| `mcp_config.json` | **Bağlantılar** | Yeni bir MCP sunucusu (DB, Search vb.) eklemek istiyorsan. |
| `mcp_server.py` | **Eller** (İşi yapar) | Senin yazdığın yerel fonksiyonları/araçları düzenlemek istiyorsan. |
| `intents.yaml` | **Harita** (Yol gösterir) | Araçları niyetlere (intent) bağlamak veya gruplamak istiyorsan. |
| `.env` | **Ayar** (LLM seçer) | Gemini veya Ollama arasında geçiş yapmak istiyorsan. |
