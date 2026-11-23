from typing import List
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader

def load_pdf(file_path: str) -> List[Document]:
    """
    Loads and extracts text and metadata from a PDF file using PyPDFLoader.
    
    Args:
        file_path (str): The local path to the PDF file.
        
    Returns:
        List[Document]: List of LangChain Document objects representing the PDF pages.
    """
    loader = PyPDFLoader(file_path)
    return loader.load()
