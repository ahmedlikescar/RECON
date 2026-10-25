from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import JSON, ForeignKey, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now() -> str:
    return datetime.now(UTC).isoformat()


class Base(DeclarativeBase):
    pass


class Binary(Base):
    __tablename__ = "binaries"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    filename: Mapped[str]
    size: Mapped[int]
    status: Mapped[str] = mapped_column(default="queued")
    artifact_path: Mapped[str | None]
    artifact_hash: Mapped[str | None]
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    imported_at: Mapped[str] = mapped_column(default=now)


class Function(Base):
    __tablename__ = "functions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    binary_id: Mapped[str] = mapped_column(
        ForeignKey("binaries.id", ondelete="CASCADE"), index=True
    )
    address: Mapped[int]
    end_address: Mapped[int]
    name: Mapped[str] = mapped_column(index=True)
    discovery_method: Mapped[str]
    confidence: Mapped[float]
    instruction_count: Mapped[int]
    block_count: Mapped[int]
    artifact_index: Mapped[int]


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str]
    resource_id: Mapped[str]
    state: Mapped[str] = mapped_column(default="queued", index=True)
    progress: Mapped[float] = mapped_column(default=0)
    phase: Mapped[str] = mapped_column(default="queued")
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    error_code: Mapped[str | None]
    error: Mapped[str | None]
    created_at: Mapped[str] = mapped_column(default=now)
    finished_at: Mapped[str | None]
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Comparison(Base):
    __tablename__ = "comparisons"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_binary_id: Mapped[str] = mapped_column(ForeignKey("binaries.id", ondelete="CASCADE"))
    target_binary_id: Mapped[str] = mapped_column(ForeignKey("binaries.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(default="queued")
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    artifact_path: Mapped[str | None]
    artifact_hash: Mapped[str | None]
    created_at: Mapped[str] = mapped_column(default=now)


class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str]
    status: Mapped[str] = mapped_column(default="queued")
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    artifact_path: Mapped[str | None]
    artifact_hash: Mapped[str | None]
    created_at: Mapped[str] = mapped_column(default=now)


def database(root: Path) -> sessionmaker:
    root.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{root / 'recon.sqlite3'}",
        connect_args={"check_same_thread": False, "timeout": 15},
    )

    @event.listens_for(engine, "connect")
    def pragmas(connection: Any, _: Any) -> None:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=15000")

    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")
    return sessionmaker(engine, expire_on_commit=False)


def record(row: Base) -> dict[str, Any]:
    return {col.name: getattr(row, col.name) for col in row.__table__.columns}
