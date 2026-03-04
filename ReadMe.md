python -m pipenv install mcp google-genai pydantic python-dotenv
python -m pipenv run python3 client.py 

Client.py
 Gemini ile sohbet eder 
 toolları mcpden ister ve onları geminie iletir 

 """

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

