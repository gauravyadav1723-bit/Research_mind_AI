import asyncio
import re
import json
from typing import List, TypedDict, Dict, Any
from langchain_core.documents import Document
from langgraph.graph import StateGraph, START, END

# Define Graph State including Specialist parameters
class QueryGraphState(TypedDict):
    question: str
    document_id: str
    top_k: int
    queries: List[str]
    current_query_idx: int
    retrieved_docs: List[Document]
    research_notes: str         # Added Researcher specialist state
    critic_feedback: str        # Added Critic specialist state
    has_enough_info: bool
    draft_answer: str           # Added Writer specialist state
    reviewer_feedback: str      # Added Reviewer specialist state
    answer: str                 # Final Answer
    iteration_count: int
    stream_queue: Any           # Queue for real-time SSE streaming


# Node 1: Planner Agent
async def planner_node(state: QueryGraphState) -> Dict[str, Any]:
    """
    Decomposes the user's research question into search queries.
    """
    if "stream_queue" in state and state["stream_queue"]:
        await state["stream_queue"].put({"type": "status", "content": "Planning search queries..."})

    question = state["question"]

    from app.config.settings import settings
    from langchain_groq import ChatGroq

    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        groq_api_key=settings.GROQ_API_KEY,
        temperature=0.0
    )

    prompt = (
        f"You are a search planner. Break down the user question into up to 2 distinct search queries "
        f"to retrieve relevant context from a research paper. The first query should be the original question.\n"
        f"Question: \"{question}\"\n\n"
        f"Respond ONLY with a JSON array of strings (the search queries).\n"
        f"Do not write any introductory or concluding text, only return the raw JSON array.\n"
        f"Example format: [ \"What are transformer models?\", \"transformer model architecture details\" ]"
    )

    try:
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)

        json_match = re.search(r"\[\s*\".*\"\s*\]", content, re.DOTALL)
        if json_match:
            queries = json.loads(json_match.group(0))
        else:
            queries = json.loads(content)

        queries = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
        if not queries or question not in queries:
            queries = [question] + queries
    except Exception:
        # Fallback to only the original question
        queries = [question]

    return {
        "queries": queries,
        "current_query_idx": 0,
        "iteration_count": 0
    }

# Node 2: Retriever Agent
async def retrieve_node(state: QueryGraphState) -> Dict[str, Any]:
    """
    Retrieves candidate chunks using the Hybrid search retriever.
    """
    document_id = state["document_id"]
    top_k = state["top_k"]
    queries = state["queries"]
    idx = state["current_query_idx"]

    # Select query
    query = queries[idx] if idx < len(queries) else state["question"]

    if "stream_queue" in state and state["stream_queue"]:
        await state["stream_queue"].put({"type": "status", "content": f"Retrieving context for: '{query}'..."})

    from app.rag.embeddings import get_embeddings
    from app.rag.vectorstore.qdrant import get_qdrant_client
    from app.config.settings import settings
    from app.rag.retrievers.hybrid import HybridRetriever

    q_client = get_qdrant_client()
    embeddings = get_embeddings()

    retriever = HybridRetriever(
        client=q_client,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        embeddings=embeddings,
        document_id=document_id,
        top_k=top_k
    )

    new_docs = await retriever.ainvoke(query)

    # Merge new documents avoiding duplicate chunk IDs
    accumulated = list(state["retrieved_docs"])
    existing_chunk_ids = {d.metadata.get("chunk_id") for d in accumulated if d.metadata.get("chunk_id")}

    for doc in new_docs:
        cid = doc.metadata.get("chunk_id")
        if not cid or cid not in existing_chunk_ids:
            accumulated.append(doc)
            if cid:
                existing_chunk_ids.add(cid)

    return {
        "retrieved_docs": accumulated
    }

