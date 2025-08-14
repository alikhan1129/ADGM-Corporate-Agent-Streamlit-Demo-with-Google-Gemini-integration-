# app.py
import streamlit as st
from docx_utils import parse_docx_documents, insert_review_notes_and_save
from classifier import classify_doc_type, detect_process
import json, tempfile, os, logging, time
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

st.set_page_config(page_title="ADGM Corporate Agent — Streamlit Demo", layout="wide")
st.title("ADGM-Compliant Corporate Agent — Streamlit Demo")
st.markdown(
    "Upload `.docx` documents for a company incorporation (or other ADGM process). "
    "We'll parse, check a checklist, flag issues, and produce a reviewed `.docx` and JSON report."
)

# Try to import rag_utils safely
rag_utils = None
try:
    import rag_utils as _rag_utils
    rag_utils = _rag_utils
except Exception as e:
    logging.error(f"Failed to import rag_utils: {e}")
    st.warning("RAG utilities not available. Some features will be disabled.")

with st.sidebar:
    st.header("RAG / Refs")
    if st.button("(Re)Ingest ADGM reference docs"):
        if rag_utils is None:
            st.error("RAG utilities not available (missing dependencies or rag_utils import error). Check logs.")
        else:
            refs_folder = 'adgm_refs'
            if not os.path.isdir(refs_folder):
                st.error(f"Reference folder '{refs_folder}' not found. Please create it and add ADGM refs before ingesting.")
            else:
                st.info("Ingesting reference docs into local vector DB (this may take a minute)...")
                try:
                    rag_utils.ingest_reference_documents(refs_folder=refs_folder)
                    st.success("Reference documents ingested.")
                except Exception as e:
                    logging.error(f"Ingest failed: {e}")
                    st.error(f"Ingest failed: {e}")

uploaded_files = st.file_uploader("Upload one or more .docx files", type=["docx"], accept_multiple_files=True)

