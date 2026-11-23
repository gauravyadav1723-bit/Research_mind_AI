from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

def split_documents(
    documents: List[Document],
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[Document]:
    """
    Splits a list of LangChain Document objects into smaller text chunks.
    
    Args:
        documents (List[Document]): The list of raw documents to split.
        chunk_size (int): The target size of each text chunk in characters.
        chunk_overlap (int): The overlap size between adjacent chunks.
        
    Returns:
        List[Document]: List of split Document objects.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True
    )
    return splitter.split_documents(documents)
