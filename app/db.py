from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url or "sqlite://", pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope():
    """Phien lam viec tu commit/rollback (dung ngoai FastAPI)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def user_scope(user):
    """Phien lam viec CHAN theo quyen cua nguoi dung (RLS tren Postgres).

    Vai tro chatbot_app khong phai chu bang nen chinh sach RLS ap dung; SET LOCAL chi co hieu luc
    trong giao dich nay nen khong ro ri sang ket noi khac trong pool. Danh tinh lay tu phien dang nhap,
    khong bao gio tu noi dung request.
    """
    db = SessionLocal()
    try:
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SET LOCAL ROLE chatbot_app"))
            db.execute(text("SELECT set_config('app.is_admin', :a, true), set_config('app.depts', :d, true), "
                            "set_config('app.user_id', :u, true)"),
                       {"a": "on" if user.department == "admin" else "off", "d": user.department,
                        "u": str(user.id)})
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