if uploaded_files:
    tmpdir = tempfile.mkdtemp(prefix="adgm_upl_")
    saved_paths = []
    for up in uploaded_files:
        path = os.path.join(tmpdir, up.name)
        with open(path, "wb") as f:
            f.write(up.read())
        saved_paths.append(path)

    st.success(f"Saved {len(saved_paths)} files.")
    docs = parse_docx_documents(saved_paths)
    for d in docs:
        d["predicted_type"] = classify_doc_type(d["text"])
    process = detect_process([d["predicted_type"] for d in docs])
    st.markdown(f"**Detected process:** {process}")

    # required docs for incorporation
    required_docs = []
    if process == "Company Incorporation":
        required_docs = [
            "Articles of Association",
            "Memorandum of Association",
            "Incorporation Application Form",
            "UBO Declaration Form",
            "Register of Members and Directors"
        ]

    uploaded_doc_types = [d["predicted_type"] for d in docs]
    missing = [r for r in required_docs if r not in uploaded_doc_types]
    st.write("Required documents:", required_docs)
    st.write("Uploaded types:", uploaded_doc_types)
    if missing:
        st.warning(f"It appears that you’re trying to {process}. You have uploaded {len(uploaded_doc_types)} out of {len(required_docs)} required documents. Missing: {missing}")
    else:
        st.success("All required documents present (per checklist).")

    st.info("Running red-flag detection + (optional) RAG/Gemini. This may take a little while.")
    issues_found = []

    rag_available = False
    if rag_utils:
        try:
            rag_available = rag_utils.collection_exists()
        except Exception:
            rag_available = False

    if not rag_utils:
        st.warning("RAG utilities not loaded. RAG-based checks will be skipped.")
    elif not rag_available:
        st.warning("RAG collection not found. RAG-based checks will be skipped until you ingest reference docs.")

    # Basic rule-based checks and prepare RAG inputs
    rag_prompts = []
    flagged_docs_for_rag = []
    for d in docs:
        text = d["text"]
        # Basic checks
        if ("adgm" not in text.lower()) and ("abu dhabi global market" not in text.lower()):
            issues_found.append({
                "document": d["predicted_type"],
                "section": "Jurisdiction clause",
                "issue": "Jurisdiction clause does not specify ADGM",
                "severity": "High",
                "suggestion": "Update jurisdiction to Abu Dhabi Global Market (ADGM) Courts."
            })
        if ("signature" not in text.lower()) and ("signed" not in text.lower()):
            issues_found.append({
                "document": d["predicted_type"],
                "section": "Signatory section",
                "issue": "Missing explicit signatory or signature block",
                "severity": "Medium",
                "suggestion": "Add signatory name, title and date."
            })

        # If RAG available, prepare retrieval context for each doc
        top_k_ctx = ""
        if rag_utils and rag_available:
            try:
                top_k_ctx = rag_utils.retrieve_relevant_clauses(d["text"], top_k=3)
            except Exception as e:
                logging.warning(f"RAG retrieval failed for {d['predicted_type']}: {e}")
                top_k_ctx = ""

        # We'll only send docs with potential issues to Gemini (to reduce quota usage)
        # Construct a compact prompt for each doc and accumulate
        doc_summary = {
            "predicted_type": d["predicted_type"],
            "text_preview": d["text"][:5000],
            "context": top_k_ctx
        }
        flagged_docs_for_rag.append(doc_summary)

    # Batch all flagged docs into one Gemini prompt if Gemini is available
    gemini_response = None
    if rag_utils and rag_utils.api_key_available():
        try:
            # Build a single combined prompt to analyze all uploaded docs at once
            combined_docs_text = ""
            for dd in flagged_docs_for_rag:
                combined_docs_text += f"DOCUMENT TYPE: {dd['predicted_type']}\n{dd['text_preview']}\n\n"
                if dd.get("context"):
                    combined_docs_text += f"RELEVANT ADGM CONTEXT:\n{dd['context']}\n\n"
                combined_docs_text += "----\n\n"

            prompt = f"""SYSTEM: You are a legal compliance assistant specialized in Abu Dhabi Global Market (ADGM) regulations.
User: Review the following documents. For each document, return a JSON array (list) of identified issues with keys: section, issue, severity, suggestion. Return a top-level JSON object mapping document types to their issues.

DOCUMENTS:
{combined_docs_text}
"""
            # single call for all documents
            gemini_response = rag_utils.call_gemini_with_context(
                prompt,
                system_message="Legal assistant: ADGM rules apply",
                model_name="gemini-1.5-flash"
            )
        except Exception as e:
            # robust fallback if Gemini fails (rate limit / quota / network)
            logging.error(f"Gemini call failed: {e}")
            gemini_response = None
    else:
        # not available: mark that Gemini wasn't used
        for d in docs:
            issues_found.append({
                "document": d["predicted_type"],
                "section": "RAG Analysis",
                "issue": "Gemini or RAG unavailable.",
                "severity": "Low",
                "suggestion": "Set GEMINI_API_KEY and ingest references, or check quota."
            })

    # Parse gemini response if present
    if gemini_response:
        try:
            cleaned = rag_utils._clean_gemini_output(gemini_response) if rag_utils else gemini_response.strip()
            parsed = json.loads(cleaned)
            # parsed expected to be { "Articles of Association": [...], "Incorporation Application Form": [...] }
            if isinstance(parsed, dict):
                for doc_type, issues in parsed.items():
                    if isinstance(issues, dict):
                        issues = [issues]
                    for p in issues:
                        p["document"] = doc_type
                        issues_found.append(p)
            elif isinstance(parsed, list):
                # fallback: treat as list of issues without doc grouping
                for p in parsed:
                    if isinstance(p, dict):
                        issues_found.append(p)
            else:
                # unrecognized structure - attach raw
                issues_found.append({
                    "document": "RAG",
                    "section": "RAG Analysis",
                    "issue": f"Unrecognized Gemini response structure: {type(parsed)}",
                    "severity": "Low",
                    "suggestion": "Manual review of Gemini output."
                })
        except Exception as e:
            logging.error(f"Failed to parse Gemini response: {e}")
            issues_found.append({
                "document": "RAG",
                "section": "RAG Analysis",
                "issue": gemini_response[:1000],
                "severity": "Low",
                "suggestion": "Manual review recommended."
            })

    # Build final report
    report = {
        "process": process,
        "documents_uploaded": len(uploaded_doc_types),
        "required_documents": len(required_docs),
        "missing_documents": missing,
        "issues_found": issues_found
    }

    st.header("Structured JSON report")
    st.json(report)

    # Insert review notes into docs and create outputs
    out_files = []
    for d in docs:
        out_path = os.path.join(tmpdir, "reviewed_" + os.path.basename(d["path"]))
        doc_issues = [i for i in issues_found if i.get("document") == d["predicted_type"]]
        try:
            insert_review_notes_and_save(d["path"], doc_issues, out_path)
            out_files.append(out_path)
        except Exception as e:
            logging.error(f"Failed to insert review notes for {d['path']}: {e}")
            st.error(f"Failed to insert review notes for {os.path.basename(d['path'])}")

    for p in out_files:
        with open(p, "rb") as f:
            st.download_button(label=f"Download reviewed: {os.path.basename(p)}", data=f, file_name=os.path.basename(p))

    st.download_button(label="Download JSON report", data=json.dumps(report, indent=2), file_name="adgm_report.json")

else:
    st.info("Upload `.docx` files to begin.")
