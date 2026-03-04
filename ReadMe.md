# Başlangıç
pipenv sanal ortama yükle 
"""bash
python -m pipenv install mcp google-genai pydantic python-dotenv
"""

sanal ortamdan başlat 
"""bash
python -m pipenv run python3 client.py 
"""

# Dosyalar
Client.py
 Gemini ile sohbet eder 
 toolları mcpden ister ve onları geminie iletir 

 """python

                 response = gemini_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=user_input,
                    config=types.GenerateContentConfig(
                        tools=[tool_config],
                    )
                )
 """

 server.py

 mcp burada 
toollar ekelenecek

