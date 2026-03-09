When assistans asked to get data i.e. "en fazla roası olan ürün", "roası ortalam altı olan ürünler" ,"hangi ürünler var" , "ürünlerin son  hafta tıklanma ortalaması" gibi sadece data çekme görevlerind sql yazılsın uygulansın sonucu insan okunur olaarak iletilsin.



geniş bir analiz istenince 

örneğin  bir ürüne ait tıklanma trendleri outliers etc db çekiminden sonra naliz nodu ve insan okunur olmalı 

### Yapılabilecek Tahmini Analizler (Plan)
Veritabanı kolonlarına (`harcanan_butce`, `gosterim_sayisi`, `tiklanma_sayisi`, `reklam_cirosu`, `harcama_getirisi`, `gerceklesen_tbm`, `tbm_teklif`, `onerilen_tbm`, `satis_adet`, `net_satis`) dayanarak eklenecek olan derin analiz yetenekleri (Tool eklemeleri planlanıyor):

1. **Zarar Saptırma Analizi (Outlier Detection):**
   - Gösterimi ve tıklanması çok yüksek olup, hiç satmayan (`satis_adet = 0`, `reklam_cirosu = 0`) ürünlerin tespiti.
   - Bütçeyi aşırı tüketen ama ROAS getirmeyen (`harcama_getirisi < 1`) "kanayan yara" ürünleri.

2. **Rekabet & TBM (CPC) Optimizasyon Analizi:**
   - `tbm_teklif` (verilen teklif) ile `gerceklesen_tbm` (asıl kesilen) arasındaki farkın analizi (boşa yüksek teklif veriliyor mu?).
   - `onerilen_tbm` ile mevcut teklifin kıyaslanması; pazarın gerisinde kalıp gösterim kaybeden yıldız ürünlerin tespiti.

3. **Trend ve Dönüşüm (CR) Analizi:**
   - Tıklama Oranı (CTR = `tiklanma_sayisi` / `gosterim_sayisi`) analizleri. Yüksek gösterim ama sıfır tıklama = Kötü ana görsel.
   - Dönüşüm Oranı (CVR = `satis_adet` / `tiklanma_sayisi`). Yüksek tıklama ama sıfır satış = Yanıltıcı reklam veya pahalı ürün.
   - Gün be gün (`sorgu_tarihi`) metrik değişimlerinin izlenip aniden satışı azalan ürünlerin tespiti. 

4. **Kârlılık ve Ölçekleme (Scale-Up) Analizi:**
   - ROAS'ı (`harcama_getirisi`) çok yüksek (örneğin >15) olan ve `harcanan_butce`si `gunluk_butce` sınırına yaklaşan ürünler (Bu ürünlerin bütçesi/teklifi artırılmalıdır). 

### Niyet (Intent) ve Düğüm (Node) Gruplandırması
`test_sorulari.md` dokümanındaki tüm sorular ve yeni özellikler, LangGraph mimarisindeki **Node (Düğüm)** rotalarına göre 3 ana iş akışına bölünmüştür. 
*(Not: Bot sadece okuma, analiz ve tavsiye yapar. Veritabanına doğrudan yazma eylemi (Write/Action) yoktur).*

#### 1. Fast-Track İş Akışı (Sadece Veri Çekme & Özetleme)
**İlgili Node Rotası:** `Intent Router -> Tool Selector -> Explainer Node`
Bu akış, yorumlama gerektirmeyen, veritabanından doğrudan cevap dönecek sorular içindir. `Analyst` düğümüne **gitmez**.
- **İlgili Sorular (`test_sorulari.md`):** 
  - "Hangi puf modellerimiz var?" (Soru 6)
  - "Tüm ürünleri listeler misin?" (Soru 1)
  - "ZAYNABED160X200 kodlu ürünün güncel kar marjını getir" (Soru 2)
  - "Tıklanma sayısı 100'ün altında kalan kampanyaları getir" (Soru 45)
  - "Kar marjı %50'nin üzerinde olan ürünleri listele" (Soru 52)
- **Gerekli Niyetler (Intents):** `data_fetch`, `list_products`, `filter_db`
- **Gerekli Araçlar (Tools):** Temel SQL aracı (Örn: `read_query`), `get_product_costs`.

