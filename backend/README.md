# 🧠 ResearchMind-AI — Backend API

FastAPI asynchronous backend powering ResearchMind-AI with multi-agent LangGraph orchestration, hybrid vector search, Beanie/MongoDB persistence, and real-time SSE streaming.

## 🛠️ Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Async ASGI)
- **Multi-Agent Orchestration**: [LangGraph](https://github.com/langchain-ai/langgraph) (Planner, Retriever, Researcher, Critic, Writer, Reviewer)
- **RAG & Tooling**: [LangChain](https://github.com/langchain-ai/langchain)
- **Primary LLM**: [Groq Cloud](https://console.groq.com/) (`llama-3.3-70b-versatile`)
- **Embeddings**: [Google Generative AI](https://aistudio.google.com/) (`models/gemini-embedding-001`)
- **Database & ODM**: [MongoDB](https://www.mongodb.com/) via [Motor](https://motor.readthedocs.io/) & [Beanie](https://beanie-odm.net/)
- **Vector Search**: [Qdrant](https://qdrant.tech/) (with automatic fallback to in-memory vector database)
- **Sparse Retrieval**: BM25 Okapi (`rank-bm25`) + Reciprocal Rank Fusion (RRF)
- **Auth & Security**: PyJWT & Bcrypt password hashing

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- MongoDB instance (Local or MongoDB Atlas)
- Groq API Key & Google Gemini API Key

---

### Setup Instructions

1. **Create and activate a virtual environment**:
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and fill in the required keys:
   ```bash
   cp .env.example .env
   ```

   Key environment variables:
   - `MONGODB_URL`: MongoDB connection URI
   - `GROQ_API_KEY`: Groq API key for Llama 3.3 70B
   - `GOOGLE_API_KEY`: Google Gemini API key for embeddings
   - `SECRET_KEY`: Secret key for JWT session tokens
   - `QDRANT_URL`: Qdrant endpoint (defaults to `http://localhost:6333`, falls back to in-memory if unreachable)

4. **Run the development server**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   Or:
   ```bash
   python run_server.py
   ```

5. **Access Interactive API Docs**:
   - Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
   - ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
