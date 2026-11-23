import os
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, BackgroundTasks
from app.rag.graph import ingestion_graph
from beanie import PydanticObjectId
from app.api.deps import get_current_user
from app.models.user import User
from app.models.project import ResearchProject
from app.models.document import ResearchDocument
from app.schemas.document import DocumentOut
from app.schemas.query import QueryRequest, QueryResponse

router = APIRouter()

# Upload directory configuration
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads"))

@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    project_id: PydanticObjectId,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    # Ensure upload directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # 1. Validate file extension is PDF
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported."
        )
    
    # 2. Verify project exists
    project = await ResearchProject.get(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research project not found."
        )
        
    # 3. Save file locally with unique prefix to avoid collision
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    try:
        content = await file.read()
        file_size = len(content)
        
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save file to storage: {str(e)}"
        )
        
    # 4. Save metadata to database
    doc = ResearchDocument(
        filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        project_id=project_id,
        user_id=current_user.id,
        status="uploaded"
    )
    await doc.insert()
    return doc

@router.get("/project/{project_id}", response_model=List[DocumentOut])
async def list_project_documents(
    project_id: PydanticObjectId,
    current_user: User = Depends(get_current_user)
):
    # Verify project belongs to current user
    project = await ResearchProject.get(project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this project."
        )
    # List documents mapped to the project and owned by the user
    return await ResearchDocument.find(
        ResearchDocument.project_id == project_id,
        ResearchDocument.user_id == current_user.id
    ).to_list()


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: PydanticObjectId,
    current_user: User = Depends(get_current_user)
):
    doc = await ResearchDocument.get(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )
    return doc

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: PydanticObjectId,
    current_user: User = Depends(get_current_user)
):
    doc = await ResearchDocument.get(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )
        
    # Remove physical file from uploads folder
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception as e:
            # Log error and continue to delete from DB to avoid deadlock
            print(f"Error deleting physical file {doc.file_path}: {str(e)}")
            
    # Delete associated chunks from MongoDB
    from app.models.chunk import DocumentChunk
    await DocumentChunk.find(DocumentChunk.document_id == document_id).delete()

    # Delete associated vectors from Qdrant
    from app.rag.vectorstore.qdrant import delete_document_vectors
    await delete_document_vectors(str(document_id))

    await doc.delete()
    return None


async def run_ingestion_in_background(file_path: str, doc_id: str):
    await ingestion_graph.ainvoke({
        "file_path": file_path,
        "document_id": doc_id
    })

@router.post("/{document_id}/process", response_model=DocumentOut)
async def process_document(
    document_id: PydanticObjectId,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    doc = await ResearchDocument.get(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )
        
    if doc.status == "processing":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document is already being processed."
        )
        
    doc.status = "processing"
    await doc.save()
    
    background_tasks.add_task(
        run_ingestion_in_background,
        doc.file_path,
        str(doc.id)
    )
    
    return doc

@router.post("/{document_id}/query")
async def query_document(
    document_id: PydanticObjectId,
    query_in: QueryRequest,
    current_user: User = Depends(get_current_user)
):
    from fastapi.responses import StreamingResponse
    import json
    import asyncio

    doc = await ResearchDocument.get(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )
        
    if doc.status != "indexed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document status is '{doc.status}'. It must be fully processed and indexed before querying."
        )
        
    async def sse_generator():
        queue = asyncio.Queue()
        
        # Invoke the LangGraph query orchestration workflow
        input_state = {
            "question": query_in.question,
            "document_id": str(document_id),
            "top_k": query_in.top_k,
            "queries": [query_in.question],
            "current_query_idx": 0,
            "retrieved_docs": [],
            "research_notes": "",
            "critic_feedback": "",
            "draft_answer": "",
            "reviewer_feedback": "",
            "has_enough_info": False,
            "answer": "",
            "iteration_count": 0,
            "stream_queue": queue
        }
        
        from app.rag.graph.query_graph import query_graph
        graph_task = asyncio.create_task(query_graph.ainvoke(input_state))
        
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
                await asyncio.sleep(0.01)
            
            # Graph finished
            final_state = await graph_task
            relevant_docs = final_state.get("retrieved_docs", [])
            
            # Format source citations
            sources = []
            for rd in relevant_docs:
                sources.append({
                    "page": rd.metadata.get("page", 0) + 1,
                    "section": rd.metadata.get("section", "Main Body"),
                    "snippet": rd.page_content,
                    "author": rd.metadata.get("author", "Unknown"),
                    "year": rd.metadata.get("year", 0)
                })
            
            yield f"data: {json.dumps({'type': 'done', 'sources': sources})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            if not graph_task.done():
                graph_task.cancel()

    return StreamingResponse(sse_generator(), media_type="text/event-stream")



