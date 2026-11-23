import json
import re
from typing import List
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from beanie import PydanticObjectId
from app.config.settings import settings
from app.models.chunk import DocumentChunk
from app.models.document import ResearchDocument
from app.models.project import ResearchProject

def get_groq_llm() -> ChatGroq:
    """
    Helper to instantiate Groq LLM.
    """
    return ChatGroq(
        model=settings.GROQ_MODEL,
        groq_api_key=settings.GROQ_API_KEY,
        temperature=0.0
    )

@tool
async def summarize_paper_tool(document_id: str) -> str:
    """
    Generates a comprehensive structured summary of a research paper given its document_id.
    Includes: Executive Summary, Key Methodology, Main Findings, and Research Implications.
    """
    # 1. Fetch document and top chunks
    doc = await ResearchDocument.get(PydanticObjectId(document_id))
    if not doc:
        return "Error: Document not found."

    # Fetch top 10 chunks to avoid model token limits while providing enough context
    chunks = await DocumentChunk.find(
        DocumentChunk.document_id == PydanticObjectId(document_id)
    ).limit(10).to_list()

    if not chunks:
        return "Error: No chunks found for the document."

    context = "\n\n".join([f"[Page {c.page}] {c.text}" for c in chunks])
    
    llm = get_groq_llm()
    prompt = (
        f"You are an expert academic summarizer. Generate a comprehensive, professional, structured "
        f"summary of the research paper titled \"{doc.filename}\" based on the following context:\n\n"
        f"Context:\n{context}\n\n"
        f"Synthesize the summary using these exact headers:\n"
        f"### 📄 Document Summary: {doc.filename}\n"
        f"1. **Executive Summary**\n"
        f"2. **Key Methodology**\n"
        f"3. **Main Findings & Contributions**\n"
        f"4. **Research Implications**\n\n"
        f"Summary:"
    )

    response = await llm.ainvoke(prompt)
    return response.content if hasattr(response, 'content') else str(response)

@tool
async def compare_papers_tool(document_id_1: str, document_id_2: str) -> str:
    """
    Performs a comparative analysis between two research papers given their document_ids.
    Outlines commonalities, key differences, and contrasting methodologies/findings.
    """
    doc1 = await ResearchDocument.get(PydanticObjectId(document_id_1))
    doc2 = await ResearchDocument.get(PydanticObjectId(document_id_2))
    
    if not doc1 or not doc2:
        return "Error: One or both documents could not be found."

    chunks1 = await DocumentChunk.find(DocumentChunk.document_id == PydanticObjectId(document_id_1)).limit(5).to_list()
    chunks2 = await DocumentChunk.find(DocumentChunk.document_id == PydanticObjectId(document_id_2)).limit(5).to_list()

    context1 = "\n".join([c.text for c in chunks1])
    context2 = "\n".join([c.text for c in chunks2])

    llm = get_groq_llm()
    prompt = (
        f"You are a critical scientific evaluator. Compare the following two research papers:\n"
        f"Paper 1: \"{doc1.filename}\"\n"
        f"Paper 2: \"{doc2.filename}\"\n\n"
        f"Context for Paper 1:\n{context1}\n\n"
        f"Context for Paper 2:\n{context2}\n\n"
        f"Provide a comparative report using these exact headers:\n"
        f"### ⚖️ Comparative Report\n"
        f"- **Common Themes & Overlaps**: What questions or topics do both papers share?\n"
        f"- **Methodological Contrasts**: How do their experimental designs, methodologies, or approaches differ?\n"
        f"- **Conflicting Findings / Differing Conclusions**: What claims or findings diverge between the two papers?\n"
        f"- **Synthesis**: A final assessment of how these two papers complement or challenge each other.\n\n"
        f"Report:"
    )

    response = await llm.ainvoke(prompt)
    return response.content if hasattr(response, 'content') else str(response)

