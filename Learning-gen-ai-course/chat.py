from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from dotenv import load_dotenv

load_dotenv()

def main():
    # Initialize the Groq model
    # Llama 3.3 70B is currently a top choice for speed/intelligence balance
    llm = ChatGroq(
        model="openai/gpt-oss-20b",
        temperature=0.5,
        # max_retries=2,
    )

    chat_history = [
        SystemMessage(content="You are a fast, concise AI running on Groq LPU technology.")
    ]

    print("--- Groq CLI Chatbot (Type 'exit' to quit) ---")

    while True:
        user_input = input("\nYou: ")
        
        if user_input.lower() in ["exit", "quit", "q"]:
            print("Goodbye!")
            break

        chat_history.append(HumanMessage(content=user_input))

        print("Groq: ", end="", flush=True)

        try:
            full_response = ""
            # Using .stream() for that real-time terminal feel
            for chunk in llm.stream(chat_history):
                content = chunk.content
                print(content, end="", flush=True)
                full_response += content
            
            print() # New line after stream ends
            chat_history.append(AIMessage(content=full_response))
            
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    main()

