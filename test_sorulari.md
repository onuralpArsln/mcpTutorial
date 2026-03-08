# Ajan Test Soruları (Test ve Güçlendirme İçin)

Sistemin mevcut LangGraph yapısına, `intents.yaml` dosyasındaki niyetlere ve `mcp_server.py` içerisinde tanımlı araçlara (`list_products`, `get_performance_metrics`, `get_product_costs`, `run_pattern_recognition`) göre hazırlanan test soruları aşağıdadır. 

Amacımız bu sorularla sistemin yeteneklerini sınamak ve "Şu an Yapamadıkları" bölümündeki işlemleri yapabilmesi için gelecekteki tool/node geliştirmelerine (örneğin çapraz karşılaştırma, hesaplama, veritabanı filtreleme) zemin hazırlamaktır.

---

## ✅ Şu An Başarıyla Cevap Verebileceği Sorular (20 Adet)

Bu sorular, sistemdeki mevcut araçların (Tool'ların) ve parametrelerin (örn: `urun_kodu` argümanının) doğrudan karşılayabileceği, niyetlerin (intent) kolayca eşleşebileceği isteklerdir.

1. Sistemde kayıtlı olan mevcut ürünleri listeler misin?
2. ZAYNABED160X200 kodlu ürünün güncel kar marjı ve maliyet bilgisini getir.
3. MINIPUFROUND ürününün bugün ne kadar reklam bütçesi harcadığını söyler misin?
4. XPUFFY4040KAREPUF kodlu pufun dünkü (veya mevcut mock verisindeki) tıklanma sayısını ve gösterimini analiz et.
5. ZAYNABED160X200 ürününün satışı reklamlardan kaç adet olmuş? (ROAS'ı nedir?)
6. Hangi puf modellerimiz var? Lütfen isimleriyle listele.
7. XPUFFY4040KAREPUF için tıklama başına maliyet (TBM) şu an gerçekleşen rakam olarak ne kadar?
8. ZAYNABED160X200 yatağının maliyeti ile satış fiyatı arasındaki fark nedir?
9. "analyze" veya "optimize" niyetine dair strateji kurallarını hafızandan (knowledge) okur musun?
10. MINIPUFROUND için önerilen TBM (Tıklama Başına Maliyet) aralığı nedir?
11. XPUFFY4040KAREPUF reklamının performansı nasıl? (Pattern recognition tool'unu tetikleyerek risk veya başarı ölçümü yapabilmeli).
12. XPUFFY4040KAREPUF'un harcama getirisi (ROAS) durumu şu an 0 mı? Kontrol et.
13. ZAYNABED160X200 için bütçeyi ne kadar artırmamız lazım? (Sistem süper ROAS'ı görüp "Scale Up" önerisi getirebilmeli).
14. Sisteminizin genel bilgisi nedir? (İşletim sistemi, Python sürümü vb. `system_info` aracıyla).
15. Depodaki/Portföydeki tüm yatak kategorisi ürünlerini ve puf kategorisi ürünlerini ekrana dök.
16. Kök dizindeki ".txt" uzantılı dosyaların (notların) listesini `notlari_listele` aracıyla getirir misin?
17. ZAYNABED160X200 için gerçekleşen net reklam cirosu rakamımız nedir?
18. XPUFFY6060KAREPUF (Mevcut ama reklamsız ürün) reklam performansı nedir? (Veri bulunamadı hatasını zarifçe işlemeli).
19. Maliyeti 1000 TL üzerinde olan ürün hangisi? (Bunu ancak `list_products` veya `get_product_costs` ile tek tek bakarak veya LLM bilgisinden yapabilir).
20. MINIPUFROUND için harcama getirisi (ROAS) durumu stabil mi dalgalı mı? (Pattern analyzer ile).

---

## ❌ Şu An Cevap Vermekte Zorlanacağı veya Hata Yapacağı Sorular (20 Adet)

Sistemin mevcut yapısında bu sorular ya çoklu bağlam/araç kullanımını birleştirmeyi gerektirir, ya veritabanında "Tümünü filtrele/Tümünün ortalamasını al" gibi mantıksal işlevler yoktur, ya da LLM'in tek adımda halledemeyeceği SQL/Matematik operasyonlarına ihtiyaç duyar.

1. **(Toplu Kıyaslama)**: ZAYNABED160X200 ile MINIPUFROUND ürünlerinin reklam ROAS performanslarını kıyasla, hangisi daha karlı? (Tool'lar tek tek `urun_kodu` beklediği için ikisini birden çekip yorumlamakta zorlanabilir).
2. **(Toplu Operasyon)**: Sistemdeki **tüm ürünlerin** bugünkü toplam harcaması ne kadardır? (Bunu yapan bir `get_total_spend` aracı yok).
3. **(Arama/Filtreleme)**: Reklam getirisi (ROAS) en çok olan ürün hangisi? (LLM tüm ürünleri tek tek çekip aklında tutup sıralama (`sort`) yapamaz. Bunu DB'de yapan bir Tool'a ihtiyacı var).
4. **(Filtreleme)**: Reklam giderleri, toplam harcama ortalamasından yüksek olan ürünleri listele.
5. **(Matematiksel)**: MINIPUFROUND ürününün reklam maliyeti, ürün maliyetinin yüzde kaçına denk geliyor? (Matematiksel hata riski yüksek).
6. **(Arama/Filtreleme)**: Tıklanma sayısı 100'ün altında kalan tüm ürün kampanyalarını bana getir.
7. **(Metrik Kıyaslama)**: XPUFFY4040KAREPUF'un teklif edilen TBM'si ile gerçekleşen TBM'si arasındaki fark yüzdesel olarak kaç?
8. **(Oluşturma/Yazma)**: Bugünün performansını özetleyen bir CSV raporu oluştur ve kök dizine kaydet. (`dosya_yaz` aracı var ama veriyi CSV formatında derlemek promt'a bağlı olarak bozulabilir veya intent yanlış seçilebilir).
9. **(Derin Kıyaslama)**: Geçen haftaki reklam cirosu ile bu haftaki reklam cirosu arasındaki büyüme metrikleri ne alemde? (Mock db'de tarih filtresi yapabilen bir araç yok).
10. **(Toplu Operasyon)**: ROAS değeri 0 olan bütün ürün reklamlarını toplu olarak kapat/durdur. (Bir "Action/Write" veya "Duraklat" aracı yok).
11. **(Korelasyon Analizi)**: Yatak satışları ile Puf satışları arasında bir bağ var mı? Reklam etkileşimleri benzer mi?
12. **(Zaman/Saat)**: Sadece sabah saatlerinde (09:00 - 12:00 arası) gösterim alan ürünlerin performansı nedir? (`sorgu_saati` filtresi yeteneği tool'da tanımlı değil).
13. **(Arama/Filtreleme)**: Kar marjı %50'nin üzerinde olan ürünleri harcama tutarına göre azalan sırada listele.
14. **(Arama/Filtreleme)**: Hiç tıklanma almayan ama gösterim sayısı 5000'i geçen reklamlar var mı?
15. **(Senaryo/Öneri)**: Cebimde ekstra 500 TL var, sence hangi ürünün bütçesine yatırmalıyım ki en yüksek e-ticaret dönüşümünü (CPA) alayım? (Bunun için gelişmiş bir tahmin (forecast) aracı yok).
16. **(Toplu Operasyon)**: Karlılığı negatif olan tüm reklamların günlük limitini (gunluk_butce) %20 oranında düşür. ("Update/Set" aracı yok).
17. **(İsim Analizi)**: İçinde "PUF" kelimesi geçen ürünlerin reklam harcama oranları (ROAS) toplamı nedir? 
18. **(Matematiksel Değerlendirme)**: ZAYNABED160X200 ürünündeki net satış cirosu 12.600 TL yazıyor. Bu 3 satış adetini (12.600 / 3 = 4200 TL / adet) tutturuyor mu, sağlamasını yap!
19. **(Akıllı Sentez)**: XPUFFY4040KAREPUF için strateji kurallarını (`get_strategy_rules`) okuyup, güncel reklam verisiyle harmanlayıp, "reklam_acma" kurallarına göre bir aksiyon planı çiz. (İşlem sırası 2 farklı intent grubuna girdiği için `tool_selector` hangi aracı çekeceğini veya hangi akışa gideceğini karıştırabilir).
20. **(Dış Sistem Entegrasyonu)**: Şu anki reklam bütçe durumunu PostgreSQL DB'sindeki (yeni bağladığımız MCP'deki) `xpermate_farm` tablosundaki bir maliyet verisi ile eşleştirip farkları bul. (İki farklı veri kaynağını join/merge işlemi yapacak bir orkestrasyon henüz yok).