#### 2. Deep-Track İş Akışı (Tekil Kaynak Analizi & Matematik)
**İlgili Node Rotası:** `Intent Router -> Tool Selector -> Analyst Node -> Explainer Node`
Veri çekildikten sonra hafızada (memory) matematiksel işlem, kıyaslama, anormallik tespiti (outlier) veya kural birleştirme gerektiren durumlar içindir.
- **İlgili Sorular (`test_sorulari.md`):**
  - "ZAYNABED ile MINIPUF'u kıyasla, hangisi daha karlı?" (Soru 40 - Toplu Kıyaslama)
  - "MINIPUF'un reklam maliyeti, ürün maliyetinin yüzde kaçına denk geliyor?" (Soru 44 - Matematik)
  - "XPUFFY için TBM farkı yüzdesel olarak kaç?" (Soru 46)
  - "ZAYNABED net satış cirosu 3 satış adetini tutturuyor mu, sağlamasını yap!" (Soru 57)
  - "XPUFFY için strateji kurallarını güncel reklam verisiyle harmanla." (Soru 58 - Akıllı Sentez)
- **Gerekli Niyetler (Intents):** `analyze`, `compare_metrics`, `verify_math`
- **Gerekli Araçlar (Tools):** `calculate_ratio`, `compare_multiple_products` (Python-based pandas/math toolları).

#### 3. Orchestration & Forecast İş Akışı (Çoklu Kaynak & Tahmin)
**İlgili Node Rotası:** `Intent Router -> Tool Selector -> Cross-Agent/Orchestrator Node -> Analyst Node -> Explainer Node`
Bağımsız iki farklı veritabanından/sunucudan veri birleştirmeyi veya geleceğe yönelik simülasyon/hesaplama yapmayı gerektiren en üst düzey akıştır.
- **İlgili Sorular (`test_sorulari.md`):**
  - "Cebimde ekstra 500 TL var, sence hangi ürünün bütçesine yatırmalıyım?" (Soru 54 - Forecast/Öneri)
  - "Şu anki reklam bütçe durumunu PostgreSQL DB'sindeki tablo ile eşleştirip farkları bul." (Soru 59 - Çoklu Kaynak)
  - "Geçen haftaki ciro ile bu haftaki ciro arasındaki büyüme nedir?" (Soru 48 - Zaman serisi/Trend)
- **Gerekli Niyetler (Intents):** `forecast_strategy`, `cross_db_merge`, `trend_analysis`
- **Gerekli Araçlar (Tools):** `forecast_budget_allocation`, `cross_db_join_tool` (Memry'de iki source'u birleştiren özel tool), `time_series_filter`.

### Geliştirilmesi Gereken Node Rotaları ve MCP Araçları (To-Do List)

Yukarıdaki 3 ana iş akışını (Fast, Deep, Orchestration) otonom olarak yönetebilmek için yazılması gereken **Kod / Mantık** gereksinimleri şunlardır:

#### 1. LangGraph Node (Düğüm) ve Yönlendirme (Routing) Geliştirmeleri (`graph.py`)
- **Dinamik Rota (Dynamic Router):** Mevcut haldeki "eğer niyet analyze ise Analyst'e git" (`route_after_tools` içindeki) hardcoded mantığı silinmelidir.
  - *Yapılacaklar:* `intents.yaml` dosyasındaki her niyet için bir `route_type` (ör. `fast`, `deep`, `orchestration`) parametresi eklenmeli. Yönlendirici fonksiyon bu parametreyi okuyarak grafikteki bir sonraki adımı belirlemelidir.
- **Orchestrator Node (Yeni Düğüm):** `Deep-Track` (Tek veri kaynağı) ile `Orchestration` (Çoklu veri kaynağı) arasındaki ayrımı yönetmek üzere, gerekirse farklı MCP'lerden dönen veri listelerini bellekte birleştirecek yeni bir ara düğüm (`Orchestrator Node`) yazılmalıdır.

#### 2. Yazılması Gereken Özel Python MCP Araçları (`mcp_server.py`)
Modelin tek başına matematik veya karmaşık algoritma çalıştıramayacağı senaryolar için şu fonksiyonlar (Tool) kodlanmalıdır:

**Deep-Track (Analiz & Matematik) İçin Gereken Araçlar:**
- `@tool("compare_multiple_products")`: `urun_kodlari` listesi alan, bu ürünleri veritabanından çekip pandas/dict mantığı ile ROAS, TBM oranlarını karşılaştıran ve sonucu string döndüren metrik kıyaslama aracı.
- `@tool("calculate_ratio")`: "Maliyetin yüzde kaçı?" veya "Dönüşüm oranı nedir?" gibi net matematik ve bölme işlemi hatalarını sıfıra indiren basit hesaplama aracı.

