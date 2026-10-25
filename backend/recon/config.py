from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RECON_")

    data_dir: Path = Path(".recon")
    max_upload_bytes: int = Field(default=32 * 1024 * 1024, ge=1024, le=256 * 1024 * 1024)
    max_storage_bytes: int = Field(default=1024 * 1024 * 1024, ge=1024)
    worker_timeout: int = Field(default=45, ge=1, le=600)
    worker_memory_mb: int = Field(default=1024, ge=128, le=8192)
    max_functions: int = Field(default=5000, ge=1, le=20000)
    max_function_bytes: int = Field(default=65536, ge=64, le=1048576)
    max_instructions: int = Field(default=200000, ge=100, le=1000000)
    max_queued_jobs: int = Field(default=20, ge=1, le=100)
    rea_enabled: bool = False
    rea_command: Path | None = None
    ghidra_path: Path | None = None
    provider_timeout: int = Field(default=60, ge=1, le=300)

    @property
    def root(self) -> Path:
        return self.data_dir.expanduser().resolve()


REPO_ROOT = Path(__file__).resolve().parents[2]
