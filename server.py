# server.py
from mcp.server.fastmcp import FastMCP
import os

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
    """Belirtilen dosyanın içeriğini okur ve metin olarak döner."""
    try:
        with open(dosya_adi, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Hata: {dosya_adi} adında bir dosya bulunamadı."
    except Exception as e:
        return f"Okuma hatası: {str(e)}"

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