# Node 3: Researcher Agent
async def researcher_node(state: QueryGraphState) -> Dict[str, Any]:
    """
    Analyzes the retrieved chunks and extracts key facts, definitions, and insights.
    """
    if "stream_queue" in state and state["stream_queue"]:
        await state["stream_queue"].put({"type": "status", "content": "Researcher specialist extracting key facts..."})

    question = state["question"]
    retrieved_docs = state["retrieved_docs"]

    from app.config.settings import settings
    from langchain_groq import ChatGroq
    from app.rag.chains.rag import format_docs

    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        groq_api_key=settings.GROQ_API_KEY,
        temperature=0.0
    )

    context_str = format_docs(retrieved_docs)
    prompt = (
        f"You are a Researcher specialist. Analyze the retrieved context chunks and extract all key facts, "
        f"definitions, quantitative data points, and technical insights relevant to answering the question: \"{question}\".\n"
        f"Organize your findings into a clear, bulleted research brief. Maintain any source metadata references (paper and page) "
        f"associated with each fact so they can be cited later.\n\n"
        f"Context:\n{context_str}\n\n"
        f"Research Brief:"
    )

    try:
        response = await llm.ainvoke(prompt)
        research_notes = response.content if hasattr(response, 'content') else str(response)
    except Exception as e:
        research_notes = f"Research extraction failed: {str(e)}"

    return {
        "research_notes": research_notes
    }

# Node 4: Critic Agent
async def critic_node(state: QueryGraphState) -> Dict[str, Any]:
    """
    Reviews extracted research notes for sufficiency and identifies gaps.
    """
    if "stream_queue" in state and state["stream_queue"]:
        await state["stream_queue"].put({"type": "status", "content": "Critic specialist evaluating information completeness..."})

    question = state["question"]
    research_notes = state["research_notes"]

    from app.config.settings import settings
    from langchain_groq import ChatGroq

    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        groq_api_key=settings.GROQ_API_KEY,
        temperature=0.0
    )

    prompt = (
        f"You are a Critic specialist. Review the extracted research notes against the user's question.\n"
        f"Question: \"{question}\"\n"
        f"Research Notes:\n{research_notes}\n\n"
        f"Evaluate if there is sufficient information to answer the question fully and accurately. "
        f"If NO, identify what missing detail is needed, and formulate a refined search query for retrieval.\n"
        f"Respond ONLY in JSON format: {{\"sufficient\": true/false, \"feedback\": \"...\", \"refined_query\": \"...\"}}."
        f"Do not write any introductory or concluding text, only return the raw JSON object."
    )

    try:
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)

        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            eval_res = json.loads(json_match.group(0))
        else:
            eval_res = json.loads(content)

        sufficient = bool(eval_res.get("sufficient", False))
        feedback = eval_res.get("feedback", "")
        refined_query = eval_res.get("refined_query", "")
    except Exception as e:
        sufficient = True
        feedback = f"Critic evaluation failed: {str(e)}"
        refined_query = ""

    queries = list(state["queries"])
    if not sufficient and refined_query:
        queries.append(refined_query)

    return {
        "has_enough_info": sufficient,
        "critic_feedback": feedback,
        "queries": queries
    }

# Node 5: Increment Index (Loop Counter Node)
async def increment_idx_node(state: QueryGraphState) -> Dict[str, Any]:
    """
    Updates graph index pointer for loop control.
    """
    return {
        "current_query_idx": state["current_query_idx"] + 1,
        "iteration_count": state["iteration_count"] + 1
    }

# Node 6: Writer Agent
async def writer_node(state: QueryGraphState) -> Dict[str, Any]:
    """
    Drafts the RAG answer based on the research brief and chunks.
    """
    if "stream_queue" in state and state["stream_queue"]:
        await state["stream_queue"].put({"type": "status", "content": "Writer specialist drafting the response..."})

    question = state["question"]
    research_notes = state["research_notes"]
    retrieved_docs = state["retrieved_docs"]

    from app.config.settings import settings
    from langchain_groq import ChatGroq
    from app.rag.chains.rag import format_docs

    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        groq_api_key=settings.GROQ_API_KEY,
        temperature=0.0
    )

    context_str = format_docs(retrieved_docs)
    prompt = (
        f"You are a Writer specialist. Your task is to write a comprehensive, professional answer to the user's question "
        f"based on the research notes and context.\n"
        f"Question: \"{question}\"\n\n"
        f"Research Notes:\n{research_notes}\n\n"
        f"Context Chunks:\n{context_str}\n\n"
        f"You MUST cite sources inline using the format: (Source: [Paper Name] Page [Page Number]).\n"
        f"Draft Answer:"
    )

    try:
        response = await llm.ainvoke(prompt)
        draft_answer = response.content if hasattr(response, 'content') else str(response)
    except Exception as e:
        draft_answer = f"Drafting failed: {str(e)}"

    return {
        "draft_answer": draft_answer
    }

