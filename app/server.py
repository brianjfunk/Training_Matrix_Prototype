"""Minimal single-page web app for the role-aware training matrix.

Run with: uvicorn app.server:app --reload

Datasets are discovered by listing subdirectories of companies/ — loading a
new company means dropping its five CSVs into a new companies/<name>/
folder, with zero code changes required.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.dataset import DatasetError, load_dataset
from app.matching import compute_all, compute_matrix
from app.reports import (
    comparison_summary_rows,
    company_rollup_rows,
    gap_report_rows,
    master_matrix_rows,
    rows_to_csv,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPANIES_DIR = REPO_ROOT / "companies"

app = FastAPI(title="Role-Aware Training Matrix")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def list_companies() -> list[str]:
    if not COMPANIES_DIR.exists():
        return []
    return sorted(p.name for p in COMPANIES_DIR.iterdir() if p.is_dir())


def _load_or_404(company: str):
    company_dir = COMPANIES_DIR / company
    if not company_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Unknown company dataset: {company}")
    try:
        return load_dataset(company_dir)
    except DatasetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/", response_class=HTMLResponse)
def index(request: Request, company: str | None = None, profile: str | None = None):
    companies = list_companies()
    if not companies:
        return templates.TemplateResponse(
            request, "index.html", {"companies": [], "error": "No datasets found under companies/."}
        )

    company = company if company in companies else companies[0]
    dataset = _load_or_404(company)

    profile_ids = dataset.profile_order()
    profile = profile if profile in profile_ids else (profile_ids[0] if profile_ids else None)

    all_results = compute_all(dataset)
    summary_rows = comparison_summary_rows(all_results)
    rollup_rows = company_rollup_rows(all_results)
    gap_rows = gap_report_rows(all_results)

    selected_result = None
    assignments_by_tier: dict[str, list] = {"Must-Know": [], "Must-Locate": [], "Not Applicable": []}
    if profile is not None:
        selected_result = compute_matrix(dataset, profile)
        for a in selected_result.assignments:
            assignments_by_tier[a.tier].append(a)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "companies": companies,
            "company": company,
            "profiles": [dataset.profiles[pid] for pid in profile_ids],
            "selected_profile_id": profile,
            "selected_result": selected_result,
            "assignments_by_tier": assignments_by_tier,
            "summary_rows": summary_rows,
            "rollup_rows": rollup_rows,
            "gap_rows": gap_rows,
            "gap_count": len(gap_rows),
            "error": None,
        },
    )


@app.get("/export/{report}.csv")
def export_csv(report: str, company: str = Query(...)):
    dataset = _load_or_404(company)
    all_results = compute_all(dataset)

    builders = {
        "master_matrix": master_matrix_rows,
        "comparison_summary": comparison_summary_rows,
        "company_rollup": company_rollup_rows,
        "gap_report": gap_report_rows,
    }
    if report not in builders:
        raise HTTPException(status_code=404, detail=f"Unknown report: {report}")

    rows = builders[report](all_results)
    csv_text = rows_to_csv(rows)
    filename = f"{company}-{report}.csv"
    return PlainTextResponse(
        csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
