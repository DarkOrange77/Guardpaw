from langchain_community.vectorstores import FAISS
from .document_loader import load_documents
import os

# Embedding backends: 'huggingface' or 'google'
# Configure via env: EMBEDDING_BACKEND=huggingface
EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "huggingface")

_HF_AVAILABLE = False
try:
    from langchain_huggingface import HuggingFaceEmbeddings
    _HF_AVAILABLE = True
except Exception:
    _HF_AVAILABLE = False

_GOOGLE_AVAILABLE = False
try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    _GOOGLE_AVAILABLE = True
except Exception:
    _GOOGLE_AVAILABLE = False


def build_or_load_index():
    # Embedding client configuration (select backend)
    if EMBEDDING_BACKEND == "huggingface":
        if not _HF_AVAILABLE:
            raise RuntimeError("HuggingFace embeddings requested but langchain_huggingface is not installed.")
        hf_model = os.getenv("HF_MODEL", "BAAI/bge-m3")
        hf_device = os.getenv("HF_DEVICE", "cpu")
        embeddings = HuggingFaceEmbeddings(
            model_name=hf_model,
            model_kwargs={"device": hf_device},
            encode_kwargs={"normalize_embeddings": True},
        )
    else:
        if not _GOOGLE_AVAILABLE:
            raise RuntimeError("Google embeddings requested but langchain_google_genai is not installed.")
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            task_type="retrieval_document",
            request_options={"timeout": 60},
        )

    # Configurable batch size (no quota waits for local models)
    BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "5"))

    # Paths (project-root relative)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    index_path = os.path.join(base_dir, "rag/vector_store/index.faiss")
    data_path = os.path.join(base_dir, "data")

    if os.path.exists(index_path):
        print("Loading existing index...")
        return FAISS.load_local(os.path.dirname(index_path), embeddings, allow_dangerous_deserialization=True)

    print("Building new index from documents...")
    docs = load_documents(data_path)
    print(f"Loaded {len(docs)} documents. Processing in batches of {BATCH_SIZE}...")

    vectorstore = None

    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"Processing batch {batch_num} ({len(batch)} documents)...")

        if vectorstore is None:
            vectorstore = FAISS.from_documents(batch, embeddings)
        else:
            vectorstore.add_documents(batch)
        print(f"Batch {batch_num} processed.")

    if vectorstore is None:
        raise RuntimeError("No documents were processed; vectorstore not created.")

    print("Saving index locally...")
    vectorstore.save_local(os.path.dirname(index_path))
    print("Index saved successfully!")
    return vectorstore
