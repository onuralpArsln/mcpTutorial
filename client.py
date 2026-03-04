# client.py
import asyncio
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
load_dotenv()  # .env dosyasını ortam değişkenlerine yükler


# Gemini İstemcisi (API anahtarını ortam değişkenlerinden alır)
gemini_client = genai.Client()

async def main():
    # 1. MCP Server'ı çalıştıracak parametreler (server.py ile aynı klasörde olmalı)
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"]
    )

    print("MCP Server'a bağlanılıyor...")
    
    # 2. MCP Server ile iletişimi başlatıyoruz
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Bağlantı başarılı! Gemini ile sohbet edebilirsin. (Çıkmak için 'q' yaz)")

            # Gemini'a vereceğimiz tool tanımları
            # (Gerçek dünyada bunları `await session.list_tools()` ile MCP'den dinamik çekeriz)
            tool_definitions = [
                types.FunctionDeclaration(
                    name="dosya_yaz",
                    description="Belirtilen isimde yeni bir dosya açar ve içine metin yazar.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "dosya_adi": types.Schema(type=types.Type.STRING),
                            "icerik": types.Schema(type=types.Type.STRING),
                        },
                        required=["dosya_adi", "icerik"]
                    )
                ),
                types.FunctionDeclaration(
                    name="dosya_oku",
                    description="Belirtilen dosyanın içeriğini okur.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "dosya_adi": types.Schema(type=types.Type.STRING),
                        },
                        required=["dosya_adi"]
                    )
                ),
                types.FunctionDeclaration(
                    name="notlari_listele",
                    description="Mevcut klasördeki tüm .txt not dosyalarını listeler. Parametre gerekmez.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={}
                    )
                )
            ]
            
            tool_config = types.Tool(function_declarations=tool_definitions)

            # 3. Sohbet Döngüsü
            while True:
                user_input = input("\nSen: ")
                if user_input.lower() in ['q', 'çıkış']:
                    break

                # Gemini'a mesajı ve toolları gönderiyoruz
                response = gemini_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=user_input,
                    config=types.GenerateContentConfig(
                        tools=[tool_config],
                    )
                )

                # Gemini bir tool çağırmak istedi mi kontrol edelim
                if response.function_calls:
                    for function_call in response.function_calls:
                        tool_name = function_call.name
                        args = function_call.args

                        print(f"\n[SİSTEM] Gemini '{tool_name}' aracını kullanıyor... Argümanlar: {args}")

                        # MCP Server üzerinden ilgili aracı çalıştır
                        mcp_result = await session.call_tool(tool_name, arguments=args)
                        
                        # Sonucu ekrana ve (opsiyonel olarak) tekrar modele bildirebilirsin
                        print(f"[MCP SONUÇ]: {mcp_result.content[0].text}")
                else:
                    # Normal metin cevabı
                    print(f"\nGemini: {response.text}")

if __name__ == "__main__":
    asyncio.run(main())