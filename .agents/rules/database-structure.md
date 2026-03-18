---
trigger: always_on
---

This rule expalins the data base of products where the agent built is manages the ads for it. There are two tables.
Tables are update multiple times each day. Resulting many entries of values for each day. Yet entires are cumulative meaning you need to get max of agreateion of each day to find daily values. (or min if asking for reaminin budget)

The product_report table

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



The store_report table

"id" : database id for each entry 
"sorgu_tarihi" : day of the data collected
"sorgu_saati" : time of the data collected
"reklam_kodu" :  ad code defined by the producer
"reklam_adi" : the verbal name given to ads by prodcuer
"gunluk_butce" : the maximum daily limit for given ads budget
"kalan_gunluk_butce" : the daily reamainig to limit for given ads budget
"gosterim_sayisi" :   amount of impression of given product ad on users scrren
"tiklanma_sayisi" : amount of clicks that store ad get 
"satis_adet" :  amount of sales made fby store through given ad
"harcama_getirisi" : ratio of money made to ad spent. 0 meeans no sales made through that ad
"gerceklesen_gbm" : calculated by "harcanan_butce" divided by "gosterim_sayisi" and result is multipleid by 1000
"harcanan_butce" : amount of money spent for the ad
"reklam_cirosu" : sales made to users whom click that ad 



An example for mtable store_report

id: 1
sorgu_tarihi: 2026-02-27
sorgu_saati: 15:40:02.531121
reklam_kodu: 865a940e-5e77-4e68-ba8c-a65e03010e1a
reklam_adi: Sandalye Minderi Mağaza-25.02.2026 13:15
gunluk_butce: 200
kalan_gunluk_butce: 2.36
gosterim_sayisi: 730
tiklanma_sayisi: 15
satis_adet: 1
harcama_getirisi: 4.19
gerceklesen_gbm: 270.74
harcanan_butce: 197.64
reklam_cirosu: 829

