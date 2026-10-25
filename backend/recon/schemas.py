from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from recon import ANALYZER_VERSION, FEATURE_SCHEMA


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Instruction(StrictModel):
    address: int
    size: int
    mnemonic: str
    operands: str
    token: str
    bytes_hex: str
    branch_target: int | None = None
    flow: Literal["next", "conditional", "jump", "return", "call", "stop"] = "next"


class Block(StrictModel):
    id: str
    start_address: int
    end_address: int
    instruction_addresses: list[int]


class Edge(StrictModel):
    source: str
    target: str
    kind: Literal["branch", "fallthrough"]


class CFG(StrictModel):
    blocks: list[Block] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    unresolved_branches: list[int] = Field(default_factory=list)
    statistics: dict[str, float] = Field(default_factory=dict)


class FunctionAnalysis(StrictModel):
    address: int
    end_address: int
    name: str
    discovery_method: str
    confidence: float
    bytes_hash: str
    instructions: list[Instruction]
    cfg: CFG
    limitations: list[str] = Field(default_factory=list)
    feature_schema: str = FEATURE_SCHEMA


class Analysis(StrictModel):
    analyzer_version: str = ANALYZER_VERSION
    feature_schema: str = FEATURE_SCHEMA
    sha256: str
    format: str = "ELF"
    architecture: str = "x86-64"
    bitness: int = 64
    entry_point: int
    sections: list[dict[str, str | int | bool]]
    imports: list[str]
    functions: list[FunctionAnalysis]
    limitations: list[str]
    duration_seconds: float
    tool_versions: dict[str, str]


class ComparisonRequest(StrictModel):
    source_binary_id: str
    target_binary_id: str
    query_function_id: str | None = None
    method: Literal["opcode", "ngram", "structure", "hybrid", "neural"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=50)
    threshold: float = Field(default=0.65, ge=0, le=1)


class TrainingRequest(StrictModel):
    epochs: int = Field(default=30, ge=1, le=200)
    seed: int = Field(default=42, ge=0, le=2147483647)
    resume: bool = False


class InvestigationRequest(StrictModel):
    consent: bool = False