**Orchestration (Tahmin & Senaryo) İçin Gereken Araçlar:**
- `@tool("forecast_budget_allocation")`: Parametre olarak boşta kalan bütçeyi (ör: 500 TL) alan, DB'den en yüksek ROAS getiren mevcut kampanyaları bulup istatistiksel olarak kârlı bir paylaştırma formülü hesaplayıp tavsiye metni dönen simülasyon aracı.
- `@tool("cross_db_join_tool")`: İleride bağlanacak farklı PostgreSQL veya harici ERP veritabanlarındaki "Maliyet/Satış" tabloları ile mevcut "Reklam" tablolarını bir ID üzerinde birleştirip (memory'de JOIN yapıp) LLM'e tek bir özet tablo çıkaran veri birleştirici araç.
- `@tool("time_series_filter")`: "Geçen hafta" ile "Bu hafta" arasındaki verileri hızlıca alıp gruplayan, büyüme (growth) hesapları yapan araç.
**Orchestration (Tahmin & Senaryo) İçin Gereken Araçlar:**
- `@tool("forecast_budget_allocation")`: Parametre olarak boşta kalan bütçeyi (ör: 500 TL) alan, DB'den en yüksek ROAS getiren mevcut kampanyaları bulup istatistiksel olarak kârlı bir paylaştırma formülü hesaplayıp tavsiye metni dönen simülasyon aracı.
- `@tool("cross_db_join_tool")`: İleride bağlanacak farklı PostgreSQL veya harici ERP veritabanlarındaki "Maliyet/Satış" tabloları ile mevcut "Reklam" tablolarını bir ID üzerinde birleştirip (memory'de JOIN yapıp) LLM'e tek bir özet tablo çıkaran veri birleştirici araç.
- `@tool("time_series_filter")`: "Geçen hafta" ile "Bu hafta" arasındaki verileri hızlıca alıp gruplayan, büyüme (growth) hesapları yapan araç.

---

## Geliştirme Planı ve Görev Listesi (Roadmap)

Sistemi yukarıdaki mimariye kavuşturmak için adım adım uygulanacak detaylı görev listesi:

### 1. Aşama: Doğru MCP Araçlarını (Tools) Geliştirmek
- `mcp_server.py` içerisine yeni araçlar kodlanacak (ör. `calculate_roas_comparison`, `forecast_budget_allocation`, `calculate_ratio`).
- Araçların girdileri (schema) ve çıktıları (LLM'in kolay okuyacağı string loglar) teste ve hata yönetimine uygun şekilde tasarlanacak. (Örn: `ROAS < 1` uyarısı, division_by_zero önlemi).

### 2. Aşama: `intents.yaml` Dosyasını Yeni Akışlara Göre Düzenlemek
- Her bir niyet grubuna ait mevcut ve yeni eklenecek niyetler (örn: `advanced_data_mining`, `forecast_strategy`) yaml dosyasına tanımlanacak.
- Niyetlere atanacak özel araç listesi (`tools: [...]`) güncellenecek (LLM'e sadece ilgili araçlar verilecek).
- **Kritik Eklenti:** Her bir niyet için `route_type` parametresi eklenecek. `route_type: fast_track` sadece `Explainer` düğümüne, `route_type: deep_track` ise `Analyst` düğümüne yönlendirilmeyi temsil edecek.

### 3. Aşama: Gerekli Yeni Node'ları (Düğümleri) Yazmak
- `graph.py` içine Niyet/Rota grubuna özel (örn: `Orchestrator` veya `Data Aggregator`) ara düğümler kodlanacak, şayet standart `Analyst` düğümü belirli verileri işlemek veya farklı bir role bürünmek için yetersiz kalacaksa ayrıştırılmış özel Node yapıları tanımlanacak. 

### 4. Aşama: Graph Yönlendirmesini (Routing) Dinamik Hale Getirmek
- `graph.py` içindeki `route_after_tools` yapısındaki hardcoded ("analyze", "optimize") kontrolü silinecek.
- Sisteme, o anki aktif Intent'in `route_type` bilgisini yaml'dan çekip dinamik `workflow.add_conditional_edges` bağlarını kurarak doğru rotalara yönlenebileceği altyapı sağlanacak.
- Tüm bu değişiklikler uçtan uca çalıştırılarak test edilecek.


