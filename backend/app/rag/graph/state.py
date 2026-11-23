from typing import TypedDict, List, Optional
from langchain_core.documents import Document

class IngestionState(TypedDict):
    """
    State representing the PDF ingestion pipeline.
    """
    file_path: str
    document_id: str
    raw_documents: Optional[List[Document]]
    split_documents: Optional[List[Document]]

    status: str