@tool
async def literature_review_tool(project_id: str) -> str:
    """
    Generates a thematic literature review synthesizing all documents uploaded under a specific project_id.
    """
    project = await ResearchProject.get(PydanticObjectId(project_id))
    if not project:
        return "Error: Project not found."

    docs = await ResearchDocument.find(ResearchDocument.project_id == PydanticObjectId(project_id)).to_list()
    if not docs:
        return "Error: No documents found in this project to perform a literature review on."

    # For each document, grab the top 3 chunks to synthesize
    combined_context = ""
    for d in docs:
        chunks = await DocumentChunk.find(DocumentChunk.document_id == d.id).limit(3).to_list()
        combined_context += f"--- Paper: {d.filename} ---\n"
        combined_context += "\n".join([c.text for c in chunks]) + "\n\n"

    llm = get_groq_llm()
    prompt = (
        f"You are a senior academic writer. Generate a comprehensive thematic literature review for "
        f"the research project \"{project.title}\" ({project.description}) incorporating the following sources:\n\n"
        f"Sources:\n{combined_context}\n"
        f"Review structure requirements:\n"
        f"### 📚 Literature Review: {project.title}\n"
        f"1. **Introduction & Thematic Scope** (Establish the domain and scope of the research)\n"
        f"2. **Thematic Synthesis** (Group findings thematic rather than listing papers sequentially; contrast findings)\n"
        f"3. **Open Challenges & Directives** (What gaps does this collective literature expose?)\n\n"
        f"Review:"
    )

    response = await llm.ainvoke(prompt)
    return response.content if hasattr(response, 'content') else str(response)

@tool
async def find_research_gaps_tool(document_id: str) -> str:
    """
    Analyzes limitations, assumptions, and future work of a paper given its document_id to identify potential research gaps.
    """
    doc = await ResearchDocument.get(PydanticObjectId(document_id))
    if not doc:
        return "Error: Document not found."

    # Fetch chunks containing limitation/future keywords, or fallback to the final chunks of the paper
    chunks = await DocumentChunk.find(
        DocumentChunk.document_id == PydanticObjectId(document_id),
        DocumentChunk.text == re.compile(r"limitation|future work|concl|discussion|assumption", re.IGNORECASE)
    ).limit(8).to_list()


    if not chunks:
        # Fallback to last 8 chunks
        chunks = await DocumentChunk.find(
            DocumentChunk.document_id == PydanticObjectId(document_id)
        ).sort("-page").limit(8).to_list()
        chunks.reverse()

    context = "\n\n".join([f"[Page {c.page}] {c.text}" for c in chunks])

    llm = get_groq_llm()
    prompt = (
        f"You are a critical reviewer. Identify open research gaps, methodological limitations, "
        f"and opportunities for future work in the paper \"{doc.filename}\" based on the following text:\n\n"
        f"Context:\n{context}\n\n"
        f"Structure your response as follows:\n"
        f"### 🔍 Research Gaps & Future Directions: {doc.filename}\n"
        f"- **Methodological Limitations**: What constraints did the authors outline regarding their experimental design or data?\n"
        f"- **Under-explored Assumptions**: What concepts or constraints did the paper assume without rigorous proof?\n"
        f"- **Identified Research Gaps**: What specific open research questions are left unanswered?\n"
        f"- **Proposed Extension Project**: Suggest a concrete follow-up research study that addresses these gaps.\n\n"
        f"Report:"
    )

    response = await llm.ainvoke(prompt)
    return response.content if hasattr(response, 'content') else str(response)

