from typing import Tuple, Any, List
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from qdrant_client.http import models

from app.config.settings import settings
from app.rag.embeddings import get_embeddings
from app.rag.vectorstore.qdrant import get_qdrant_client
from app.rag.prompts.rag import get_rag_prompt
from app.rag.retrievers.hybrid import HybridRetriever


class CustomQdrantRetriever(BaseRetriever):
    client: Any
    collection_name: str
    embeddings: Any
    document_id: str
    top_k: int = 4
    
    def _get_relevant_documents(self, query: str, *, run_manager: Any = None) -> List[Document]:
        # 1. Embed user query using Google Generative AI
        query_vector = self.embeddings.embed_query(query)
        
        # 2. Filter by document_id
        filter_cond = models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=self.document_id)
                )
            ]
        )
        
        # 3. Query Qdrant using the new unified query_points API
        res = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=filter_cond,
            limit=self.top_k
        )
        
        # 4. Convert ScoredPoints back to LangChain Documents
        docs = []
        for point in res.points:
            docs.append(Document(
                page_content=point.payload.get("text", ""),
                metadata={
                    "page": point.payload.get("page", 1) - 1, # 0-indexed in LangChain
                    "section": point.payload.get("section", "Main Body"),
                    "author": point.payload.get("author", "Unknown"),
                    "year": point.payload.get("year", 0),
                    "document_id": point.payload.get("document_id")
                }
            ))
        return docs

def format_docs(docs) -> str:
    """
    Utility to format LangChain Document contents as a context string.
    Includes Paper Name, Page Number, and Section Name inside chunk headers.
    """
    formatted = []
    for doc in docs:
        paper = doc.metadata.get("paper", "Research Paper")
        page = doc.metadata.get("page", 0) + 1  # Convert back to 1-indexed
        section = doc.metadata.get("section", "Main Body")
        formatted.append(
            f"[Source Document: {paper}, Page: {page}, Section: {section}]\n{doc.page_content}"
        )
    return "\n\n".join(formatted)


def get_rag_chain(document_id: str, top_k: int = 4) -> Tuple[Any, Any]:
    """
    Constructs the complete RAG LCEL Chain:
    Retriever | Prompt | LLM | Parser
    
    Returns:
        Tuple[Any, Any]: (lcel_chain, retriever_instance)
    """
    q_client = get_qdrant_client()
    embeddings = get_embeddings()
    prompt = get_rag_prompt()
    
    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        groq_api_key=settings.GROQ_API_KEY,
        temperature=0.0
    )
    
    retriever = HybridRetriever(
        client=q_client,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        embeddings=embeddings,
        document_id=document_id,
        top_k=top_k
    )



    
    # LCEL pipeline definition
    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return chain, retriever

