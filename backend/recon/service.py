import logging
import shutil
import threading
import time
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from recon import ANALYZER_VERSION, FEATURE_SCHEMA
from recon.config import Settings
from recon.errors import ReconError
from recon.features.baselines import BaselineIndex
from recon.indexing.exact import rank_queries
from recon.schemas import Analysis, ComparisonRequest, FunctionAnalysis
from recon.security.process import run_analysis
from recon.security.validation import inside, safe_filename, safe_id, validate_elf
from recon.storage.artifacts import atomic_bytes, atomic_json, digest, read_json
from recon.storage.database import (
    Binary,
    Comparison,
    Experiment,
    Function,
    Job,
    database,
    now,
    record,
)

log = logging.getLogger("recon.jobs")


def identifier() -> str:
    return uuid.uuid4().hex


class Service:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.root
        self.sessions: sessionmaker = database(self.root)
        self.stop_event = threading.Event()
        self.wake = threading.Event()
        self.lock = threading.RLock()
        self.thread: threading.Thread | None = None
        self.index_cache: dict[str, BaselineIndex] = {}
        with self.sessions.begin() as db:
            for job in db.scalars(select(Job).where(Job.state == "running")):
                job.state, job.phase, job.error_code = "failed", "interrupted", "INTERRUPTED"
                job.error, job.finished_at = (
                    "The service restarted during this task. Retry explicitly.",
                    now(),
                )
                self.set_resource_status(db, job, "failed")
        for path in self.root.glob("worker-*"):
            if path.is_dir():
                shutil.rmtree(path)

    def start(self) -> None:
        self.thread = threading.Thread(target=self.worker_loop, daemon=True, name="recon-queue")
        self.thread.start()

    def close(self) -> None:
        self.stop_event.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=self.settings.worker_timeout + 5)
        self.sessions.kw["bind"].dispose()

    def get(self, cls: Any, value: str) -> dict[str, Any]:
        safe_id(value)
        with self.sessions() as db:
            row = db.get(cls, value)
            if row is None:
                raise ReconError("NOT_FOUND", "Record not found.", 404)
            return record(row)

    def check_queue(self) -> None:
        with self.sessions() as db:
            jobs = db.scalars(select(Job.id).where(Job.state.in_(["queued", "running"]))).all()
            if len(jobs) >= self.settings.max_queued_jobs:
                raise ReconError(
                    "QUEUE_FULL", "The local job queue is full. Wait for a task to finish.", 409
                )

    def storage_budget(self, incoming: int = 0) -> None:
        used = sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file())
        if used + incoming > self.settings.max_storage_bytes:
            raise ReconError(
                "STORAGE_LIMIT",
                "Local storage budget reached. Delete unneeded binaries or increase RECON_MAX_STORAGE_BYTES.",
                413,
            )

    def import_binary(self, data: bytes, filename: str | None) -> dict[str, Any]:
        filename = safe_filename(filename)
        validate_elf(data, self.settings.max_upload_bytes)
        sha = digest(data)
        with self.lock, self.sessions.begin() as db:
            existing = db.scalar(select(Binary).where(Binary.sha256 == sha))
            if existing:
                job = db.scalar(
                    select(Job)
                    .where(Job.resource_id == existing.id)
                    .order_by(Job.created_at.desc())
                )
                compatible = existing.metadata_json.get("analyzer_version") == ANALYZER_VERSION
                if existing.status == "completed" and not compatible:
                    raise ReconError(
                        "CACHE_INCOMPATIBLE",
                        "Stored analysis uses a different analyzer. Reanalyze the binary.",
                        409,
                    )
                return {
                    "binary": record(existing),
                    "job_id": job.id if job else None,
                    "cached": existing.status == "completed",
                }
            self.check_queue()
            self.storage_budget(len(data))
            binary_id, job_id = identifier(), identifier()
            atomic_bytes(self.root / "binaries" / sha, data)
            binary = Binary(id=binary_id, sha256=sha, filename=filename, size=len(data))
            job = Job(id=job_id, kind="analysis", resource_id=binary_id)
            db.add_all([binary, job])
            db.flush()
            result = {"binary": record(binary), "job_id": job_id, "cached": False}
        self.wake.set()
        return result

    def reanalyze(self, binary_id: str) -> dict[str, Any]:
        self.get(Binary, binary_id)
        with self.lock, self.sessions.begin() as db:
            if db.scalar(
                select(Job).where(
                    Job.resource_id == binary_id, Job.state.in_(["queued", "running"])
                )
            ):
                raise ReconError(
                    "JOB_ACTIVE", "This binary already has an active analysis task.", 409
                )
            self.check_queue()
            job = Job(id=identifier(), kind="analysis", resource_id=binary_id)
            db.add(job)
            db.get(Binary, binary_id).status = "queued"
            db.flush()
            result = record(job)
        self.wake.set()
        return result

    def analysis(self, binary_id: str) -> Analysis:
        binary = self.get(Binary, binary_id)
        if binary["status"] != "completed" or not binary["artifact_path"]:
            raise ReconError(
                "ANALYSIS_NOT_READY", "Wait for this binary's analysis to complete.", 409
            )
        result = Analysis.model_validate(
            read_json(inside(self.root, binary["artifact_path"]), binary["artifact_hash"])
        )
        if result.analyzer_version != ANALYZER_VERSION or result.feature_schema != FEATURE_SCHEMA:
            raise ReconError(
                "CACHE_INCOMPATIBLE", "Reanalyze this binary with the current analyzer.", 409
            )
        if digest((self.root / "binaries" / binary["sha256"]).read_bytes()) != binary["sha256"]:
            raise ReconError(
                "BINARY_INTEGRITY",
                "The stored binary was changed. Delete and import it again.",
                409,
            )
        return result

    def function(self, function_id: str) -> tuple[dict[str, Any], FunctionAnalysis]:
        row = self.get(Function, function_id)
        analysis = self.analysis(row["binary_id"])
        return row, analysis.functions[row["artifact_index"]]

    def functions(self, binary_id: str) -> list[tuple[str, FunctionAnalysis]]:
        analysis = self.analysis(binary_id)
        with self.sessions() as db:
            rows = db.scalars(
                select(Function)
                .where(Function.binary_id == binary_id)
                .order_by(Function.artifact_index)
            ).all()
            return [(r.id, analysis.functions[r.artifact_index]) for r in rows]

    def compare(self, request: ComparisonRequest) -> dict[str, Any]:
        self.analysis(request.source_binary_id)
        self.analysis(request.target_binary_id)
        if request.query_function_id:
            row, _ = self.function(request.query_function_id)
            if row["binary_id"] != request.source_binary_id:
                raise ReconError(
                    "QUERY_SCOPE", "The query function must belong to the source binary."
                )
        if request.method == "neural":
            from recon.ml.model import load_model

            load_model(self.root / "models/current")
        with self.lock, self.sessions.begin() as db:
            self.check_queue()
            item = Comparison(
                id=identifier(),
                source_binary_id=request.source_binary_id,
                target_binary_id=request.target_binary_id,
                config_json=request.model_dump(),
            )
            job = Job(
                id=identifier(),
                kind="comparison",
                resource_id=item.id,
                config_json=request.model_dump(),
            )
            db.add_all([item, job])
            db.flush()
            result = {"comparison": record(item), "job_id": job.id}
        self.wake.set()
        return result

    def cancel(self, job_id: str) -> dict[str, Any]:
        self.get(Job, job_id)
        with self.lock, self.sessions.begin() as db:
            job = db.get(Job, job_id)
            if job.state in {"queued", "running"}:
                job.cancel_requested = True
                if job.state == "queued":
                    job.state, job.phase, job.finished_at = "cancelled", "cancelled", now()
                    self.set_resource_status(db, job, "cancelled")
            db.flush()
            return record(job)

    def is_cancelled(self, job_id: str) -> bool:
        if self.stop_event.is_set():
            return True
        with self.sessions() as db:
            job = db.get(Job, job_id)
            return job is None or job.cancel_requested

    @staticmethod
    def set_resource_status(db: Any, job: Job, state: str) -> None:
        cls = {"analysis": Binary, "comparison": Comparison}.get(job.kind, Experiment)
        resource = db.get(cls, job.resource_id)
        if resource:
            resource.status = state

    def worker_loop(self) -> None:
        while not self.stop_event.is_set():
            with self.lock, self.sessions.begin() as db:
                job = db.scalar(
                    select(Job).where(Job.state == "queued").order_by(Job.created_at).limit(1)
                )
                if job:
                    job.state, job.phase, job.progress = "running", job.kind, 0.1
                    self.set_resource_status(db, job, "running")
                    task = record(job)
                else:
                    task = None
            if task is None:
                self.wake.wait(0.5)
                self.wake.clear()
                continue
            started = time.perf_counter()
            try:
                self.storage_budget()
                if task["kind"] == "analysis":
                    self.perform_analysis(task)
                elif task["kind"] == "comparison":
                    self.perform_comparison(task)
                else:
                    self.perform_experiment(task)
                with self.lock, self.sessions.begin() as db:
                    job = db.get(Job, task["id"])
                    job.state, job.phase, job.progress, job.finished_at = (
                        "completed",
                        "completed",
                        1.0,
                        now(),
                    )
                    self.set_resource_status(db, job, "completed")
            except Exception as exc:
                code = exc.code if isinstance(exc, ReconError) else "TASK_FAILED"
                message = (
                    exc.message
                    if isinstance(exc, ReconError)
                    else "Task failed. Check the local service log for diagnostics."
                )
                if not isinstance(exc, ReconError):
                    log.exception("task_failed job_id=%s kind=%s", task["id"], task["kind"])
                with self.lock, self.sessions.begin() as db:
                    job = db.get(Job, task["id"])
                    job.state = "cancelled" if code == "CANCELLED" else "failed"
                    job.phase, job.error_code, job.error, job.finished_at = (
                        job.state,
                        code,
                        message,
                        now(),
                    )
                    self.set_resource_status(db, job, job.state)
            log.info(
                "task_finished job_id=%s kind=%s elapsed=%.3f",
                task["id"],
                task["kind"],
                time.perf_counter() - started,
            )

    def perform_analysis(self, task: dict[str, Any]) -> None:
        binary = self.get(Binary, task["resource_id"])
        source = self.root / "binaries" / binary["sha256"]
        if digest(source.read_bytes()) != binary["sha256"]:
            raise ReconError("BINARY_INTEGRITY", "The stored binary hash changed.", 409)
        result = run_analysis(source, self.settings, lambda: self.is_cancelled(task["id"]))
        self.storage_budget(len(result.model_dump_json().encode()))
        artifact = f"analysis/{binary['id']}.json"
        artifact_hash = atomic_json(self.root / artifact, result.model_dump())
        with self.lock, self.sessions.begin() as db:
            if self.is_cancelled(task["id"]):
                (self.root / artifact).unlink(missing_ok=True)
                raise ReconError("CANCELLED", "Analysis cancelled.", 409)
            db.execute(delete(Function).where(Function.binary_id == binary["id"]))
            for pos, function in enumerate(result.functions):
                db.add(
                    Function(
                        id=identifier(),
                        binary_id=binary["id"],
                        address=function.address,
                        end_address=function.end_address,
                        name=function.name,
                        discovery_method=function.discovery_method,
                        confidence=function.confidence,
                        instruction_count=len(function.instructions),
                        block_count=len(function.cfg.blocks),
                        artifact_index=pos,
                    )
                )
            row = db.get(Binary, binary["id"])
            row.artifact_path, row.artifact_hash = artifact, artifact_hash
            row.metadata_json = {
                **result.model_dump(exclude={"functions"}),
                "function_count": len(result.functions),
            }
        self.index_cache.pop(binary["id"], None)

    def perform_comparison(self, task: dict[str, Any]) -> None:
        request = ComparisonRequest.model_validate(task["config_json"])
        queries, targets = (
            self.functions(request.source_binary_id),
            self.functions(request.target_binary_id),
        )
        if request.query_function_id:
            queries = [p for p in queries if p[0] == request.query_function_id]
        if request.method == "neural":
            from recon.ml.model import neural_rank

            result = neural_rank(
                queries, targets, self.root / "models/current", request.top_k, request.threshold
            )
        else:
            index = self.index_cache.get(request.target_binary_id)
            if index is None:
                path = self.root / "indexes" / f"{request.target_binary_id}.json"
                manifest_path = path.with_suffix(".sha256")
                if path.exists() and manifest_path.exists():
                    index = BaselineIndex.restore(
                        [f for _, f in targets], read_json(path, manifest_path.read_text())
                    )
                else:
                    index = BaselineIndex([f for _, f in targets])
                    sha = atomic_json(path, index.manifest())
                    atomic_bytes(manifest_path, sha.encode())
                self.index_cache = {request.target_binary_id: index}
            result = rank_queries(
                queries, targets, index, request.method, request.top_k, request.threshold
            )
        if self.is_cancelled(task["id"]):
            raise ReconError("CANCELLED", "Comparison cancelled.", 409)
        result.update(
            {
                "comparison_id": task["resource_id"],
                "created_at": now(),
                "source_binary": self.get(Binary, request.source_binary_id),
                "target_binary": self.get(Binary, request.target_binary_id),
            }
        )
        report_path = f"comparisons/{task['resource_id']}.json"
        self.storage_budget()
        sha = atomic_json(self.root / report_path, result)
        with self.lock, self.sessions.begin() as db:
            row = db.get(Comparison, task["resource_id"])
            row.artifact_path, row.artifact_hash = report_path, sha

    def delete_binary(self, binary_id: str) -> None:
        binary = self.get(Binary, binary_id)
        with self.lock, self.sessions.begin() as db:
            related = db.scalars(
                select(Comparison).where(
                    (Comparison.source_binary_id == binary_id)
                    | (Comparison.target_binary_id == binary_id)
                )
            ).all()
            ids = [binary_id, *[c.id for c in related]]
            if db.scalar(
                select(Job).where(Job.resource_id.in_(ids), Job.state.in_(["queued", "running"]))
            ):
                raise ReconError(
                    "JOB_ACTIVE",
                    "Cancel active jobs and wait for them to finish before deleting this binary.",
                    409,
                )
            paths = [c.artifact_path for c in related if c.artifact_path]
            paths.extend(
                [
                    f"binaries/{binary['sha256']}",
                    f"analysis/{binary_id}.json",
                    f"indexes/{binary_id}.json",
                    f"indexes/{binary_id}.sha256",
                ]
            )
            db.execute(delete(Job).where(Job.resource_id.in_(ids)))
            db.delete(db.get(Binary, binary_id))
        for path in paths:
            inside(self.root, path).unlink(missing_ok=True)
        self.index_cache.pop(binary_id, None)

    def perform_experiment(self, task: dict[str, Any]) -> None:
        from recon.ml.research import run_experiment

        path, sha = run_experiment(task, self.settings, lambda: self.is_cancelled(task["id"]))
        with self.sessions.begin() as db:
            row = db.get(Experiment, task["resource_id"])
            row.artifact_path, row.artifact_hash = path, sha
