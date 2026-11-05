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

from app.db import Base  # noqa: E402
from app import models  # noqa: E402,F401


@pytest.fixture()
def db():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng, expire_on_commit=False)()
    yield s
    s.close()
