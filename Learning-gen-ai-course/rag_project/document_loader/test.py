from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader, TextLoader

# ==============================================================
# THE PROBLEM CODE (Current Behavior)
# ==============================================================
# loader = TextLoader("./linix_and_shell.txt") 
# 
# WHY THIS FAILS: 
# The "./" refers to your "Current Working Directory" (CWD). 
# Since you ran the command from the /rag_project/ folder, 
# Python looks for the file there, NOT inside /document_loader/.
# ==============================================================


# ==============================================================
# THE CORRECTED CODE (Robust Pathing)
# ==============================================================

# 1. __file__ is the path to this script (test.py)
# 2. .parent gets the directory this script lives in (/document_loader/)
current_dir = Path(__file__).parent
# 3. Combine the directory with the filename to get an absolute path
txt_file_path = current_dir / "linix_and_shell.txt"
pdf_file_path = current_dir / "computer_revolution.pdf"

def load_text_file(file_path):
    TextLoader(str(file_path))
    # Initialize the loader using the dynamic path
    loader = TextLoader(str(file_path))
    # Load and print
    docs = loader.load()
    print(f"--- Loaded from: {file_path} ---")
    print(f"Metadata: {docs[0].metadata}")
    print(f"Content: {docs[0].page_content}")

def load_pdf_file(file_path):
    # Initialize the loader using the dynamic path
    loader = PyPDFLoader(str(file_path))
    # Load and print
    docs = loader.load()
    print(f"--- Loaded from: {file_path} ---")
    # print(f"Metadata: {docs[0].metadata}")
    print(f"Number of pages: {len(docs)}")
    print(f"Content: {len(docs[0].page_content)}")

# load_text_file(txt_file_path)
load_pdf_file(pdf_file_path)


