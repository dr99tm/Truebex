"""Analysis and AI services' routes in one router (PF11), so main.py registers
the feature with one line: the AI proxy (/ai, contract ai-proxy), the
dashboard's AI section and its admin (/account/ai, /admin/ai), the analysis
catalogue and weather library (/analysis, /admin/analysis). Analysis jobs
themselves use PF6's /jobs and /workers. Importing it registers the ai.* jobs,
the analysis kinds on PF6's queue and the billing hook that credits bought
packs."""

from fastapi import APIRouter

from ..ai import jobs as _ai_jobs  # noqa: F401  (ai.* jobs, the PAID_HOOK)
from ..analysis import kinds as _analysis_kinds  # noqa: F401  (registers wind, energy, acoustics)
from . import ai, ai_account, analysis

router = APIRouter()
router.include_router(ai.router)
router.include_router(ai_account.router)
router.include_router(analysis.router)
router.include_router(analysis.admin_router)
