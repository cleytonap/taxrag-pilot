"""Local HTTP API for the TaxRAG application and developer tools."""

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from taxrag.database import SessionLocal
from taxrag.eval_manager import (
    compare_artifacts,
    debug_answer,
    get_artifact,
    get_fixture,
    get_run_job,
    list_artifacts,
    list_suites,
    promote_to_baseline,
    run_suite,
    save_fixture,
    start_suite_run,
)

app = FastAPI(title="TaxRAG API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)


class FixtureUpdate(BaseModel):
    """Local developer payload for replacing one versioned fixture file."""

    content: str = Field(min_length=1)


class DebugAnswerRequest(BaseModel):
    """One explicit question submitted from the local Eval Manager workbench."""

    question: str = Field(min_length=1, max_length=4_000)
    strategy: Literal["lexical", "lexical_authority", "semantic", "hybrid_rrf", "hybrid_rerank"] = "semantic"
    provider: Literal["fake", "openai"] = "fake"
    confirm_paid_request: bool = False


class SuiteRunRequest(BaseModel):
    """Local suite run configuration selected in the Eval Workshop."""

    strategy: Literal["lexical", "lexical_authority", "semantic", "hybrid_rrf", "hybrid_rerank"] = "lexical"
    provider: Literal["fake", "openai"] = "fake"
    confirm_paid_request: bool = False


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is alive; dependency checks come later."""
    return {"status": "ok"}


@app.get("/api/evals/suites")
def eval_suites() -> dict[str, object]:
    """List the small closed set of versioned evaluation suites."""
    return {"suites": list_suites()}


@app.get("/api/evals/suites/{suite_id}/fixture")
def eval_fixture(suite_id: str) -> dict[str, object]:
    """Return one editable local fixture after resolving its known suite id."""
    try:
        return get_fixture(suite_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/evals/suites/{suite_id}/run")
def run_eval_suite(suite_id: str, request: SuiteRunRequest) -> dict[str, object]:
    """Execute a known suite locally and persist its result artifact for review."""
    with SessionLocal() as session:
        try:
            return run_suite(
                session,
                suite_id=suite_id,
                strategy=request.strategy,
                provider_id=request.provider,
                confirm_paid_request=request.confirm_paid_request,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except SQLAlchemyError as error:
            raise HTTPException(status_code=503, detail="The local database is unavailable") from error


@app.post("/api/evals/suites/{suite_id}/jobs")
def start_eval_suite_job(suite_id: str, request: SuiteRunRequest) -> dict[str, object]:
    """Start a suite run in the background; the UI polls the job instead of holding a request."""
    try:
        return start_suite_run(
            suite_id=suite_id,
            strategy=request.strategy,
            provider_id=request.provider,
            confirm_paid_request=request.confirm_paid_request,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/evals/jobs/{job_id}")
def eval_suite_job(job_id: str) -> dict[str, object]:
    """Return progress, and the result once finished, for one background suite run."""
    try:
        return get_run_job(job_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


class BaselineRequest(BaseModel):
    """Promote one saved run artifact to a named, Git-tracked baseline."""

    artifact_name: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=40)


@app.post("/api/evals/baselines")
def promote_eval_baseline(request: BaselineRequest) -> dict[str, object]:
    """Copy a run into docs/evals/baselines/ so later changes can be compared against it."""
    try:
        return promote_to_baseline(request.artifact_name, request.label)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Run artifact not found: {error}") from error
    except FileExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/evals/compare")
def compare_eval_runs(baseline: str, candidate: str) -> dict[str, object]:
    """Compare a candidate run with a baseline: metric deltas and per-case changes."""
    try:
        return compare_artifacts(baseline, candidate)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Artifact not found: {error}") from error
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.put("/api/evals/suites/{suite_id}/fixture")
def update_eval_fixture(suite_id: str, update: FixtureUpdate) -> dict[str, object]:
    """Validate and save a local fixture; this changes the developer's Git working tree."""
    try:
        return save_fixture(suite_id, update.content)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/evals/artifacts")
def eval_artifacts() -> dict[str, object]:
    """List read-only local run artifacts."""
    return {"artifacts": list_artifacts()}


@app.get("/api/evals/artifacts/{artifact_name}")
def eval_artifact(artifact_name: str) -> dict[str, str]:
    """Return one bounded local artifact for debugging and review."""
    try:
        return get_artifact(artifact_name)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Artifact not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/evals/debug-answer")
def debug_eval_answer(request: DebugAnswerRequest) -> dict[str, object]:
    """Run one diagnostic answer request without storing a new evaluation artifact yet."""
    with SessionLocal() as session:
        try:
            return debug_answer(
                session,
                question=request.question,
                strategy=request.strategy,
                provider_id=request.provider,
                confirm_paid_request=request.confirm_paid_request,
            )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except SQLAlchemyError as error:
            raise HTTPException(
                status_code=503,
                detail=(
                    "The local database is unavailable. Start it with `docker compose up -d` "
                    "and apply migrations with `uv run alembic upgrade head`."
                ),
            ) from error
