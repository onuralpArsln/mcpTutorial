---
trigger: always_on
---

This rule expalins the data base of products where the agent built is managest the ads for it.


id: database id for each entry 
sorgu_tarihi: day of the data collected
sorgu_saati: time of the data collected
urun_kodu: product code defined by the producer
harcanan_butce: the ad budget spent for that day, since the beggining of given day
gosterim_sayisi: amount of impression of given product ad on users scrren
tiklanma_sayisi: amount of clicks that products ad get 
reklam_cirosu: sales made to users whom click that ad (including people who purchase other prodcuts)
harcama_getirisi: ratio of money made to ad spent. 0 meeans no sales made through that ad
gerceklesen_tbm: cost per click on given ads
tbm_teklif: the cost per click set by human ad manager
onerilen_tbm: the cost per click setting suggested by the market place
satis_adet: amount of sales made for given product through given ad
net_satis:  satis_adet times the product price, revenue made by sale of given product
created_at: time and date of ads starting 
gunluk_butce: the maximum daily limit for given ads budget


An example from db 

id: 1
sorgu_tarihi: "2026-02-27"
sorgu_saati: "15:40:02.575786"
urun_kodu: "XPUFFY4040KAREPUF"
harcanan_butce: 372.54
gosterim_sayisi: 10781
tiklanma_sayisi: 193
reklam_cirosu: 0.00
harcama_getirisi: 0.00
gerceklesen_tbm: 1.93
tbm_teklif: 1.79
onerilen_tbm: "Önerilen TBM: 3,28 ₺ (En iyi 5,26 ₺)"
satis_adet: 0
net_satis: 0.00
created_at: "2026-02-27 12:40:24.287168"
gunluk_butce: 500