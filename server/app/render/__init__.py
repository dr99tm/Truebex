"""Cloud render orchestration (PF6, contract render-jobs v1.0).

The jobs table is the queue: clients submit (`service`), workers claim with a
lease (`queue`), followed panorama sets re-render the faces an edit touches
(`sets`), tiles are content-addressed behind a CDN (`tiles`), every success is
metered in cost units against the tier's allowance (`quotas`, `overage`), and
the worker pool scales on queue depth (`pools`). Jobs: `jobs.py`.
"""