@tool
async def recommend_papers_tool(document_id: str) -> str:
    """
    Suggests theoretical keywords, authors, search terms, and follow-up titles to look up based on the paper's themes.
    """
    doc = await ResearchDocument.get(PydanticObjectId(document_id))
    if not doc:
        return "Error: Document not found."

    chunks = await DocumentChunk.find(
        DocumentChunk.document_id == PydanticObjectId(document_id)
    ).limit(5).to_list()

    context = "\n".join([c.text for c in chunks])

    llm = get_groq_llm()
    prompt = (
        f"You are a research advisor. Based on the topics, theories, and keywords in the paper \"{doc.filename}\", "
        f"recommend related terms, keywords, and follow-up literature areas to search for. Here is a sample context from the paper:\n\n"
        f"{context}\n\n"
        f"Provide recommendation guides under these headers:\n"
        f"### 🧭 Literature Exploration Guide: {doc.filename}\n"
        f"1. **Core Semantic Search Queries** (Provide 3 precise strings to paste into Google Scholar/Arxiv)\n"
        f"2. **Related Theoretical Frameworks** (Key theories or concepts to explore that expand on this paper)\n"
        f"3. **Pivotal Author / Lab Recommendations** (Types of researchers or seminal labs publishing in this domain)\n\n"
        f"Guide:"
    )

    response = await llm.ainvoke(prompt)
    return response.content if hasattr(response, 'content') else str(response)

@tool
async def generate_flashcards_tool(document_id: str) -> str:
    """
    Extracts core concepts, models, and definitions from a paper given its document_id and formats them as educational Q&A flashcards.
    """
    doc = await ResearchDocument.get(PydanticObjectId(document_id))
    if not doc:
        return "Error: Document not found."

    chunks = await DocumentChunk.find(
        DocumentChunk.document_id == PydanticObjectId(document_id)
    ).limit(8).to_list()

    context = "\n\n".join([c.text for c in chunks])

    llm = get_groq_llm()
    prompt = (
        f"You are an educational designer. Extract 5 key terminology terms, core algorithms, models, "
        f"or concepts from the paper \"{doc.filename}\" and format them as educational flashcards (Question & Answer pairs).\n\n"
        f"Context:\n{context}\n\n"
        f"Structure the response exactly as follows:\n"
        f"### 📇 Conceptual Flashcards: {doc.filename}\n"
        f"Format each card as:\n"
        f"**Card [Number]: [Concept Name]**\n"
        f"- **Question**: [Conceptual Q]\n"
        f"- **Answer**: [Detailed response based on paper context]\n\n"
        f"Flashcards:"
    )

    response = await llm.ainvoke(prompt)
    return response.content if hasattr(response, 'content') else str(response)

@tool
async def timeline_extraction_tool(document_id: str) -> str:
    """
    Extracts chronological events, historical context, publication timelines, or development milestones mentioned in the paper.
    """
    doc = await ResearchDocument.get(PydanticObjectId(document_id))
    if not doc:
        return "Error: Document not found."

    # Look for chunks containing years (e.g. 19xx, 20xx) or time/history keywords
    chunks = await DocumentChunk.find(
        DocumentChunk.document_id == PydanticObjectId(document_id),
        DocumentChunk.text == re.compile(r"19\d{2}|20\d{2}|history|milestone|chronology|timeline", re.IGNORECASE)
    ).limit(8).to_list()


    if not chunks:
        # Fallback to top chunks
        chunks = await DocumentChunk.find(
            DocumentChunk.document_id == PydanticObjectId(document_id)
        ).limit(8).to_list()

    context = "\n\n".join([c.text for c in chunks])

    llm = get_groq_llm()
    prompt = (
        f"You are an historical timeline extractor. Extract chronological events, development milestones, "
        f"publication dates, or historical evolution points mentioned in the paper \"{doc.filename}\" based on the following text:\n\n"
        f"Context:\n{context}\n\n"
        f"Format your output as a Markdown timeline list with dates/milestones bolded, e.g.:\n"
        f"### 📅 Timeline & Evolution: {doc.filename}\n"
        f"- **[Year/Milestone]**: [Description of event, technology milestone, or historical context]\n\n"
        f"Timeline:"
    )

    response = await llm.ainvoke(prompt)
    return response.content if hasattr(response, 'content') else str(response)
