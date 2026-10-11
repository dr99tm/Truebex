"""5.1 for the analysis kinds (contract render-jobs §5.1; PF11).

PF6's `render.service.submit` hands these kinds here. The order of checks:
the kind's params (422), its required input files uploaded as `job-input`
(422), the plan's feature (403 `plan_required`), the project when one is
named (viewer access; 409 `seq_ahead`), the files themselves (a binary STL,
an epJSON with zones, a rooms file), the estimate, the quota (403
`quota_exceeded`). The job then waits on PF6's queue for a worker of its
class (`cpu-8`; `gpu-ai` for texture).

An analysis may name no project: its inputs are self-contained (AN3 uploads
the watertight geometry), so `project_id` is optional here; when given, the
result echoes it and `at_seq`.
"""

import re
import secrets

from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..licence import clock
from ..projects import service as projects
from ..projects.caller import ProjectCaller
from ..render import quotas
from ..render.models import RenderJob
from ..render.queue import notify_claim
from . import estimates, inputs, kinds, weather
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


def submit(db: Session, caller: ProjectCaller, body: dict) -> tuple[RenderJob, bool]:
    from ..render import service as render_service

    user = caller.user
    kind = kinds.KINDS[body["kind"]]
    params = kinds.validate_params(kind.name, body.get("params"), known_weather=lambda wid: weather.known(db, wid))
    files = (body.get("inputs") or {}).get("files") if isinstance(body.get("inputs"), dict) else None
    need = kinds.REQUIRED_FILES.get(kind.name)
    if need and not (isinstance(files, dict) and files.get(need)):
        raise invalid(f"inputs.files.{need}", f"a {kind.name} job needs its {need} uploaded as a job-input")
    allowed = {need, *kinds.OPTIONAL_FILES.get(kind.name, ())} - {None}
    extra = sorted(set(files or {}) - allowed)
    if extra:
        raise invalid("inputs.files", f"a {kind.name} job takes {', '.join(sorted(allowed)) or 'no files'}", unknown=extra)
    plan = require_feature(db, user, kind)
    project_id = body.get("project_id")
    at_seq = body.get("at_seq", 0)
    if project_id is not None:
        if not isinstance(project_id, str) or not _HEX32.match(project_id):
            raise invalid("project_id", "the project's 32-hex id, or leave it out")
        if not isinstance(at_seq, int) or isinstance(at_seq, bool) or at_seq < 0:
            raise invalid("at_seq", "a sequence number, 0 or more")
        project, _member = projects.open_project(db, caller, project_id, "viewer")
        if at_seq > project.head_seq:
            raise ContractError(
                "seq_ahead", 409, f"at_seq {at_seq} is past the project's head ({project.head_seq}). Push first.",
                {"head_seq": project.head_seq},
            )
    elif not isinstance(at_seq, int) or isinstance(at_seq, bool) or at_seq < 0:
        raise invalid("at_seq", "a sequence number, 0 or more")
    job_inputs = render_service._job_input_files(db, user, body.get("inputs"))
    meta: dict = {}
    if kind.name == "wind":
        mesh = inputs.stl(db, user.id, files["geometry"], "inputs.files.geometry")
        if files.get("entities"):
            inputs.entities_match(db, user.id, files["entities"], mesh.triangles)
        for name in ("surroundings", "terrain"):
            if files.get(name):
                inputs.stl(db, user.id, files[name], f"inputs.files.{name}")
        units, detail = estimates.units_for("wind", mesh=mesh)
        meta = {"geometry_triangles": mesh.triangles}
    elif kind.name == "energy":
        zones, tph = inputs.energy_model(db, user.id, files["model"], kinds.PROFILES["energy"]["timesteps_per_hour_default"])
        units, detail = estimates.units_for("energy", zones=zones, tph=tph)
    elif kind.name == "acoustics":
        meta = {"rooms": inputs.rooms(db, user.id, files["rooms"])}
        units, detail = estimates.units_for("acoustics", params=params)
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
        quality="standard",
        follow=False,
        inputs={**job_inputs, **meta, "estimate": est.detail},
        params=params,
        priority=plan.rank,
        doc_version_needed=render_service.doc_version_needed(db, project_id, at_seq) if project_id else 0,
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
