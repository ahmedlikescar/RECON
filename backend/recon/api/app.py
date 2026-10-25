import csv
import io
import mimetypes
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import FastAPI, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import func, select
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from recon import ANALYZER_VERSION, FEATURE_SCHEMA, __version__
from recon.api.views import (
    BinaryView,
    ComparisonCreated,
    ComparisonView,
    ExperimentView,
    FunctionSummary,
    FunctionView,
    ImportView,
    JobView,
    Page,
)
from recon.config import REPO_ROOT, Settings
from recon.errors import ReconError
from recon.schemas import CFG, ComparisonRequest, InvestigationRequest, TrainingRequest
from recon.security.http import BodyBudgetMiddleware
from recon.security.validation import csv_cell, inside
from recon.service import Service, identifier
from recon.storage.artifacts import read_json
from recon.storage.database import Binary, Comparison, Experiment, Function, Job, record

ORIGINS = {f"http://{host}:{port}" for host in ["127.0.0.1", "localhost"] for port in [5173, 8000]}
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    service: Service

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        nonlocal service
        service = Service(settings)
        app.state.service = service
        service.start()
        yield
        service.close()

    app = FastAPI(title="RECON", version=__version__, lifespan=lifespan)
    app.add_middleware(BodyBudgetMiddleware, max_bytes=settings.max_upload_bytes + 65536)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(ORIGINS),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )

    @app.middleware("http")
    async def local_guard(request: Request, call_next: Any) -> Response:
        origin = request.headers.get("origin")
        if origin and origin not in ORIGINS and origin != str(request.base_url).rstrip("/"):
            return JSONResponse(
                {
                    "error": {
                        "code": "ORIGIN_DENIED",
                        "message": "Only the local RECON interface may access this service.",
                    }
                },
                status_code=403,
            )
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > settings.max_upload_bytes + 65536):
            return JSONResponse(
                {
                    "error": {
                        "code": "FILE_TOO_LARGE",
                        "message": "Request exceeds the configured upload budget.",
                    }
                },
                status_code=413,
            )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' http://127.0.0.1:8000; frame-ancestors 'none'; base-uri 'self'"
        )
        return response

    @app.exception_handler(ReconError)
    async def recon_error(_: Request, exc: ReconError) -> JSONResponse:
        return JSONResponse(
            {"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
        return JSONResponse(
            {"error": {"code": f"HTTP_{exc.status_code}", "message": str(exc.detail)}},
            status_code=exc.status_code,
        )

    @app.get("/api/v1/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": __version__,
            "analyzer_version": ANALYZER_VERSION,
            "feature_schema": FEATURE_SCHEMA,
            "local_only": True,
        }

    @app.get("/api/v1/capabilities")
    def capabilities() -> dict[str, Any]:
        from recon.analysis.providers import provider_status
        from recon.ml.model import model_status

        return {
            "formats": ["ELF"],
            "architectures": ["x86-64"],
            "bitness": [64],
            "methods": ["hybrid", "opcode", "ngram", "structure", "neural"],
            "max_upload_bytes": settings.max_upload_bytes,
            "analyzer_version": ANALYZER_VERSION,
            "feature_schema": FEATURE_SCHEMA,
            "neural": model_status(settings.root / "models/current"),
            "providers": provider_status(settings),
            "target_execution": False,
            "limits": {
                "worker_seconds": settings.worker_timeout,
                "worker_memory_mb": settings.worker_memory_mb,
                "functions": settings.max_functions,
                "instructions": settings.max_instructions,
            },
        }

    @app.post("/api/v1/binaries", response_model=ImportView, status_code=202)
    async def upload(file: UploadFile) -> dict[str, Any]:
        try:
            data = await file.read(settings.max_upload_bytes + 1)
            return service.import_binary(data, file.filename)
        finally:
            await file.close()

    @app.get("/api/v1/binaries", response_model=Page[BinaryView])
    def binaries(offset: Offset = 0, limit: Limit = 50) -> dict[str, Any]:
        with service.sessions() as db:
            rows = db.scalars(
                select(Binary).order_by(Binary.imported_at.desc()).offset(offset).limit(limit)
            ).all()
            return {
                "items": [record(r) for r in rows],
                "total": db.scalar(select(func.count()).select_from(Binary)),
                "offset": offset,
                "limit": limit,
            }

    @app.get("/api/v1/binaries/{binary_id}", response_model=BinaryView)
    def binary(binary_id: str) -> dict[str, Any]:
        return service.get(Binary, binary_id)

    @app.post("/api/v1/binaries/{binary_id}/reanalyze", response_model=JobView, status_code=202)
    def reanalyze(binary_id: str) -> dict[str, Any]:
        return service.reanalyze(binary_id)

    @app.delete("/api/v1/binaries/{binary_id}", status_code=204)
    def remove(binary_id: str) -> Response:
        service.delete_binary(binary_id)
        return Response(status_code=204)

    @app.get("/api/v1/binaries/{binary_id}/functions", response_model=Page[FunctionSummary])
    def functions(
        binary_id: str,
        search: Annotated[str, Query(max_length=100)] = "",
        offset: Offset = 0,
        limit: Limit = 50,
    ) -> dict[str, Any]:
        service.get(Binary, binary_id)
        with service.sessions() as db:
            statement = (
                select(Function).where(Function.binary_id == binary_id).order_by(Function.address)
            )
            rows = db.scalars(statement).all()
            if search:
                needle = search.lower()
                analysis = service.analysis(binary_id)
                rows = [
                    r
                    for r in rows
                    if needle in r.name.lower()
                    or needle in hex(r.address)
                    or needle in r.discovery_method
                    or any(
                        needle in i.mnemonic
                        for i in analysis.functions[r.artifact_index].instructions
                    )
                ]
            return {
                "items": [record(r) for r in rows[offset : offset + limit]],
                "total": len(rows),
                "offset": offset,
                "limit": limit,
            }

    @app.get("/api/v1/functions/{function_id}", response_model=FunctionView)
    def function(function_id: str) -> dict[str, Any]:
        row, analysis = service.function(function_id)
        return {**analysis.model_dump(), "id": row["id"], "binary_id": row["binary_id"]}

    @app.get("/api/v1/functions/{function_id}/cfg", response_model=CFG)
    def cfg(function_id: str) -> CFG:
        return service.function(function_id)[1].cfg

    @app.post("/api/v1/comparisons", response_model=ComparisonCreated, status_code=202)
    def compare(request: ComparisonRequest) -> dict[str, Any]:
        return service.compare(request)

    @app.get("/api/v1/comparisons", response_model=Page[ComparisonView])
    def comparisons(offset: Offset = 0, limit: Limit = 50) -> dict[str, Any]:
        with service.sessions() as db:
            rows = db.scalars(
                select(Comparison)
                .order_by(Comparison.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).all()
            return {
                "items": [record(r) for r in rows],
                "total": db.scalar(select(func.count()).select_from(Comparison)),
                "offset": offset,
                "limit": limit,
            }

    @app.get("/api/v1/comparisons/{comparison_id}", response_model=ComparisonView)
    def comparison(comparison_id: str) -> dict[str, Any]:
        row = service.get(Comparison, comparison_id)
        if row["artifact_path"] and row["status"] == "completed":
            row["result"] = read_json(
                inside(service.root, row["artifact_path"]), row["artifact_hash"]
            )
        return row

    @app.get("/api/v1/jobs", response_model=Page[JobView])
    def jobs(offset: Offset = 0, limit: Limit = 50) -> dict[str, Any]:
        with service.sessions() as db:
            rows = db.scalars(
                select(Job).order_by(Job.created_at.desc()).offset(offset).limit(limit)
            ).all()
            return {
                "items": [record(r) for r in rows],
                "total": db.scalar(select(func.count()).select_from(Job)),
                "offset": offset,
                "limit": limit,
            }

    @app.get("/api/v1/jobs/{job_id}", response_model=JobView)
    def job(job_id: str) -> dict[str, Any]:
        return service.get(Job, job_id)

    @app.post("/api/v1/jobs/{job_id}/cancel", response_model=JobView)
    def cancel(job_id: str) -> dict[str, Any]:
        return service.cancel(job_id)

    @app.post("/api/v1/demo", response_model=list[ImportView], status_code=202)
    def demo() -> list[dict[str, Any]]:
        folder = settings.root / "fixtures"
        files = [folder / f"demo-{opt}.elf" for opt in ["O0", "O2"]]
        if not all(p.is_file() for p in files):
            raise ReconError(
                "DEMO_NOT_INSTALLED",
                "Build the known demo fixtures first: python scripts/build_fixtures.py. The imported programs will not be run.",
                409,
            )
        return [service.import_binary(p.read_bytes(), p.name) for p in files]

    @app.get("/api/v1/demo/{optimization}")
    def demo_download(optimization: str) -> FileResponse:
        if optimization not in {"O0", "O2"}:
            raise ReconError("NOT_FOUND", "Demo build not found.", 404)
        path = settings.root / "fixtures" / f"demo-{optimization}.elf"
        if not path.is_file():
            raise ReconError("DEMO_NOT_INSTALLED", "Build the demo fixtures first.", 409)
        return FileResponse(path, media_type="application/octet-stream", filename=path.name)

    @app.get("/api/v1/reports/{resource_id}/export")
    def export(resource_id: str, format: str = "json") -> Response:
        if format not in {"json", "csv"}:
            raise ReconError("EXPORT_FORMAT", "Choose json or csv.")
        try:
            row = service.get(Comparison, resource_id)
        except ReconError:
            try:
                row = service.get(Experiment, resource_id)
            except ReconError:
                row = service.get(Binary, resource_id)
        if row["status"] != "completed" or not row["artifact_path"]:
            raise ReconError("REPORT_NOT_READY", "This task has no completed report yet.", 409)
        report = read_json(inside(service.root, row["artifact_path"]), row["artifact_hash"])
        if "filename" in row:
            report = {
                **service.analysis(resource_id).model_dump(),
                "binary": BinaryView.model_validate(row).model_dump(),
                "report_kind": "analysis",
            }
        headers = {"Content-Disposition": f'attachment; filename="recon-{resource_id}.{format}"'}
        if format == "json":
            return JSONResponse(report, headers=headers)
        stream = io.StringIO()
        writer = csv.writer(stream)
        if report.get("report_kind") == "analysis":
            writer.writerow(
                [
                    "function",
                    "function_address",
                    "instruction_address",
                    "mnemonic",
                    "operands",
                    "normalized_token",
                    "source_sha256",
                    "analyzer_version",
                    "feature_schema",
                    "discovery_method",
                ]
            )
            for function in report["functions"]:
                for instruction in function["instructions"]:
                    writer.writerow(
                        [
                            csv_cell(function["name"]),
                            hex(function["address"]),
                            hex(instruction["address"]),
                            csv_cell(instruction["mnemonic"]),
                            csv_cell(instruction["operands"]),
                            csv_cell(instruction["token"]),
                            report["sha256"],
                            report["analyzer_version"],
                            report["feature_schema"],
                            function["discovery_method"],
                        ]
                    )
            return Response(stream.getvalue(), media_type="text/csv", headers=headers)
        writer.writerow(
            [
                "query_function",
                "candidate_function",
                "rank",
                "similarity_score",
                "method",
                "model_version",
                "feature_schema",
                "source_sha256",
                "target_sha256",
                "limitations",
            ]
        )

        for query in report.get("results", []):
            for match in query["matches"]:
                writer.writerow(
                    [
                        csv_cell(query["name"]),
                        csv_cell(match["name"]),
                        match["rank"],
                        match["similarity_score"],
                        report["method"],
                        report["model_version"],
                        report["feature_schema"],
                        report["source_binary"]["sha256"],
                        report["target_binary"]["sha256"],
                        " ".join(report["limitations"]),
                    ]
                )
        if "results" not in report:
            raise ReconError(
                "EXPORT_FORMAT",
                "Experiment reports use JSON to preserve nested provenance. Choose json.",
            )
        return Response(stream.getvalue(), media_type="text/csv", headers=headers)

    @app.post("/api/v1/experiments/{kind}", status_code=202)
    def experiment(kind: str, request: TrainingRequest) -> dict[str, Any]:
        if kind not in {"train", "evaluate"}:
            raise ReconError("EXPERIMENT_KIND", "Choose train or evaluate.")
        dataset = settings.root / "research/dataset.json"
        if not dataset.is_file():
            raise ReconError(
                "DATASET_NOT_READY",
                "Build the licensed research dataset first: recon dataset build.",
                409,
            )
        with service.lock, service.sessions.begin() as db:
            service.check_queue()
            item = Experiment(id=identifier(), kind=kind, config_json=request.model_dump())
            job = Job(
                id=identifier(), kind=kind, resource_id=item.id, config_json=request.model_dump()
            )
            db.add_all([item, job])
            db.flush()
            result = {"experiment": record(item), "job_id": job.id}
        service.wake.set()
        return result

    @app.get("/api/v1/research/status")
    def research_status() -> dict[str, Any]:
        from recon.ml.model import model_status

        path = settings.root / "research/dataset.json"
        dataset = read_json(path) if path.is_file() else None
        return {
            "dataset_available": dataset is not None,
            "sample_count": len(dataset["samples"]) if dataset else 0,
            "projects": dataset["audit"]["projects"] if dataset else {},
            "missing_toolchains": dataset["missing_toolchains"] if dataset else [],
            "model": model_status(settings.root / "models/current"),
        }

    @app.get("/api/v1/experiments", response_model=Page[ExperimentView])
    def experiments(offset: Offset = 0, limit: Limit = 50) -> dict[str, Any]:
        with service.sessions() as db:
            rows = db.scalars(
                select(Experiment)
                .order_by(Experiment.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).all()
            return {
                "items": [record(r) for r in rows],
                "total": db.scalar(select(func.count()).select_from(Experiment)),
                "offset": offset,
                "limit": limit,
            }

    @app.get("/api/v1/experiments/{experiment_id}", response_model=ExperimentView)
    def experiment_detail(experiment_id: str) -> dict[str, Any]:
        row = service.get(Experiment, experiment_id)
        if row["status"] == "completed" and row["artifact_path"]:
            row["result"] = read_json(
                inside(service.root, row["artifact_path"]), row["artifact_hash"]
            )
        return row

    @app.post("/api/v1/functions/{function_id}/investigate")
    def investigate(function_id: str, request: InvestigationRequest) -> dict[str, Any]:
        from recon.analysis.providers import investigate_function

        row, analysis = service.function(function_id)
        binary = service.get(Binary, row["binary_id"])
        return investigate_function(
            settings, service.root / "binaries" / binary["sha256"], analysis, request.consent
        )

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> Response:
        if path.startswith("api/"):
            raise ReconError("NOT_FOUND", "API route not found.", 404)
        dist = REPO_ROOT / "frontend/dist"
        target = (dist / path).resolve()
        if target.is_relative_to(dist.resolve()) and target.is_file():
            return FileResponse(target, media_type=mimetypes.guess_type(target)[0])
        index = dist / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse(
            {
                "message": "RECON API is running. Build frontend with pnpm --dir frontend build, or start the Vite development server.",
                "docs": "/docs",
            }
        )

    return app
