"""5.1 for the analysis kinds (contract render-jobs §5.1, §6.5; PF11, PF11c).

PF6's `render.service.submit` hands these kinds here. The order of checks:
the kind's params (422), its quality (422), its required input files
uploaded as `job-input` (422), the plan's feature (403 `plan_required`), the
reference (§6.5.1, below), the files themselves (a closed binary STL of at
most 200 000 triangles with 16 bytes of entity ids each, an epJSON with
zones, a rooms file), the wind job an airflow job runs on (422), the
estimate, the quota (403 `quota_exceeded`). The job then waits on PF6's
queue for a worker of its class (`cpu-8`; `gpu-ai` for texture); an airflow
job also for its wind job (`dependents`). Its quality (draft, standard or
high) is kept: a wind job's mesh follows it (`kinds.profile`).

The reference (§6.5.1): an analysis computes from its upload alone, and its
`project_id` (32 hex, optional) and `at_seq` record what was computed: the
cloud project's id when the project is cloud-saved, else the document's own
CL0 project id. Only a cloud project the caller can view is checked against
its head (409 `seq_ahead`); any other id (a document id, someone else's
project, a deleted one) is recorded as given, with no error and no hint
whether it exists. The job never opens a snapshot, so its
`doc_version_needed` is 0.
"""

import re
import secrets

from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..licence import clock
from ..projects import service as projects
from ..projects.caller import ProjectCaller
from ..projects.models import Project
from ..render import quotas
from ..render.models import RenderJob
from ..render.queue import notify_claim
from . import dependents, estimates, inputs, kinds, weather
from .validation import invalid

_HEX32 = re.compile(r"^[0-9a-f]{32}$")

handles = kinds.handles


def require_feature(db: Session, user, kind) -> object:
    plan = quotas.plan_of(db, user)
    if kind.feature not in plan.features:
        what = "Texture generation" if kind.name == kinds.TEXTURE else "Analysis reports"
        raise ContractError(
            "plan_required", 403, f"{what} come with a paid plan or the trial. Upgrade to run them in the cloud.",
            {"feature": kind.feature, "plan": plan.id},
        )
    return plan


def reference(db: Session, caller: ProjectCaller, body: dict) -> tuple[str | None, int]:
    """(project_id, at_seq) as given (§6.5.1); 409 `seq_ahead` only past the head
    of a cloud project the caller can view."""
    project_id = body.get("project_id")
    at_seq = body.get("at_seq", 0)
    if not isinstance(at_seq, int) or isinstance(at_seq, bool) or at_seq < 0:
        raise invalid("at_seq", "a sequence number, 0 or more")
    if project_id is None:
        return None, at_seq
    if not isinstance(project_id, str) or not _HEX32.match(project_id):
        raise invalid("project_id", "the project's 32-hex id (the cloud project's, else the document's own), or leave it out")
    project = db.get(Project, project_id)
    if project is not None and project.deleted_at is None and projects.membership(db, project_id, caller.user.id) is not None:
        if at_seq > project.head_seq:
            raise ContractError(
                "seq_ahead", 409, f"at_seq {at_seq} is past the project's head ({project.head_seq}). Push first.",
                {"head_seq": project.head_seq},
            )
    return project_id, at_seq


def submit(db: Session, caller: ProjectCaller, body: dict) -> tuple[RenderJob, bool]:
    from ..render import service as render_service

    user = caller.user
    kind = kinds.KINDS[kinds.name_of(body["kind"])]
    params = kinds.validate_params(kind.name, body.get("params"), known_weather=lambda wid: weather.known(db, wid))
    quality = kinds.quality_of(body.get("quality"))
    files = (body.get("inputs") or {}).get("files") if isinstance(body.get("inputs"), dict) else None
    needs = kinds.REQUIRED_FILES.get(kind.name, ())
    for need in needs:
        if not (isinstance(files, dict) and files.get(need)):
            raise invalid(f"inputs.files.{need}", f"a {kind.name} job needs its {need} uploaded as a job-input")
    if kind.name == "airflow" and files.get("geometry"):
        # §6.5.3's optional interior air volume for a CFD run: not offered yet (GD2).
        raise invalid(
            "inputs.files.geometry",
            "the interior CFD run is not available yet: send the rooms file alone (the orifice network runs on the wind job's Cp)",
        )
    allowed = {*needs, *kinds.OPTIONAL_FILES.get(kind.name, ())}
    extra = sorted(set(files or {}) - allowed)
    if extra:
        raise invalid("inputs.files", f"a {kind.name} job takes {', '.join(sorted(allowed)) or 'no files'}", unknown=extra)
    plan = require_feature(db, user, kind)
    project_id, at_seq = reference(db, caller, body)
    job_inputs = render_service._job_input_files(db, user, body.get("inputs"))
    meta: dict = {}
    base_job_id = None
    message = ""
    if kind.name == "wind":
        mesh = inputs.stl(db, user.id, files["geometry"], "inputs.files.geometry", max_triangles=inputs.MAX_GEOMETRY_TRIANGLES, closed=True)
        inputs.entities_match(db, user.id, files["entities"], mesh.triangles)
        for name in ("surroundings", "terrain"):
            if files.get(name):
                inputs.stl(db, user.id, files[name], f"inputs.files.{name}")
        units, detail = estimates.units_for("wind", mesh=mesh, quality=quality)
        meta = {"geometry_triangles": mesh.triangles, "geometry_over_shared_edges": mesh.over_shared_edges}
    elif kind.name == "energy":
        zones, tph = inputs.energy_model(db, user.id, files["model"], kinds.PROFILES["energy"]["timesteps_per_hour_default"])
        units, detail = estimates.units_for("energy", zones=zones, tph=tph)
    elif kind.name == "acoustics":
        meta = {"rooms": inputs.rooms(db, user.id, files["rooms"])}
        units, detail = estimates.units_for("acoustics", params=params)
    elif kind.name == "airflow":
        rooms, openings = inputs.airflow_rooms(db, user.id, files["rooms"])
        wind = dependents.wind_job_for(db, user, params)
        base_job_id = wind.job_id
        message = "" if wind.state == "succeeded" else dependents.WAITING
        units, detail = estimates.units_for("airflow", rooms=rooms, openings=openings)
        meta = {"rooms": rooms, "openings": openings}
    else:
        units, detail = estimates.units_for(kinds.TEXTURE, params=params)
    est = estimates.estimate(db, kind.name, units, detail)
    quotas.check(db, user, plan, est.cost_units)
    now = clock.now()
    job = RenderJob(
        job_id=secrets.token_hex(16),
        account_kind=quotas.ACCOUNT_KIND,
        account_id=user.id,
        kind=kind.name,
        worker_class=kind.worker_class,
        state="queued",
        rev=1,
        project_id=project_id,
        at_seq=at_seq,
        views=[],
        changed=[],
        base_job_id=base_job_id,
        quality=quality,
        follow=False,
        message=message,
        inputs={**job_inputs, **meta, "estimate": est.detail},
        params=params,
        priority=plan.rank,
        doc_version_needed=0,
        created_at=now,
        queued_at=now,
        updated_at=now,
        est_units=units,
        cost_units_estimate=est.cost_units,
    )
    db.add(job)
    db.commit()
    notify_claim()
    return job, False
