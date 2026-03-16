import json
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

# 1. Define the list of allowed intents
INTENT_LIST = ["data_fetch", "advanced_data_mining", "forecast_strategy"]

# 2. Define the desired structure using Pydantic
# This helps LangChain (and some models) understand the exact JSON schema required
class IntentOutput(BaseModel):
    user_intent: str = Field(description="The detected intent of the user. Must be one of the allowed categories.")

def run_structured_tutorial(user_query: str, model_name: str = "llama3.2:3b"):
    """
    Demonstrates how to get structured JSON output from a local Ollama model.
    """
    
    print(f"\n--- OLLAMA STRUCTURED OUTPUT TUTORIAL ---")
    print(f"Model: {model_name}")
    print(f"User Query: '{user_query}'")
    
    # 3. Initialize the local model
    # Ensure you have run 'ollama pull <model_name>' before running this
    llm = ChatOllama(model=model_name, temperature=0)

    # 4. Create a prompt that strictly enforces the format and choice
    # We include 'format="json"' in the prompt for smaller models that might struggle
    system_prompt = (
        "You are an intent classification assistant.\n"
        "ALLOWED INTENTS: {intents}\n\n"
        "CRITICAL RULES:\n"
        "1. You MUST return ONLY a valid JSON object.\n"
        "2. The JSON object must have exactly one key: 'user_intent'.\n"
        "3. The value must be ONE of the allowed intents listed above.\n"
        "4. Do NOT include any explanation, greeting, or Markdown formatting outside the JSON."
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{query}")
    ])

    # 5. Connect the prompt and the model
    # We use .with_structured_output() which is the modern LangChain way
    # Most newer Ollama models (like Llama 3.1/3.2) handle this well
    structured_llm = llm.with_structured_output(IntentOutput)
    
    chain = prompt | structured_llm

    print("\nProcessing request...")
    try:
        # 6. Invoke the chain
        result = chain.invoke({
            "intents": ", ".join(INTENT_LIST),
            "query": user_query
        })
        
        # 7. Print the results
        # 'result' is already a Pydantic object (IntentOutput)
        print("\n✅ Successfully received structured output:")
        print(f"Type: {type(result)}")
        print(f"Content: {result}")
        print(f"Detected Intent: {result.user_intent}")
        
        # Demonstrate conversion to plain dictionary/JSON
        json_data = result.model_dump()
        print(f"As JSON string: {json.dumps(json_data)}")

    except Exception as e:
        print(f"\n❌ Error during processing: {e}")
        print("Tip: Make sure Ollama is running ('ollama serve') and the model is pulled.")

if __name__ == "__main__":
    # Test cases
    test_queries = [
        "Hangi ürünlerin stoğu azaldı?",              # Expected: data_fetch
        "Puf modelleri ile yatakları karşılaştır",    # Expected: advanced_data_mining
        "Elimdeki 1000 TL'yi nereye harcamalıyım?"    # Expected: forecast_strategy
    ]
    
    for q in test_queries:
        run_structured_tutorial(q)
        print("-" * 40)
