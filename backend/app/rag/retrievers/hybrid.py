import asyncio
from typing import List, Any
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.http import models

class HybridRetriever(BaseRetriever):
    client: Any
    collection_name: str
    embeddings: Any
    document_id: str
    top_k: int = 4
    llm: Any = None

    def _get_relevant_documents(self, query: str, *, run_manager: Any = None) -> List[Document]:
        """
        Synchronous retriever fallback.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(self._aget_relevant_documents(query, run_manager=run_manager))
        else:
            return asyncio.run(self._aget_relevant_documents(query, run_manager=run_manager))

    async def _aget_relevant_documents(self, query: str, *, run_manager: Any = None) -> List[Document]:
        """
        Asynchronous retrieval pipeline:
        BM25 + Semantic Search -> Reciprocal Rank Fusion (RRF) -> Top K.
        """
        # 1. Fetch all document chunks from MongoDB
        from app.models.chunk import DocumentChunk
        from app.models.document import ResearchDocument
        from beanie import PydanticObjectId

        db_chunks = await DocumentChunk.find(
            DocumentChunk.document_id == PydanticObjectId(self.document_id)
        ).to_list()

        if not db_chunks:
            return []

        doc_record = await ResearchDocument.get(PydanticObjectId(self.document_id))
        paper_title = doc_record.filename if doc_record else "Research Paper"

        # Convert to LangChain Documents
        lc_docs = []
        for c in db_chunks:
            lc_docs.append(Document(
                page_content=c.text,
                metadata={
                    "page": c.page - 1,  # 0-indexed in LangChain
                    "section": c.section or "Main Body",
                    "author": c.author or "Unknown",
                    "year": c.year or 0,
                    "document_id": str(c.document_id),
                    "chunk_id": str(c.id),
                    "paper": paper_title
                }
            ))


        # 2. BM25 Search
        # Dynamic fitting of BM25 retriever on this specific paper's chunks
        from langchain_community.retrievers import BM25Retriever
        bm25_retriever = BM25Retriever.from_documents(lc_docs)
        
        k_candidates = min(len(lc_docs), self.top_k * 2)
        bm25_retriever.k = k_candidates
        bm25_results = bm25_retriever.invoke(query)

        # 3. Qdrant Semantic Vector Search
        query_vector = self.embeddings.embed_query(query)
        filter_cond = models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=self.document_id)
                )
            ]
        )

        q_res = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=filter_cond,
            limit=k_candidates
        )

        vector_results = []
        for point in q_res.points:
            vector_results.append(Document(
                page_content=point.payload.get("text", ""),
                metadata={
                    "page": point.payload.get("page", 1) - 1,
                    "section": point.payload.get("section", "Main Body"),
                    "author": point.payload.get("author", "Unknown"),
                    "year": point.payload.get("year", 0),
                    "document_id": point.payload.get("document_id"),
                    "chunk_id": point.payload.get("chunk_id") or str(point.id),
                    "paper": paper_title
                }
            ))


        # 4. Fusion via Reciprocal Rank Fusion (RRF)
        # Score = Sum ( 1 / (60 + Rank_in_retriever) )
        rrf_scores = {}
        
        def add_rrf_rankings(results):
            for rank, doc in enumerate(results):
                chunk_id = doc.metadata.get("chunk_id")
                key = chunk_id or doc.page_content
                
                if key not in rrf_scores:
                    rrf_scores[key] = (doc, 0.0)
                
                doc_obj, current_score = rrf_scores[key]
                rrf_scores[key] = (doc_obj, current_score + (1.0 / (60.0 + rank + 1)))

        add_rrf_rankings(bm25_results)
        add_rrf_rankings(vector_results)

        sorted_candidates = sorted(rrf_scores.values(), key=lambda item: item[1], reverse=True)
        top_candidates = [item[0] for item in sorted_candidates[:self.top_k]]
        return top_candidates

# Backwards compatibility alias
HybridRetrieverWithReranking = HybridRetriever
