import datetime

from app import models
from app.rag import citations
from app.rag.answer import answer
from app.rag.compose import ExtractiveClient, build_user_prompt
from app.rag.retrieve import RetrievalResult, RetrievedChunk


def result():
    chunk = models.Chunk(
        id=7, src_id=7, source_type="web", source_id="page:hoc-bong",
        content="Học bổng được giải ngân hai lần mỗi năm. Mức hỗ trợ được công bố công khai. Trẻ em được chọn theo hồ sơ.",
        content_hash="h", title="Học bổng", url="https://quynuoiem.com/hoc-bong",
        source_date=datetime.date(2026, 10, 18), crawled_at=datetime.datetime(2026, 11, 1),
    )
    return RetrievalResult(query="q", chunks=[RetrievedChunk(chunk=chunk, vector_similarity=0.8)],
                           best_similarity=0.8, used_vector=True)


def test_extractive_fallback_quotes_and_cites_evidence():
    r = result()
    client = ExtractiveClient()
    text = client.complete("system", build_user_prompt("Học bổng?", r))
    assert text.startswith("Theo dữ liệu hiện có:")
    assert "[7]" in text
    ok, why = citations.check(text, {"7"})
    assert ok, why


def test_answer_marks_extractive_mode():
    a = answer("Học bổng?", lambda _q: result(), ExtractiveClient())
    assert a.status == "answered"
    assert a.mode == "extractive"
    assert a.citations[0]["chunk_id"] == "7"
