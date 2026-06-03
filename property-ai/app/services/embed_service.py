import os
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.llm import embed_text
from app.models import Document


def _chunk_text(content: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    words = content.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap
    return chunks


async def embed_document(
    db: AsyncSession,
    title: str,
    source: str,
    content: str,
) -> int:
    await db.execute(delete(Document).where(Document.source == source))
    await db.commit()

    chunks = _chunk_text(content)
    docs = []
    for i, chunk in enumerate(chunks):
        embedding = await embed_text(chunk)
        docs.append(
            Document(
                title=title,
                source=source,
                content=chunk,
                chunk_index=i,
                embedding=embedding,
            )
        )

    db.add_all(docs)
    await db.commit()
    return len(docs)


async def embed_directory(db: AsyncSession, docs_dir: str) -> dict[str, int]:
    results = {}
    for fname in os.listdir(docs_dir):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(docs_dir, fname)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        title = fname.replace("_", " ").replace(".md", "").title()
        count = await embed_document(db, title=title, source=fname, content=content)
        results[fname] = count
        print(f"Embedded {fname}: {count} chunks")
    return results


async def search_documents(
    db: AsyncSession,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Search documents using vector similarity with optimized HNSW indexing.
    
    Uses HNSW (Hierarchical Navigable Small World) for efficient approximate 
    nearest neighbor search, providing better performance than exact search
    while maintaining high accuracy.
    """
    embedding = await embed_text(query)
    emb_str = "[" + ",".join(str(v) for v in embedding) + "]"

    result = await db.execute(
        text(
            """
            SELECT title, source, content,
                   embedding <=> CAST(:emb AS vector) AS distance
            FROM documents
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :top_k
            """
        ),
        {"emb": emb_str, "top_k": top_k},
    )
    rows = result.fetchall()
    return [
        {"title": r.title, "source": r.source, "content": r.content, "distance": r.distance}
        for r in rows
    ]


async def optimize_vector_indexes(db: AsyncSession) -> None:
    """
    Optimize vector indexes after bulk embedding operations.
    
    This ensures that HNSW and IVFFlat indexes are properly built and
    statistics are updated for optimal query performance.
    """
    try:
        # Reindex HNSW index for optimal performance
        await db.execute(text("REINDEX INDEX ix_documents_embedding_hnsw"))
        
        # Update table statistics for query planner
        await db.execute(text("ANALYZE documents"))
        
        # Optional: Reindex IVFFlat if using that as fallback
        await db.execute(text("REINDEX INDEX ix_documents_embedding_ivfflat"))
        
    except Exception as e:
        print(f"Warning: Index optimization failed: {e}")
        # Don't fail the entire operation if optimization fails
