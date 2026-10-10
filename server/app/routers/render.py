"""Cloud render orchestration's routes in one router (PF6), so main.py
registers the feature with one line: the jobs (5.1-5.6), the worker protocol
(5.7-5.10), public tiles and a live share's set, and the render admin.
Importing it registers the render jobs, the follow trigger on PF4's push
hook and the worker-token lookup of the upload protocol."""

from fastapi import APIRouter

from ..render import jobs as _render_jobs  # noqa: F401  (render.* jobs, the push hook, the worker lookup)
from . import admin_render, jobs, tiles, workers

router = APIRouter()
router.include_router(jobs.router)
router.include_router(workers.router)
router.include_router(tiles.router)
router.include_router(tiles.share_router)
router.include_router(admin_render.router)
