# Başlangıç

Pipenv sanal ortama yükle:

```bash
python -m pipenv install mcp google-genai pydantic python-dotenv
```

Sanal ortamdan başlat:

```bash
python -m pipenv run python3 client.py
```

# Dosyalar

## client.py
Gemini ile sohbet eder. Toolları MCP'den dinamik olarak çeker ve Gemini'ye iletir:

```python
response = gemini_client.models.generate_content(
    model='gemini-2.5-flash',
    contents=user_input,
    config=types.GenerateContentConfig(
        tools=[tool_config],
    )
)
```

## server.py
MCP sunucusu burada çalışır. Yeni toollar buraya eklenir.
