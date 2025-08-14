# rag_utils.py
import os
import glob
import re
import importlib
from dotenv import load_dotenv

# optional import for Gemini (we'll handle if missing)
try:
    import google.generativeai as genai 
except Exception:
    genai = None

# ---------------------------------------
# Chroma init (support old and new APIs)
# ---------------------------------------
load_dotenv()

_chroma_path = ".chromadb"
os.makedirs(_chroma_path, exist_ok=True)

try:
    chromadb = importlib.import_module("chromadb")
except Exception as e:
    chromadb = None
    # caller should handle missing chromadb

# Client selection
_chroma_client = None
try:
    if chromadb and hasattr(chromadb, "PersistentClient"):
        # old API
        _chroma_client = chromadb.PersistentClient(path=_chroma_path)
    else:
        # new API
        from chromadb import Client
        from chromadb.config import Settings
        _chroma_client = Client(Settings(persist_directory=_chroma_path))
except Exception:
    _chroma_client = None

COLLECTION_NAME = "adgm_refs"

# Embedding model lazy-loaded
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
_embed_model = None


def _load_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model


def api_key_available():
    return bool(os.getenv("GEMINI_API_KEY")) and genai is not None


def _ensure_gemini_configured():
    if genai is None:
        raise RuntimeError("google-generativeai library not installed.")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set.")
    # configure (this call is idempotent)
    genai.configure(api_key=api_key)


def collection_exists():
    if _chroma_client is None:
        return False
    try:
        # try to get existing collection; behavior differs by API
        try:
            coll = _chroma_client.get_collection(COLLECTION_NAME)
            # new API's collection object may not have .count; try best-effort
            cnt = None
            try:
                cnt = coll.count()
            except Exception:
                # old/new may differ; if we got this far, consider it exists
                pass
            return True
        except Exception:
            # try listing/creating as a fallback
            return False
    except Exception:
        return False


def ingest_reference_documents(refs_folder="adgm_refs"):
    """
    Ingest local reference docs into Chroma. Compatible with old/new chroma APIs.
    """
    if _chroma_client is None:
        raise RuntimeError("ChromaDB client not available. Install chromadb and try again.")

    # delete old collection if exists (attempt, ignore errors)
    try:
        _chroma_client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    # create collection - API differs, but both expose create_collection or similar
    try:
        collection = _chroma_client.create_collection(name=COLLECTION_NAME)
    except Exception as e:
        # new Client API may require other args; try to create in alternate way
        try:
            collection = _chroma_client.create_collection(COLLECTION_NAME)
        except Exception:
            raise RuntimeError(f"Failed to create Chroma collection: {e}")

    # gather documents
    paths = glob.glob(os.path.join(refs_folder, "*"))
    if not paths:
        raise FileNotFoundError(f"No reference files found in '{refs_folder}'.")

    docs, metadatas, ids = [], [], []
    for i, p in enumerate(paths):
        text = ""
        if p.lower().endswith(".docx"):
            from docx import Document
            paras = [para.text for para in Document(p).paragraphs if para.text.strip()]
            text = "\n".join(paras)
        else:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

        sentences = re.split(r'(?<=[\.\?\!])\s+', text)
        current, chunk_id = "", 0
        for sent in sentences:
            if len(current) + len(sent) + 1 <= 800:
                current += sent + " "
            else:
                if current.strip():
                    docs.append(current.strip())
                    metadatas.append({"source": os.path.basename(p)})
                    ids.append(f"{i}_{chunk_id}")
                    chunk_id += 1
                current = sent + " "
        if current.strip():
            docs.append(current.strip())
            metadatas.append({"source": os.path.basename(p)})
            ids.append(f"{i}_{chunk_id}")

    if not docs:
        raise ValueError("No document chunks created for ingestion.")

    # embed and add
    embeddings = _load_embed_model().encode(docs, show_progress_bar=True, convert_to_numpy=True)
    # Depending on API, collection.add may accept lists similarly
    try:
        collection.add(ids=ids, documents=docs, metadatas=metadatas, embeddings=embeddings.tolist())
    except Exception:
        # try alternative arg order if needed by some versions
        try:
            collection.add(documents=docs, metadatas=metadatas, ids=ids, embeddings=embeddings.tolist())
        except Exception as e:
            raise RuntimeError(f"Failed to add to Chroma collection: {e}")

    print(f"Ingested {len(docs)} chunks into '{COLLECTION_NAME}'.")


def retrieve_relevant_clauses(query_text, top_k=3):
    if _chroma_client is None:
        return ""
    try:
        coll = _chroma_client.get_collection(COLLECTION_NAME)
    except Exception:
        return ""

    q_emb = _load_embed_model().encode([query_text])[0].tolist()
    try:
        results = coll.query(query_embeddings=[q_emb], n_results=top_k, include=["documents", "metadatas"])
    except Exception:
        # try alternative signature
        results = coll.query(query_embeddings=[q_emb], n_results=top_k, include=["documents"])

    docs = []
    for doclist in results.get("documents", []):
        docs.extend(doclist)
    # Also try to include metadata excerpts if available
    return "\n\n---\n\n".join(docs)


def _clean_gemini_output(output: str) -> str:
    cleaned = (output or "").strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = "\n".join(cleaned.splitlines()[1:-1]).strip()
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].strip()
    return cleaned


def call_gemini_with_context(prompt: str, system_message: str = None, model_name: str = "gemini-1.5-flash"):
    """
    Single call to Gemini. Raises on missing API or returns None if call fails.
    """
    if genai is None:
        raise RuntimeError("google-generativeai package not installed.")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set.")
    _ensure_gemini_configured()
    try:
        generation_config = {
            "temperature": 0.0,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
            "response_mime_type": "text/plain",
        }
        model = genai.GenerativeModel(model_name=model_name, generation_config=generation_config)
        combined_prompt = f"{system_message}\n\n{prompt}" if system_message else prompt
        chat_session = model.start_chat(history=[])
        response = chat_session.send_message(combined_prompt)
        if response and hasattr(response, "text"):
            return _clean_gemini_output(response.text)
        return None
    except Exception as e:
        # propagate the exception message so caller can log and fallback
        raise RuntimeError(f"Gemini call failed: {e}")
