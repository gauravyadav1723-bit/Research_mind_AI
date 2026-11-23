from typing import Dict, Any
from beanie import PydanticObjectId
from langgraph.graph import StateGraph, END
from app.rag.graph.state import IngestionState
from app.rag.loaders.pdf import load_pdf
from app.rag.splitters.text_splitter import split_documents
from app.models.document import ResearchDocument
from app.models.chunk import DocumentChunk
from app.utils.metadata import extract_pdf_global_metadata, detect_section

def load_pdf_node(state: IngestionState) -> Dict[str, Any]:
    """
    Node to load the PDF from file path.
    """
    file_path = state["file_path"]
    try:
        raw_docs = load_pdf(file_path)
        return {
            "raw_documents": raw_docs,
            "status": f"Successfully loaded {len(raw_docs)} pages."
        }
    except Exception as e:
        return {
            "raw_documents": [],
            "status": f"Failed to load PDF: {str(e)}"
        }

def split_docs_node(state: IngestionState) -> Dict[str, Any]:
    """
    Node to split loaded document pages into chunks.
    """
    raw_docs = state.get("raw_documents") or []
    if not raw_docs:
        return {
            "split_documents": [],
            "status": "No documents to split."
        }
    
    try:
        split_docs = split_documents(raw_docs)
        return {
            "split_documents": split_docs,
            "status": f"Successfully split into {len(split_docs)} chunks."
        }
    except Exception as e:
        return {
            "split_documents": [],
            "status": f"Failed to split documents: {str(e)}"
        }

async def index_docs_node(state: IngestionState) -> Dict[str, Any]:
    """
    Extracts metadata from split chunks, saves chunks in MongoDB, and updates Document status.
    """
    split_docs = state.get("split_documents") or []
    doc_id_str = state.get("document_id")
    file_path = state.get("file_path")
    
    if not doc_id_str:
        return {"status": "Error: document_id is missing from graph state."}
        
    doc_id = PydanticObjectId(doc_id_str)
    
    if not split_docs:
        return {
            "status": "No chunks available to index."
        }
    
    try:
        # 1. Extract global PDF metadata (author, year)
        global_meta = extract_pdf_global_metadata(file_path)
        author = global_meta.get("author")
        year = global_meta.get("year")
        
        # 2. Save chunks and track active section
        current_section = "Main Body"
        db_chunks = []
        for chunk_doc in split_docs:
            text = chunk_doc.page_content
            current_section = detect_section(text, current_section)
            page = chunk_doc.metadata.get("page", 0) + 1  # 1-indexed
            
            db_chunk = DocumentChunk(
                id=PydanticObjectId(),
                document_id=doc_id,
                text=text,
                page=page,
                section=current_section,
                author=author,
                year=year,
                metadata=chunk_doc.metadata
            )

            db_chunks.append(db_chunk)
            
        # Bulk insert chunks in MongoDB
        if db_chunks:
            # Clean up any existing chunks for this document first to avoid duplication on re-run
            import asyncio
            existing_chunks = await DocumentChunk.find(DocumentChunk.document_id == doc_id).to_list()
            if existing_chunks:
                await DocumentChunk.find(DocumentChunk.document_id == doc_id).delete()
            await DocumentChunk.insert_many(db_chunks)
            
            # Index chunks in Qdrant
            from app.rag.vectorstore.qdrant import index_chunks
            await index_chunks(db_chunks, doc_id_str)
            
        # 3. Update Document status to indexed

        doc = await ResearchDocument.get(doc_id)
        if doc:
            doc.status = "indexed"
            await doc.save()
            
        return {
            "status": f"Successfully processed paper {doc_id}. Saved {len(db_chunks)} chunks to database."
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Update Document status to failed in case of exceptions
        doc = await ResearchDocument.get(doc_id)
        if doc:
            doc.status = "failed"
            await doc.save()
        return {
            "status": f"Failed during indexing phase: {str(e)}"
        }


# Setup the StateGraph workflow
workflow = StateGraph(IngestionState)

# Register the nodes
workflow.add_node("load_pdf", load_pdf_node)
workflow.add_node("split_docs", split_docs_node)
workflow.add_node("index_docs", index_docs_node)

# Set edges flow
workflow.set_entry_point("load_pdf")
workflow.add_edge("load_pdf", "split_docs")
workflow.add_edge("split_docs", "index_docs")
workflow.add_edge("index_docs", END)

# Compile the workflow graph
ingestion_graph = workflow.compile()

