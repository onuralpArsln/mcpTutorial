# server.py
from mcp.server.fastmcp import FastMCP
import os
import difflib

# Sunucumuzu isimlendiriyoruz
mcp = FastMCP("Local-File-Manager")

@mcp.tool()
def dosya_yaz(dosya_adi: str, icerik: str) -> str:
    """Belirtilen isimde yeni bir dosya açar ve içine metin yazar. (örn: notlar.txt)"""
    try:
        with open(dosya_adi, "w", encoding="utf-8") as f:
            f.write(icerik)
        return f"{dosya_adi} isimli dosya başarıyla oluşturuldu ve içerik yazıldı."
    except Exception as e:
        return f"Hata oluştu: {str(e)}"

@mcp.tool()
def dosya_oku(dosya_adi: str) -> str:
    """Belirtilen dosyanın içeriğini okur. Tam isim bilinmese de yakın eşleşme bulunur."""
    # Önce tam eşleşmeyi dene
    if os.path.exists(dosya_adi):
        try:
            with open(dosya_adi, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Okuma hatası: {str(e)}"

    # Tam eşleşme yoksa klasördeki .txt dosyaları içinde fuzzy ara
    mevcut = [f for f in os.listdir('.') if f.endswith('.txt')]
    eslesme = difflib.get_close_matches(dosya_adi, mevcut, n=1, cutoff=0.3)
    if eslesme:
        bulunan = eslesme[0]
        try:
            with open(bulunan, "r", encoding="utf-8") as f:
                icerik = f.read()
            return f"['{dosya_adi}' yerine '{bulunan}' bulundu]\n\n{icerik}"
        except Exception as e:
            return f"Okuma hatası: {str(e)}"

    return f"Hata: '{dosya_adi}' adında veya buna yakın bir dosya bulunamadı. Mevcut dosyalar: {mevcut}"

@mcp.tool()
def notlari_listele() -> str:
    """Mevcut klasördeki tüm .txt not dosyalarını listeler."""
    try:
        dosyalar = [f for f in os.listdir('.') if f.endswith('.txt')]
        if not dosyalar:
            return "Hiç not dosyası bulunamadı."
        liste = "\n".join(f"{i+1}. {d}" for i, d in enumerate(dosyalar))
        return f"Mevcut not dosyaları:\n{liste}"
    except Exception as e:
        return f"Listeleme hatası: {str(e)}"

if __name__ == "__main__":
    # Sunucuyu standart input/output üzerinden dinlemeye başlat
    mcp.run(transport='stdio')