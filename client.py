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

            # MCP Server'dan araçları dinamik olarak çek ve Gemini formatına dönüştür
            mcp_tools = await session.list_tools()
            TYPE_MAP = {
                "string":  types.Type.STRING,
                "integer": types.Type.INTEGER,
                "number":  types.Type.NUMBER,
                "boolean": types.Type.BOOLEAN,
                "array":   types.Type.ARRAY,
                "object":  types.Type.OBJECT,
            }
            tool_definitions = []
            for tool in mcp_tools.tools:
                schema = tool.inputSchema or {}
                raw_props = schema.get("properties", {})
                props = {
                    pname: types.Schema(
                        type=TYPE_MAP.get(pdef.get("type", "string"), types.Type.STRING)
                    )
                    for pname, pdef in raw_props.items()
                }
                required = schema.get("required") or None
                tool_definitions.append(
                    types.FunctionDeclaration(
                        name=tool.name,
                        description=tool.description or "",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties=props,
                            required=required
                        )
                    )
                )
            print(f"[SİSTEM] {len(tool_definitions)} araç yüklendi: {[t.name for t in tool_definitions]}")
            
            tool_config = types.Tool(function_declarations=tool_definitions)

            # Sohbet geçmişini hatırlayan bir async chat oturumu başlat
            chat = gemini_client.aio.chats.create(
                model='gemini-2.5-flash',
                config=types.GenerateContentConfig(
                    tools=[tool_config],
                )
            )

            # 3. Sohbet Döngüsü
            while True:
                user_input = input("\nSen: ")
                if user_input.lower() in ['q', 'çıkış']:
                    break

                # Mesajı chat oturumuna gönder (geçmiş otomatik korunur)
                response = await chat.send_message(user_input)

                # Tool çağrısı varsa işle ve sonucu Gemini'ye geri bildir
                while response.function_calls:
                    tool_parts = []
                    for function_call in response.function_calls:
                        tool_name = function_call.name
                        args = dict(function_call.args)
                        print(f"\n[SİSTEM] Gemini '{tool_name}' aracını kullanıyor... Argümanlar: {args}")

                        mcp_result = await session.call_tool(tool_name, arguments=args)
                        sonuc = mcp_result.content[0].text
                        print(f"[MCP SONUÇ]: {sonuc}")

                        tool_parts.append(
                            types.Part.from_function_response(
                                name=tool_name,
                                response={"result": sonuc}
                            )
                        )

                    # Tool sonuçlarını Gemini'ye ilet → nihai yanıtı al
                    response = await chat.send_message(tool_parts)

                # Metin yanıtını göster
                if response.text:
                    print(f"\nGemini: {response.text}")

if __name__ == "__main__":
    asyncio.run(main())
