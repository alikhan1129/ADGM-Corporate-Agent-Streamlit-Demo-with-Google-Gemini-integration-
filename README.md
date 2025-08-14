# ADGM Corporate Agent — Streamlit Demo (with Google Gemini integration)


This application is a sophisticated proof-of-concept for a corporate services agent, specifically tailored for **Abu Dhabi Global Market (ADGM)** compliance. It leverages a combination of rule-based checks, a local Retrieval-Augmented Generation (RAG) pipeline, and the Google Gemini API to automate the review of company incorporation documents.

The tool accepts multiple `.docx` files, classifies them, verifies them against a process-specific checklist, runs compliance and red-flag checks, and generates both a structured JSON report and annotated `.docx` files with review notes.

-----

## 🎥 Demo
▶️ Demo Video
<p align="center"> <a href="https://drive.google.com/file/d/1iN_J_5Rpsgip3o459yCDTxJu5O7Tk5r0/view?usp=sharing" target="_blank" rel="noopener noreferrer"> Watch the demo video on Google Drive </a> </p>
📸 Screenshots
<p align="center"> <img width="800" alt="Demo Overview" src="https://github.com/user-attachments/assets/78bb4422-d98a-4a70-ba02-f0f0eb5b1e3c" /> </p> <p align="center"> <img width="820" alt="Step 1: Upload & Parse" src="https://github.com/user-attachments/assets/47235e41-ac80-467a-88c7-dd9837c8c423" /> </p> <p align="center"> <img width="820" alt="Step 2: Classification & Detection" src="https://github.com/user-attachments/assets/3b08d936-86d0-4abc-a1b4-529969debb77" /> </p> <p align="center"> <img width="820" alt="Step 3: Compliance Analysis" src="https://github.com/user-attachments/assets/62b6e71f-c83b-47c6-b8e4-d84e0a7fd003" /> </p> <p align="center">

## ‎⭐ Core Features

  * **📄 Document Classification**: Automatically identifies document types from text content, supporting common abbreviations (e.g., 'AoA' for 'Articles of Association').
  * **⚙️ Process Detection**: Intelligently determines the corporate process being undertaken (e.g., "Company Incorporation") based on the combination of uploaded documents.
  * **✅ Incorporation Checklist**: For a "Company Incorporation" process, the app verifies that all required documents have been uploaded (e.g., MoA, AoA, UBO Form).
  * **⚖️ RAG-Powered Legal Analysis**:
      * Uses a local **ChromaDB** vector store for efficient, private retrieval of relevant legal clauses from a knowledge base of ADGM regulations.
      * Integrates **Sentence-Transformers** (`all-MiniLM-L6-v2`) for high-quality semantic embeddings.
      * Calls the **Google Gemini API** (`gemini-1.5-flash`) with the retrieved context to perform nuanced compliance checks that go beyond simple keyword matching.
  * **🚩 Rule-Based Red-Flagging**: Conducts preliminary checks for common issues, such as missing jurisdiction clauses or signature blocks.
  * **📝 Annotated Document Generation**: Creates a "reviewed" version of each uploaded `.docx`, inserting specific review notes directly into the document near the relevant clause.
  * **🧾 Structured JSON Reporting**: Outputs a comprehensive JSON file detailing the detected process, document checklist status, and a full list of all identified issues, each tagged with a severity level (`critical`, `major`, `minor`).

-----

## ‎🛠️ How It Works

The application follows a multi-stage pipeline to analyze and review documents:

1.  **Upload & Parse**: The user uploads one or more `.docx` files via the Streamlit interface. The files are parsed to extract their full text content.
2.  **Classify & Detect**: Each document's text is analyzed to predict its type (`classifier.py`). The collection of document types is then used to infer the overall legal process (e.g., Company Incorporation).
3.  **Checklist Verification**: The list of uploaded document types is compared against a predefined checklist for the detected process.
4.  **Analysis & Issue Flagging**:
      * **Rule-Based:** The text of each document is scanned for basic compliance issues.
      * **RAG + LLM:** For deeper analysis, the document text is used as a query to retrieve relevant articles from the `adgm_refs` vector database. This context, along with the original text, is sent to the Google Gemini API with a specialized prompt to identify potential compliance gaps.
5.  **Report Generation**:
      * All findings are compiled into a structured JSON report.
      * A new, "reviewed" copy of each `.docx` is created, with findings inserted as clearly marked review notes (`docx_utils.py`).
6.  **Download**: The user can download the final JSON report and all the reviewed `.docx` files directly from the UI.

-----

## ‎🚀 Technology Stack

  * **Application Framework**: Streamlit
  * **AI & Machine Learning**:
      * **LLM**: Google Gemini (`gemini-1.5-flash`)
      * **Embeddings**: Sentence-Transformers (`all-MiniLM-L6-v2`)
      * **Vector Store**: ChromaDB
  * **Document Processing**: `python-docx`
  * **Core Libraries**: `dotenv`, `os`, `re`, `json`
  * **Deployment**: Local execution

-----

## ‎🔧 Setup and Installation

### 1\. Prerequisites

  * Python **3.9+**
  * Access to the Google Gemini API and a valid API key.

### 2\. Clone the Repository

```bash
git clone <repository-url>
cd <repository-directory>
```

### 3\. Set Up a Virtual Environment

It's highly recommended to use a virtual environment.

```bash
# Create the virtual environment
python -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
venv\Scripts\activate     # On Windows
```

### 4\. Install Dependencies

Install all required packages from the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

### 5\. Configure Environment Variables

Create a file named `.env` in the root of the project directory. This file is used to store your Gemini API key securely. Add your key to it as follows:

```env
GEMINI_API_KEY="your_google_gemini_api_key_here"
```

### 6\. Prepare Reference Documents

The RAG pipeline requires a local folder containing your ADGM legal reference documents.

  * Create a folder named `adgm_refs` in the project's root directory.
  * Populate this folder with `.txt` or `.docx` files containing ADGM regulations, rules, or guidance notes. The system will read these files to build its knowledge base.

-----

## ‎▶️ Usage

### 1\. Ingest Reference Data (First-Time Setup)

Before you can run analysis, you must populate the local vector database with your ADGM reference documents.

  * Launch the Streamlit application:
    ```bash
    streamlit run app.py
    ```
  * In the application's sidebar, click the **"(Re)Ingest ADGM reference docs"** button.
  * Wait for the confirmation message that the ingestion is complete. This only needs to be done once, or whenever you update the files in the `adgm_refs` folder.

### 2\. Run an Analysis

  * Ensure the Streamlit app is running.
  * Use the file uploader in the main panel to select and upload the `.docx` corporate files you wish to analyze.
  * The application will automatically process the files and display the results, including:
      * The detected process.
      * The checklist verification status.
      * A full, structured JSON report.
      * Download buttons for the reviewed `.docx` files and the JSON report.

-----

## ‎📂 Project Structure

```
.
├── adgm_refs/            # Folder for reference documents (to be created by user)
├── .chromadb/            # Local ChromaDB vector store (created automatically)
├── app.py                # Main Streamlit application file
├── classifier.py         # Logic for document type and process detection
├── docx_utils.py         # Utilities for parsing and annotating .docx files
├── rag_utils.py          # RAG pipeline, ChromaDB management, and Gemini API calls
├── .env                  # API keys and environment variables (to be created by user)
├── README.md             # This file
└── requirements.txt      # Python package dependencies
```
