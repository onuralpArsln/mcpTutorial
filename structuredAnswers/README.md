# Tutorial: Local Ollama Structured JSON Outputs

This tutorial shows how to force a local LLM (via Ollama) to return structured data instead of free-form text. This is critical for building agentic systems that need to parse model responses programmatically.

## Prerequisites

1.  **Ollama**: Must be installed and running.
2.  **Model**: This tutorial default to `llama3.2`. You can pull it with:
    ```bash
    ollama pull llama3.2
    ```
3.  **Packages**: Ensure you have the necessary dependencies:
    ```bash
    pipenv install langchain-ollama pydantic
    ```

## How it Works

The tutorial uses **LangChain's `.with_structured_output()`** method combined with a **Pydantic model**.

### 1. The Schema (Pydantic)
We define a Python class that inherits from `BaseModel`. This defines the "shape" of our JSON.
```python
class IntentOutput(BaseModel):
    user_intent: str = Field(...)
```

### 2. The Chain
We combine a strict system prompt with the structured model:
```python
structured_llm = llm.with_structured_output(IntentOutput)
chain = prompt | structured_llm
```

## Running the Tutorial

Run the script using `pipenv`:
```bash
python3 -m pipenv run python structuredAnswers/ollama_structured_tutorial.py
```

## Why JSON?
In this codebase, we use this technique for:
- **Intent Routing**: Deciding which tool to call.
- **Data Extraction**: Getting specific product codes from user messages.
- **Verification**: Checking if business rules are violated.
