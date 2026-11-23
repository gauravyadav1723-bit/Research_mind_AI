import socket
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from app.config.settings import settings
from app.models.chunk import DocumentChunk
from app.rag.embeddings.google import get_embeddings

def object_id_to_uuid(object_id: str) -> str:
    """
    Deterministically converts a 24-character MongoDB ObjectId hex string 
    into a valid 128-bit UUID string formatted for Qdrant.
    """
    hex_str = object_id.zfill(32)
    return f"{hex_str[:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:]}"

_qdrant_client_instance = None

def get_qdrant_client() -> QdrantClient:
    """
    Returns a cached QdrantClient. If the local Qdrant server is not running on port 6333,
    it automatically falls back to a shared in-memory client for dev/test ease.
    """
    global _qdrant_client_instance
    if _qdrant_client_instance is None:
        if not settings.QDRANT_URL or "localhost" in settings.QDRANT_URL or "127.0.0.1" in settings.QDRANT_URL:
            # Check if port 6333 is open
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1.0)
                s.connect(("127.0.0.1", 6333))
                s.close()
                _qdrant_client_instance = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
            except Exception:
                print("Local Qdrant server not detected on port 6333. Falling back to shared in-memory vector database.")
                _qdrant_client_instance = QdrantClient(location=":memory:")
        else:
            _qdrant_client_instance = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    return _qdrant_client_instance


async def index_chunks(chunks: List[DocumentChunk], document_id: str):
    """
    Embeds document chunks using Google Generative AI and indexes them in Qdrant.
    """
    if not chunks:
        return

    client = get_qdrant_client()
    
    # 1. Ensure collection exists
    try:
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
    except Exception as e:
        # If Qdrant connection fails completely, fallback to in-memory client
        print(f"Failed to fetch collections from remote Qdrant ({e}). Using in-memory fallback.")
        client = QdrantClient(location=":memory:")
        collection_names = []

    recreate = False
    if settings.QDRANT_COLLECTION_NAME in collection_names:
        try:
            col_info = client.get_collection(settings.QDRANT_COLLECTION_NAME)
            # Support both single vector config and named vectors config
            current_size = col_info.config.params.vectors.size if hasattr(col_info.config.params.vectors, 'size') else 3072
            if current_size != 3072:
                recreate = True
        except Exception:
            pass
            
    if recreate:
        try:
            client.delete_collection(settings.QDRANT_COLLECTION_NAME)
            if settings.QDRANT_COLLECTION_NAME in collection_names:
                collection_names.remove(settings.QDRANT_COLLECTION_NAME)
        except Exception:
            pass

    if settings.QDRANT_COLLECTION_NAME not in collection_names:
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            vectors_config=VectorParams(size=3072, distance=Distance.COSINE)
        )


    # 2. Batch embed text chunks with a rate-limit friendly delay
    embeddings_model = get_embeddings()
    texts = [chunk.text for chunk in chunks]
    
    batch_size = 5
    vectors = []
    import time
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        batch_vectors = embeddings_model.embed_documents(batch_texts)
        vectors.extend(batch_vectors)
        if i + batch_size < len(texts):
            time.sleep(1.2)  # 1.2s delay between batches to stay under free tier RPM limits


    # 3. Formulate points and upsert
    points = []
    for i, chunk in enumerate(chunks):
        qdrant_id = object_id_to_uuid(str(chunk.id))
        points.append(
            PointStruct(
                id=qdrant_id,
                vector=vectors[i],
                payload={
                    "document_id": str(chunk.document_id),
                    "page": chunk.page,
                    "section": chunk.section or "Main Body",
                    "author": chunk.author or "Unknown",
                    "year": chunk.year or 0,
                    "text": chunk.text
                }
            )
        )

    # Clean up any existing vectors for this document to avoid duplicates
    await delete_document_vectors(document_id, client)

    client.upsert(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        points=points
    )

async def delete_document_vectors(document_id: str, client: Optional[QdrantClient] = None):
    """
    Removes all indexed vector points associated with the given document_id.
    """
    if client is None:
        client = get_qdrant_client()
        
    try:
        # Check if collection exists
        collections = client.get_collections().collections
        if settings.QDRANT_COLLECTION_NAME not in [c.name for c in collections]:
            return
            
        client.delete(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id)
                    )
                ]
            )
        )
    except Exception as e:
        print(f"Error deleting vectors from Qdrant: {str(e)}")
