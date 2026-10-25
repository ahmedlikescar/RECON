from typing import Any

from pydantic import BaseModel

from recon.schemas import FunctionAnalysis


class BinaryView(BaseModel):
    id: str
    filename: str
    sha256: str
    size: int
    status: str
    metadata_json: dict[str, Any]
    imported_at: str


class JobView(BaseModel):
    id: str
    kind: str
    resource_id: str
    state: str
    progress: float
    phase: str
    cancel_requested: bool
    error_code: str | None
    error: str | None
    created_at: str
    finished_at: str | None


class ImportView(BaseModel):
    binary: BinaryView
    job_id: str | None
    cached: bool


class FunctionView(FunctionAnalysis):
    id: str
    binary_id: str


class FunctionSummary(BaseModel):
    id: str
    binary_id: str
    address: int
    end_address: int
    name: str
    discovery_method: str
    confidence: float
    instruction_count: int
    block_count: int


class Page[T](BaseModel):
    items: list[T]
    total: int
    offset: int
    limit: int


class ComparisonView(BaseModel):
    id: str
    source_binary_id: str
    target_binary_id: str
    status: str
    config_json: dict[str, Any]
    created_at: str
    result: dict[str, Any] | None = None


class ComparisonCreated(BaseModel):
    comparison: ComparisonView
    job_id: str


class ExperimentView(BaseModel):
    id: str
    kind: str
    status: str
    config_json: dict[str, Any]
    created_at: str
    result: dict[str, Any] | None = None
