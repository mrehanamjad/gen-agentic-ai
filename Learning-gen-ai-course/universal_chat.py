import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

load_dotenv()

# Pricing and model metadata for April 2026
MODELS = {
    "1": {"id": "llama-3.1-8b-instant", "provider": "groq", "label": "Llama 3.1 8B", "price": "CHEAPEST", "speed": "800+ t/s"},
    "2": {"id": "openai/gpt-oss-20b", "provider": "groq", "label": "GPT-OSS 20B", "price": "CHEAP", "speed": "900+ t/s"},
    "3": {"id": "gemini-2.0-flash", "provider": "google_genai", "label": "Gemini 2.0 Flash", "price": "BUDGET", "speed": "Fast"},
    "4": {"id": "llama-3.3-70b-versatile", "provider": "groq", "label": "Llama 3.3 70B", "price": "BALANCED", "speed": "300+ t/s"},
    "5": {"id": "openai/gpt-oss-120b", "provider": "groq", "label": "GPT-OSS 120B", "price": "PREMIUM", "speed": "500+ t/s"},
}

def get_model_choice():
    print("\n" + "="*40)
    print("      SELECT A MODEL")
    print("="*40)
    for key, m in MODELS.items():
        print(f"[{key}] {m['label']:<18} | {m['price']:<10} | {m['speed']}")
    print("="*40)
    
    choice = input("Enter number (default 1): ").strip() or "1"
    return MODELS.get(choice, MODELS["1"])

def main():
    selected = get_model_choice()
    
    # Using init_chat_model for seamless switching
    llm = init_chat_model(
        model=selected["id"],
        model_provider=selected["provider"],
        temperature=0.7
    )

    chat_history = [SystemMessage(content="You are a helpful CLI assistant.")]

    print(f"\n[System] Using {selected['label']}. Type '/model' to switch or 'exit' to quit.")

    while True:
        user_input = input("\nYou: ").strip()

        if not user_input: continue
        if user_input.lower() in ["exit", "quit"]: break
        
        # Command to switch models mid-conversation
        if user_input.lower() == "/model":
            selected = get_model_choice()
            llm = init_chat_model(
                model=selected["id"],
                model_provider=selected["provider"],
                temperature=0.7
            )
            print(f"\n[System] Switched to {selected['label']}")
            continue

        chat_history.append(HumanMessage(content=user_input))

        print(f"\n{selected['label']}: ", end="", flush=True)
        full_response = ""
        
        try:
            for chunk in llm.stream(chat_history):
                print(chunk.content, end="", flush=True)
                full_response += chunk.content
            print()
            chat_history.append(AIMessage(content=full_response))
        except Exception as e:
            print(f"\n\nError: {e}")

if __name__ == "__main__":
    main()