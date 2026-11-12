import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import access, models
from ..auth import current_user
from ..db import get_db, user_scope
from ..rag.embeddings import EmbedderError, get_embedder
from ..rag.retrieve import retrieve

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    k: int = Field(default=6, ge=1, le=20)


@router.post("/search")
def search(body: SearchIn, user=Depends(current_user), owner_db: Session = Depends(get_db)):
    """Tim trong kho tri thuc. Chi tra ve chunk ma phong ban cua nguoi dung duoc phep (chan o muc DB)."""
    if not access.can_use_tool(owner_db, user, "search_knowledge"):
        access.audit(owner_db, user, "tool_denied", detail={"tool": "search_knowledge"})
        owner_db.commit()
        raise HTTPException(403, "your department may not use this tool")
    with user_scope(user) as db:
        # Chi dung vector khi da co chunk duoc embed; neu thieu thu vien embedding thi chi tim tu khoa.
        use_vector = db.query(models.Chunk.id).filter(models.Chunk.embedding.is_not(None)).first() is not None
        embedding = None
        if use_vector:
            try:
                embedding = get_embedder().embed_query(body.query)
            except EmbedderError as e:
                log.warning("vector search off: %s", e)
        result = retrieve(body.query, session=db, k=body.k, query_embedding=embedding, use_vector=embedding is not None)
        access.audit(db, user, "search", query=body.query, chunk_ids=[c.chunk.id for c in result.chunks])
        return result.as_dict()
