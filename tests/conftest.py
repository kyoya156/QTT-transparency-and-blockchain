import json
import os
import sys
import pathlib

os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from pgvector.sqlalchemy import Vector

compiles(Vector, "sqlite")(lambda t, c, **k: "TEXT")   # SQLite khong co vector: chi de test logic

# The Vector type validates EMBED_DIM on bind, which rejects the 2-dimension
# vectors the tests use as markers. On SQLite there is no vector type at all,
# so store the list as JSON and hand Postgres its normal processors.
_vector_bind = Vector.bind_processor
_vector_result = Vector.result_processor


def _sqlite_bind(self, dialect):
    if dialect.name != "sqlite":
        return _vector_bind(self, dialect)
    return lambda value: None if value is None else json.dumps([float(v) for v in value])


def _sqlite_result(self, dialect, coltype):
    if dialect.name != "sqlite":
        return _vector_result(self, dialect, coltype)
    return lambda value: None if value is None else json.loads(value)


Vector.bind_processor = _sqlite_bind
Vector.result_processor = _sqlite_result

from app.db import Base  # noqa: E402
from app import models  # noqa: E402,F401


@pytest.fixture()
def db():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng, expire_on_commit=False)()
    yield s
    s.close()
