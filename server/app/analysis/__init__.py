"""Analysis services on PF6's queue (PF11, contract render-jobs §5.1, §6.3).

Heavy analyses run as solver containers on CPU workers instead of the
designer's PC: `wind` (CFD), `energy` (building energy simulation) and
`acoustics` (room acoustics by ray tracing), plus `texture` (seamless PBR
maps on gpu-ai) behind AI_TEXTURE_ENABLED. `kinds` validates a submission,
`estimates` prices it before it runs, `results` checks a worker's
`truebex-analysis/1` output and serves it with signed file URLs, `weather`
keeps the EPW library. The runner code the images run is in `runners/`.
"""
