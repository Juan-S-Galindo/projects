import os
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def _build_url() -> str:
    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    user = os.environ.get("PGUSER", "postgres")
    password = os.environ.get("PGPASSWORD", "")
    database = os.environ.get("PGDATABASE", "expenses")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


@st.cache_resource
def get_engine():
    from src.db.schema import init_schema
    engine = create_engine(_build_url(), pool_pre_ping=True)
    init_schema(engine)
    return engine


def get_session():
    Session = sessionmaker(bind=get_engine())
    return Session()


def execute(sql: str, params: dict | None = None):
    with get_engine().connect() as conn:
        result = conn.execute(text(sql), params or {})
        conn.commit()
        return result
