"""Generic loader for a company's five-CSV dataset.

The five files (sops.csv, tasks.csv, profiles.csv, conservative_baseline.csv,
projects.csv) define the app's entire input contract. This module reads them
into plain dataclasses and does no company-specific interpretation of any
field value — every mapping (role -> department, task -> SOP, profile ->
tasks) is built from the data itself, never from a hardcoded table.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Sop:
    sop_id: str
    title: str
    process_area: str
    summary: str
    broad_applicability_conservative: str


@dataclass(frozen=True)
class Task:
    task_id: str
    task_name: str
    process_area: str
    governing_sop_id: str


@dataclass(frozen=True)
class Profile:
    profile_id: str
    role_name: str
    person_label: str
    primary_department: str
    task_ids: tuple[str, ...]


@dataclass(frozen=True)
class Project:
    project_id: str
    project_name: str
    status: str
    description: str


@dataclass
class Dataset:
    sops: dict[str, Sop] = field(default_factory=dict)
    tasks: dict[str, Task] = field(default_factory=dict)
    profiles: dict[str, Profile] = field(default_factory=dict)
    role_department: dict[str, str] = field(default_factory=dict)
    projects: dict[str, Project] = field(default_factory=dict)

    def profile_order(self) -> list[str]:
        """Profile_IDs in the order they appeared in profiles.csv."""
        return list(self.profiles.keys())


class DatasetError(ValueError):
    """Raised when a company dataset does not conform to the input contract."""


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise DatasetError(f"Required file not found: {path}")
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _split_task_ids(raw: str) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(t.strip() for t in raw.split(";") if t.strip())


def load_dataset(company_dir: str | Path) -> Dataset:
    """Load a company's five CSVs from `company_dir` into a Dataset.

    `company_dir` must contain sops.csv, tasks.csv, profiles.csv, and
    conservative_baseline.csv. projects.csv is optional (contextual only).
    """
    company_dir = Path(company_dir)

    sops: dict[str, Sop] = {}
    for row in _read_rows(company_dir / "sops.csv"):
        sop_id = row["SOP_ID"].strip()
        sops[sop_id] = Sop(
            sop_id=sop_id,
            title=row["Title"].strip(),
            process_area=row["Process_Area"].strip(),
            summary=row["Summary"].strip(),
            broad_applicability_conservative=row["Broad_Applicability_Conservative"].strip(),
        )

    tasks: dict[str, Task] = {}
    for row in _read_rows(company_dir / "tasks.csv"):
        task_id = row["Task_ID"].strip()
        governing_sop_id = row["Governing_SOP_ID"].strip()
        if governing_sop_id not in sops:
            raise DatasetError(
                f"tasks.csv row {task_id} references unknown SOP_ID {governing_sop_id!r}"
            )
        tasks[task_id] = Task(
            task_id=task_id,
            task_name=row["Task_Name"].strip(),
            process_area=row["Process_Area"].strip(),
            governing_sop_id=governing_sop_id,
        )

    role_department: dict[str, str] = {}
    for row in _read_rows(company_dir / "conservative_baseline.csv"):
        role_name = row["Role_Name"].strip()
        department = row["Primary_Department"].strip()
        if role_name in role_department and role_department[role_name] != department:
            raise DatasetError(
                f"conservative_baseline.csv has conflicting departments for role {role_name!r}"
            )
        role_department[role_name] = department

    profiles: dict[str, Profile] = {}
    for row in _read_rows(company_dir / "profiles.csv"):
        profile_id = row["Profile_ID"].strip()
        role_name = row["Role_Name"].strip()
        if role_name not in role_department:
            raise DatasetError(
                f"profiles.csv role {role_name!r} (profile {profile_id}) has no entry "
                f"in conservative_baseline.csv"
            )
        task_ids = _split_task_ids(row["Task_IDs"])
        for task_id in task_ids:
            if task_id not in tasks:
                raise DatasetError(
                    f"profiles.csv profile {profile_id} references unknown Task_ID {task_id!r}"
                )
        profiles[profile_id] = Profile(
            profile_id=profile_id,
            role_name=role_name,
            person_label=row.get("Person_Label", "").strip(),
            # Primary_Department for matching always comes from
            # conservative_baseline.csv (hard constraint: it is data, not
            # code, and conservative_baseline.csv is its single source of
            # truth) even though profiles.csv may carry its own copy of the
            # column for display purposes.
            primary_department=role_department[role_name],
            task_ids=task_ids,
        )

    projects: dict[str, Project] = {}
    projects_path = company_dir / "projects.csv"
    if projects_path.exists():
        for row in _read_rows(projects_path):
            project_id = row["Project_ID"].strip()
            projects[project_id] = Project(
                project_id=project_id,
                project_name=row.get("Project_Name", "").strip(),
                status=row.get("Status", "").strip(),
                description=row.get("Description", "").strip(),
            )

    return Dataset(
        sops=sops,
        tasks=tasks,
        profiles=profiles,
        role_department=role_department,
        projects=projects,
    )
