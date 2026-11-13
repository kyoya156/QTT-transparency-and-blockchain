import httpx
import pytest

from app import models
from app.sync.crawler_client import CrawlerError, fetch_all
from app.sync.sync_chunks import reconcile, run_sync


def item(i, text="noi dung", st="web", **meta):
    return {"id": i, "source_type": st, "source_id": f"s{i}", "content": text, "metadata": meta}


def test_insert_then_idempotent(db):
    items = [item(1, url="https://x/a", title="A", part=1), item(2, st="post", published_at="2026-10-01T08:00:00")]
    assert reconcile(db, items) == {"fetched": 2, "inserted": 2, "updated": 0, "deleted": 0, "rejected": 0}
    again = reconcile(db, items)
    assert again["inserted"] == 0 and again["updated"] == 0 and again["deleted"] == 0
    assert db.query(models.Chunk).count() == 2
    assert db.query(models.Chunk).filter_by(src_id=2).one().source_date.year == 2026


def test_changed_content_clears_embedding(db):
    reconcile(db, [item(1, "cu")])
    c = db.query(models.Chunk).one()
    c.embedding, c.embed_model = [0.1, 0.2], "m"
    db.commit()
    assert reconcile(db, [item(1, "moi")])["updated"] == 1
    c = db.query(models.Chunk).one()
    assert c.content == "moi" and c.embedding is None and c.embed_model is None


def test_metadata_only_change_keeps_embedding(db):
    reconcile(db, [item(1, "a", url="https://x/1")])
    c = db.query(models.Chunk).one()
    c.embedding = [0.1, 0.2]
    db.commit()
    r = reconcile(db, [item(1, "a", url="https://x/2")])
    assert r["updated"] == 0
    c = db.query(models.Chunk).one()
    assert c.url == "https://x/2" and c.embedding is not None


def test_deletes_chunks_crawler_dropped(db):
    reconcile(db, [item(i) for i in range(1, 5)])
    assert reconcile(db, [item(i) for i in range(1, 4)])["deleted"] == 1


def test_refuses_mass_delete_and_empty(db):
    reconcile(db, [item(i) for i in range(1, 5)])
    with pytest.raises(CrawlerError):
        reconcile(db, [item(1)])                 # xoa 3/4 > 50%
    assert db.query(models.Chunk).count() == 4   # rollback, khong mat gi
    with pytest.raises(CrawlerError):
        reconcile(db, [])                        # rong trong khi da co du lieu
    assert db.query(models.Chunk).count() == 4
    assert reconcile(db, [], allow_empty=True)["deleted"] == 4


def test_rejects_non_public_types_and_empty_text(db):
    r = reconcile(db, [item(1, st="message"), item(2, "   "), item(3, st="comment"), item(4)])
    assert r["inserted"] == 1 and r["rejected"] == 3
    assert db.query(models.Chunk).one().source_type == "web"


def _transport(pages, status=200, seen=None):
    def handler(req: httpx.Request):
        if seen is not None:
            seen.append(dict(req.url.params))
        if status != 200:
            return httpx.Response(status, text="x")
        after = int(req.url.params["after_id"])
        return httpx.Response(200, json=pages[after])
    return httpx.MockTransport(handler)


def test_fetch_all_paginates_and_sends_key_and_types():
    seen = []
    pages = {0: {"items": [item(1), item(2)], "next_after_id": 2},
             2: {"items": [item(3)], "next_after_id": None}}
    got = fetch_all("http://c", "k", 2, transport=_transport(pages, seen=seen))
    assert [i["id"] for i in got] == [1, 2, 3]
    assert seen[0]["after_id"] == "0" and seen[1]["after_id"] == "2"


@pytest.mark.parametrize("status,word", [(401, "401"), (503, "PUBLIC_API_KEY"), (500, "500")])
def test_fetch_errors_are_explicit(status, word):
    with pytest.raises(CrawlerError, match=word):
        fetch_all("http://c", "k", transport=_transport({}, status=status))


def test_fetch_requires_key():
    with pytest.raises(CrawlerError, match="CRAWLER_API_KEY"):
        fetch_all("http://c", "")


def test_run_sync_records_run_and_error(db):
    pages = {0: {"items": [item(1)], "next_after_id": None}}
    assert run_sync(db, base_url="http://c", api_key="k", transport=_transport(pages))["inserted"] == 1
    run = db.query(models.SyncRun).one()
    assert run.inserted == 1 and run.error is None and run.finished_at is not None
    with pytest.raises(CrawlerError):
        run_sync(db, base_url="http://c", api_key="k", transport=_transport({}, status=500))
    last = db.query(models.SyncRun).order_by(models.SyncRun.id.desc()).first()
    assert "500" in last.error
    assert db.query(models.Chunk).count() == 1      # loi khong lam mat du lieu