@router.post("/{document_id}/tools/summarize")
async def api_summarize_paper(
    document_id: PydanticObjectId,
    current_user: User = Depends(get_current_user)
):
    doc = await ResearchDocument.get(document_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this document."
        )
    from app.rag.tools.research_tools import summarize_paper_tool
    try:
        res = await summarize_paper_tool.ainvoke({"document_id": str(document_id)})
        return {"result": res}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{document_id}/tools/gaps")
async def api_find_research_gaps(
    document_id: PydanticObjectId,
    current_user: User = Depends(get_current_user)
):
    doc = await ResearchDocument.get(document_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this document."
        )
    from app.rag.tools.research_tools import find_research_gaps_tool
    try:
        res = await find_research_gaps_tool.ainvoke({"document_id": str(document_id)})
        return {"result": res}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{document_id}/tools/recommend")
async def api_recommend_papers(
    document_id: PydanticObjectId,
    current_user: User = Depends(get_current_user)
):
    doc = await ResearchDocument.get(document_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this document."
        )
    from app.rag.tools.research_tools import recommend_papers_tool
    try:
        res = await recommend_papers_tool.ainvoke({"document_id": str(document_id)})
        return {"result": res}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{document_id}/tools/flashcards")
async def api_generate_flashcards(
    document_id: PydanticObjectId,
    current_user: User = Depends(get_current_user)
):
    doc = await ResearchDocument.get(document_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this document."
        )
    from app.rag.tools.research_tools import generate_flashcards_tool
    try:
        res = await generate_flashcards_tool.ainvoke({"document_id": str(document_id)})
        return {"result": res}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{document_id}/tools/timeline")
async def api_extract_timeline(
    document_id: PydanticObjectId,
    current_user: User = Depends(get_current_user)
):
    doc = await ResearchDocument.get(document_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this document."
        )
    from app.rag.tools.research_tools import timeline_extraction_tool
    try:
        res = await timeline_extraction_tool.ainvoke({"document_id": str(document_id)})
        return {"result": res}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{document_id}/tools/compare")
async def api_compare_papers(
    document_id: PydanticObjectId,
    document_id_2: str,
    current_user: User = Depends(get_current_user)
):
    doc1 = await ResearchDocument.get(document_id)
    doc2 = await ResearchDocument.get(PydanticObjectId(document_id_2))
    if not doc1 or doc1.user_id != current_user.id or not doc2 or doc2.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to one or both of these documents."
        )
    from app.rag.tools.research_tools import compare_papers_tool
    try:
        res = await compare_papers_tool.ainvoke({
            "document_id_1": str(document_id),
            "document_id_2": document_id_2
        })
        return {"result": res}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/project/{project_id}/tools/literature-review")
async def api_literature_review(
    project_id: PydanticObjectId,
    current_user: User = Depends(get_current_user)
):
    project = await ResearchProject.get(project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this project."
        )
    from app.rag.tools.research_tools import literature_review_tool
    try:
        res = await literature_review_tool.ainvoke({"project_id": str(project_id)})
        return {"result": res}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