# Node 7: Reviewer Agent
async def reviewer_node(state: QueryGraphState) -> Dict[str, Any]:
    """
    Polishes the drafted answer and checks for citation validity and hallucination.
    """
    if "stream_queue" in state and state["stream_queue"]:
        await state["stream_queue"].put({"type": "status", "content": "Reviewer specialist polishing response and verifying citations..."})

    question = state["question"]
    draft_answer = state["draft_answer"]
    retrieved_docs = state["retrieved_docs"]

    from app.config.settings import settings
    from langchain_groq import ChatGroq
    from app.rag.chains.rag import format_docs

    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        groq_api_key=settings.GROQ_API_KEY,
        temperature=0.0
    )

    context_str = format_docs(retrieved_docs)
    prompt = (
        f"You are a Reviewer specialist. Review the draft answer to the user's question.\n"
        f"Your goal is to ensure the answer is: \n"
        f"1. Free of hallucinations (matches context).\n"
        f"2. Professionally formatted with correct inline citations matching the format: (Source: [Paper Name] Page [Page Number]).\n"
        f"3. Fluent, concise, and complete.\n\n"
        f"Question: \"{question}\"\n"
        f"Draft Answer:\n{draft_answer}\n\n"
        f"Reference Context Chunks:\n{context_str}\n\n"
        f"Produce the final polished answer. Do not include any reviewer comments, meta-discussion, or greetings. "
        f"Respond ONLY with the final polished answer text.\n"
        f"Final Polished Answer:"
    )

    try:
        final_answer = ""
        async for chunk in llm.astream(prompt):
            content = chunk.content if hasattr(chunk, 'content') else str(chunk)
            final_answer += content
            if "stream_queue" in state and state["stream_queue"]:
                await state["stream_queue"].put({"type": "token", "content": content})
        
        if not final_answer:
            final_answer = "Review failed to generate response."
    except Exception as e:
        final_answer = f"Review failed: {str(e)}. Fallback to draft: {draft_answer}"

    if "stream_queue" in state and state["stream_queue"]:
        await state["stream_queue"].put(None)

    return {
        "answer": final_answer
    }

# Conditional Edge
def should_retrieve_more(state: QueryGraphState) -> str:
    """
    Directs graph routing based on loop limits or evaluation sufficiency.
    """
    if state["has_enough_info"] or state["iteration_count"] >= 2 or state["current_query_idx"] + 1 >= len(state["queries"]):
        return "writer"
    return "retrieve_more"

# Construct the Specialists Graph
workflow = StateGraph(QueryGraphState)

workflow.add_node("planner", planner_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("researcher", researcher_node)
workflow.add_node("critic", critic_node)
workflow.add_node("increment_idx", increment_idx_node)
workflow.add_node("writer", writer_node)
workflow.add_node("reviewer", reviewer_node)

workflow.set_entry_point("planner")
workflow.add_edge("planner", "retrieve")
workflow.add_edge("retrieve", "researcher")
workflow.add_edge("researcher", "critic")

workflow.add_conditional_edges(
    "critic",
    should_retrieve_more,
    {
        "writer": "writer",
        "retrieve_more": "increment_idx"
    }
)
workflow.add_edge("increment_idx", "retrieve")
workflow.add_edge("writer", "reviewer")
workflow.add_edge("reviewer", END)

query_graph = workflow.compile()

