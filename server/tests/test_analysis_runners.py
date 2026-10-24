"""The solver runners the analysis images run (PF11, server/app/analysis/runners):
the parts that need no solver — the EnergyPlus output parser, the wind case
and its sampling, the acoustics ray tracer — and every result through the
platform's own §6.3 check."""

import json
import math
import sqlite3
import struct
from pathlib import Path
from types import SimpleNamespace

from app.analysis import kinds, results
from app.analysis.runners import acoustics, common, energy, wind

ZONE_1 = "0199C6A2E00070038000000000000001"  # EnergyPlus upper-cases names
ZONE_2 = "0199C6A2E00070038000000000000002"


def _job(tmp_path: Path, kind: str, params: dict, inputs: dict | None = None, profile: dict | None = None) -> common.Job:
    data = {
        "schema": "truebex-analysis-job/1", "job_id": "a" * 32, "kind": kind, "project_id": None, "at_seq": 0,
        "params": params, "profile": profile if profile is not None else kinds.profile(kind),
        "inputs": {name: f"/job/inputs/{name}" for name in (inputs or {})}, "out_dir": "/job/out",
    }
    (tmp_path / "inputs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "out").mkdir(exist_ok=True)
    for name, content in (inputs or {}).items():
        (tmp_path / "inputs" / name).write_bytes(content)
    (tmp_path / "job.json").write_text(json.dumps(data), encoding="utf-8")
    return common.load_job(tmp_path)


def _platform_job(job: common.Job, **inputs) -> SimpleNamespace:
    return SimpleNamespace(job_id=job.job_id, kind=job.kind, project_id=job.project_id, at_seq=job.at_seq, params=job.params, inputs=inputs)


def _passes(result: dict, job: common.Job, out: Path, **inputs) -> None:
    assert results.check(json.loads(json.dumps(result)), _platform_job(job, **inputs)) == []
    for sha, size in results.named_files(result).items():
        path = out / sha
        assert path.is_file(), sha
        if size is not None:
            assert path.stat().st_size == size, sha


# --- energy ----------------------------------------------------------------------------------------


def _eplusout(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE TabularDataWithStrings (ReportName TEXT, ReportForString TEXT, TableName TEXT, RowName TEXT,
                                             ColumnName TEXT, Units TEXT, Value TEXT);
        CREATE TABLE Zones (ZoneIndex INTEGER, ZoneName TEXT, FloorArea REAL);
        CREATE TABLE ReportDataDictionary (ReportDataDictionaryIndex INTEGER, IsMeter INTEGER, Type TEXT, IndexGroup TEXT,
                                           TimestepType TEXT, KeyValue TEXT, Name TEXT, ReportingFrequency TEXT,
                                           ScheduleName TEXT, Units TEXT);
        CREATE TABLE ReportData (ReportDataIndex INTEGER, TimeIndex INTEGER, ReportDataDictionaryIndex INTEGER, Value REAL);
        """
    )
    r = "AnnualBuildingUtilityPerformanceSummary"
    con.executemany(
        "INSERT INTO TabularDataWithStrings VALUES (?, 'Entire Facility', ?, ?, ?, ?, ?)",
        [
            (r, "Building Area", "Total Building Area", "Area", "m2", "      120.00"),
            (r, "Building Area", "Net Conditioned Building Area", "Area", "m2", "      100.00"),
            (r, "Site and Source Energy", "Total Site Energy", "Total Energy", "GJ", "       36.00"),
            (r, "Site and Source Energy", "Total Site Energy", "Energy Per Total Building Area", "MJ/m2", "300.00"),
            (r, "End Uses", "Heating", "Electricity", "GJ", "7.20"),
            (r, "End Uses", "Heating", "Natural Gas", "GJ", "3.60"),
            (r, "End Uses", "Heating", "Water", "m3", "5.00"),
            (r, "End Uses", "Cooling", "Electricity", "GJ", "1.80"),
            (r, "End Uses", "Cooling", "Natural Gas", "GJ", "0.00"),
            ("OtherReport", "End Uses", "Heating", "Electricity", "GJ", "99.0"),
        ],
    )
    con.executemany("INSERT INTO Zones VALUES (?, ?, ?)", [(1, ZONE_1, 70.0), (2, ZONE_2, 50.0)])
    names = [(ZONE_1, energy.HEATING), (ZONE_1, energy.COOLING), (ZONE_2, energy.HEATING), (ZONE_2, energy.COOLING), (ZONE_1, "Zone Mean Air Temperature")]
    for i, (key, name) in enumerate(names, start=1):
        con.execute("INSERT INTO ReportDataDictionary VALUES (?, 0, 'Sum', 'HVAC', 'System', ?, ?, 'Run Period', '', 'J')", (i, key, name))
    joules = {1: 7.2e9, 2: 1.08e9, 3: 3.6e9, 4: 0.72e9, 5: 21.0}
    for i, value in joules.items():
        con.execute("INSERT INTO ReportData VALUES (?, 1, ?, ?)", (i, i, value))
    con.commit()
    con.close()


def test_energy_output_parser(tmp_path):
    sql = tmp_path / "eplusout.sql"
    _eplusout(sql)
    parsed = energy.parse_sql(sql)
    assert parsed["area_m2"] == 120.0
    assert math.isclose(parsed["site_kwh"], 10_000.0, rel_tol=1e-9)
    # Heating: 7.2 + 3.6 GJ (the water column is not energy) = 3000 kWh; cooling 1.8 GJ = 500 kWh.
    assert math.isclose(parsed["heating_kwh"], 3000.0, rel_tol=1e-9) and math.isclose(parsed["cooling_kwh"], 500.0, rel_tol=1e-9)
    assert math.isclose(parsed["eui_kwh_m2_y"], 10_000 / 120, rel_tol=1e-9)
    zones = {z["name"]: z for z in parsed["zones"]}
    assert math.isclose(zones[ZONE_1]["heating_kwh"], 2000.0) and math.isclose(zones[ZONE_1]["cooling_kwh"], 300.0)
    assert math.isclose(zones[ZONE_2]["heating_kwh"], 1000.0) and zones[ZONE_2]["floor_area_m2"] == 50.0
    # The result: summary keys §6.3 asks of energy, per-space fields keyed and named by the zones' ids.
    job = _job(tmp_path / "job", "energy", {"weather": "gbr-london-test", "period": "annual"})
    result = energy.build_result(job, parsed, job.out_dir, "24.2.0")
    assert result["summary"]["eui_kwh_m2_y"] == round(10_000 / 120, 6) and result["summary"]["heating_kwh_y"] == 3000.0
    heating = result["fields"][0]
    assert heating["name"] == "heating_kwh" and heating["on"] == "spaces" and heating["count"] == 2 and heating["keys"] == [ZONE_1, ZONE_2]
    assert (job.out_dir / heating["entities"]).read_bytes() == bytes.fromhex(ZONE_1) + bytes.fromhex(ZONE_2)
    assert common.unpack_f32((job.out_dir / heating["values"]).read_bytes()) == [2000.0, 1000.0]
    assert result["engine"]["name"] == "energyplus" and result["engine"]["version"] == "24.2.0"
    _passes(result, job, job.out_dir)


def test_energy_model_outputs_and_failures(tmp_path):
    model = {"Zone": {"Study": {}}, "Output:Variable": {"Mine": {"variable_name": "Zone Mean Air Temperature"}}}
    prepared = energy.prepare_model(model)
    assert prepared["Output:SQLite"] == {"Output:SQLite 1": {"option_type": "SimpleAndTabular"}}
    assert prepared["Output:Table:SummaryReports"]["Output:Table:SummaryReports 1"]["reports"] == [{"report_name": "AllSummary"}]
    assert {v["variable_name"] for v in prepared["Output:Variable"].values()} == {"Zone Mean Air Temperature", energy.HEATING, energy.COOLING}
    assert model["Output:Variable"] == {"Mine": {"variable_name": "Zone Mean Air Temperature"}}  # a copy
    # A job without its model: bad_input in error.json, exit 2.
    job_dir = tmp_path / "missing"
    _job(job_dir, "energy", {"weather": "x", "period": "annual"}, inputs={})
    assert common.main(energy.run, [str(job_dir)]) == 2
    assert json.loads((job_dir / "out" / "error.json").read_text())["code"] == "bad_input"
    # EnergyPlus not installed (as here): engine_error.
    job_dir = tmp_path / "noengine"
    _job(job_dir, "energy", {"weather": "x", "period": "annual"}, inputs={"model": json.dumps({"Zone": {"A": {}}}).encode(), "weather": b"LOCATION"})
    assert common.main(energy.run, [str(job_dir)]) == 3
    assert json.loads((job_dir / "out" / "error.json").read_text())["code"] == "engine_error"


# --- wind ------------------------------------------------------------------------------------------


def _box_stl(x0, y0, x1, y1, h) -> bytes:
    v = [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0), (x0, y0, h), (x1, y0, h), (x1, y1, h), (x0, y1, h)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    tris = [t for a, b, c, d in quads for t in ((v[a], v[b], v[c]), (v[a], v[c], v[d]))]
    out = bytearray(b"box".ljust(80, b" ")) + struct.pack("<I", len(tris))
    for t in tris:
        out += struct.pack("<3f", 0, 0, 0) + b"".join(struct.pack("<3f", *p) for p in t) + struct.pack("<H", 0)
    return bytes(out)


WIND = {"speed_ms": 5, "direction_deg": 270, "reference_height_m": 10, "terrain": "suburban", "comfort": "lawson"}


def test_wind_case_files(tmp_path):
    job = _job(tmp_path, "wind", WIND, inputs={"geometry": _box_stl(-5, -4, 5, 4, 6)})
    mesh = wind.read_stl(job.input("geometry"))
    assert mesh.count == 12
    # From the west (270): the wind already blows along +x; no turn needed.
    frame = wind.Frame.for_wind(mesh, 270)
    assert math.isclose(frame.angle, 0.0, abs_tol=1e-12)
    north = wind.Frame.for_wind(mesh, 0)  # from the north: flow (0, -1) turned onto +x
    flow = north.to_case((0.0, -1.0, 0.0))
    assert math.isclose(flow[0], 1.0, abs_tol=1e-9) and math.isclose(flow[1], 0.0, abs_tol=1e-9)
    p = (3.0, -2.0, 1.5)
    assert all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(north.to_model(north.to_case(p)), p))
    case_tris = [tuple(frame.to_case(v) for v in t) for t in mesh.triangles]
    files = wind.case_files(job, case_tris, job.profile)
    block = files["system/blockMeshDict"]
    # H = 6 m: 5 H upstream (-35), 15 H downstream (95), 5 H to the sides (±34), 5 H above (36); cells H/10.
    assert "(-35 -34 0) (95 -34 0)" in block and "(-35 -34 36)" in block
    assert "(217 114 60)" in block
    assert "Uref            5;" in files["0/U"] and "Zref            10;" in files["0/U"] and "z0              uniform 0.3;" in files["0/U"]
    assert "atmBoundaryLayerInletVelocity" in files["0/U"] and "atmBoundaryLayerInletK" in files["0/k"]
    assert "nutkAtmRoughWallFunction; z0 uniform 0.3" in files["0/nut"]
    assert "endTime         2000;" in files["system/controlDict"] and "p 0.0001;" in files["system/fvSolution"]  # 1.2.0 §6.5.4
    assert "level (2 3)" in files["system/snappyHexMeshDict"] and "building.stl" in files["system/snappyHexMeshDict"]
    assert "RASModel realizableKE;" in files["constant/turbulenceProperties"]  # 1.2.0: realizable k-epsilon by default
    # The inlet's log law: the reference speed at the reference height, rising with height.
    assert math.isclose(wind.log_law_speed(10, 5, 10, 0.3), 5.0)
    assert wind.log_law_speed(2, 5, 10, 0.3) < wind.log_law_speed(20, 5, 10, 0.3)
    classes = job.profile["lawson"]["classes"]
    # 1.2.0's LDDC thresholds 4 / 6 / 8 / 10 m/s (sitting, standing, strolling, business walking, uncomfortable).
    assert [wind.lawson_class(s, classes) for s in (0, 4.0, 4.01, 6.0, 8.0, 10.0, 10.01, 30)] == [0, 0, 1, 1, 2, 3, 4, 4]


def test_wind_sampling_and_result(tmp_path):
    raw = "#  x  y  z  p\n0.5 0 3 -2.0\n4.9 0 3 1.25\n# done\nbad line\n"
    rows = wind.parse_raw(raw, 1)
    assert rows == [(0.5, 0.0, 3.0, -2.0), (4.9, 0.0, 3.0, 1.25)]
    assert wind.match_nearest([(4.8, 0.1, 3.0), (0.0, 0.0, 3.0)], rows, 1.0) == [rows[1], rows[0]]
    points = [(0.0, 0.0, 1.5), (0.5, 0.0, 1.5), (9.0, 9.0, 1.5)]
    u_rows = [(0.0001, 0.0, 1.5, 3.0, 4.0, 0.0), (0.5, 0.0002, 1.5, 0.0, 6.0, 8.0)]
    assert wind.grid_speeds(points, u_rows, 0.5) == [5.0, 10.0, None]
    job = _job(tmp_path, "wind", WIND, inputs={"geometry": _box_stl(-5, -4, 5, 4, 6)})
    mesh = wind.read_stl(job.input("geometry"))
    # PF11c: the origin is the centre of cell (0, 0), and build_result takes the velocities (model frame).
    grid = wind.Grid((-22.0, -21.0), 2.0, 3, 2, 1.5)
    speeds = [2.0, 5.0, None, 7.5, 9.0, 3.0]
    vectors = [None if s is None else (s, 0.0, 0.0) for s in speeds]
    cp = [0.8, -0.5, -1.2, 0.1, 0.0, -0.3] * 2
    info = {"cells": 120000, "iterations": 640, "converged": True, "residual": 9.5e-05}
    result = wind.build_result(job, mesh, cp, grid, vectors, None, job.out_dir, info)
    lawson = next(g for g in result["grids"] if g["name"] == "comfort_lawson")
    assert list((job.out_dir / lawson["values"]).read_bytes()) == [0, 1, 255, 2, 3, 0]  # 1.2.0's LDDC classes
    ratio = common.unpack_f32((job.out_dir / next(g for g in result["grids"] if g["name"] == "speed_ratio")["values"]).read_bytes())
    assert ratio[0] == 0.4 or math.isclose(ratio[0], 0.4, rel_tol=1e-6)
    assert math.isnan(ratio[2])
    assert lawson["origin_mm"] == [-22000.0, -21000.0, 1500.0] and lawson["cell_mm"] == 2000.0
    field = result["fields"][0]
    assert (job.out_dir / field["entities"]).read_bytes() == bytes(16 * 12)
    assert result["summary"] == {"max_speed_ms": 9.0, "max_speed_ratio": 1.8, "min_cp": -1.2, "max_cp": 0.8, "cells": 120000,
                                 "iterations": 640, "converged": 1, "residual": 9.5e-05}
    _passes(result, job, job.out_dir, geometry_triangles=12)
    # With the uploaded ids, those are what the field names.
    ids = b"".join(bytes([i]) * 16 for i in range(12))
    with_ids = wind.build_result(job, mesh, cp, grid, vectors, ids, job.out_dir, info)
    assert (job.out_dir / with_ids["fields"][0]["entities"]).read_bytes() == ids


def test_wind_main_reports_bad_input(tmp_path):
    _job(tmp_path, "wind", WIND, inputs={})
    assert common.main(wind.run, [str(tmp_path)]) == 2
    assert json.loads((tmp_path / "out" / "error.json").read_text())["code"] == "bad_input"
    _job(tmp_path / "ascii", "wind", WIND, inputs={"geometry": b"solid x\nendsolid x\n"})
    assert common.main(wind.run, [str(tmp_path / "ascii")]) == 2
    _job(tmp_path / "ids", "wind", WIND, inputs={"geometry": _box_stl(0, 0, 1, 1, 3), "entities": b"\0" * 15})
    assert common.main(wind.run, [str(tmp_path / "ids")]) == 2
    # With valid inputs and no OpenFOAM installed (as here): engine_error.
    _job(tmp_path / "noengine", "wind", WIND, inputs={"geometry": _box_stl(0, 0, 4, 3, 3)})
    assert common.main(wind.run, [str(tmp_path / "noengine")]) == 3


# --- acoustics -------------------------------------------------------------------------------------


def _shoebox(x1, y1, z1, alpha, scattering) -> dict:
    q = [
        [[0, 0, 0], [x1, 0, 0], [x1, y1, 0], [0, y1, 0]], [[0, 0, z1], [0, y1, z1], [x1, y1, z1], [x1, 0, z1]],
        [[0, 0, 0], [0, 0, z1], [x1, 0, z1], [x1, 0, 0]], [[0, y1, 0], [x1, y1, 0], [x1, y1, z1], [0, y1, z1]],
        [[0, 0, 0], [0, y1, 0], [0, y1, z1], [0, 0, z1]], [[x1, 0, 0], [x1, 0, z1], [x1, y1, z1], [x1, y1, 0]],
    ]
    return {"id": "0199c6a2e00070028000000000000001", "name": "Hall", "surfaces": [{"vertices_m": v, "absorption": alpha, "scattering": scattering} for v in q]}


def test_acoustics_shoebox_against_eyring(tmp_path):
    bands = [500]
    params = {"bands": bands, "sources": [{"position_m": [3, 2.5, 1.5], "power_db": 90}], "rays": 1500, "receiver_grid_m": 3.0, "receiver_height_m": 1.2}
    profile = {**kinds.profile("acoustics"), "receiver_radius_m": 0.5}
    room = acoustics.room_from(_shoebox(10, 8, 3, 0.2, 1.0), bands, 0)
    assert len(room.tris) == 12 and math.isclose(room.area, 268.0)
    first = acoustics.analyse([room], params["sources"], params, profile, rays=1500, seed=3)
    # Eyring's reverberation time for a diffuse field: 0.161 V / (−S ln(1 − α)).
    eyring = 0.161 * 240 / (-268 * math.log(0.8))
    t30 = first["rooms"][0]["t30"][0]
    assert abs(t30 - eyring) / eyring < 0.2, (t30, eyring)
    # The level near the diffuse-field estimate Lw + 10 lg(4 / A) (A = Eyring's absorption area), A-weighted at 500 Hz.
    expected = 90 + 10 * math.log10(4 / (-268 * math.log(0.8))) - 3.2
    levels = [x for x in first["rooms"][0]["spl_dba"] if math.isfinite(x)]
    assert abs(sum(levels) / len(levels) - expected) < 3.0
    # Deterministic for a seed.
    again = acoustics.analyse([acoustics.room_from(_shoebox(10, 8, 3, 0.2, 1.0), bands, 0)], params["sources"], params, profile, rays=1500, seed=3)
    assert again["rooms"][0]["t30"] == first["rooms"][0]["t30"]
    job = _job(tmp_path, "acoustics", params, profile=profile)
    result = acoustics.build_result(job, first, job.out_dir)
    names = [f["name"] for f in result["fields"]]
    assert names == ["t30_500", "edt_500"] and result["fields"][0]["keys"] == ["Hall"]
    assert (job.out_dir / result["fields"][0]["entities"]).read_bytes() == bytes.fromhex("0199c6a2e00070028000000000000001")
    assert result["grids"][0]["name"] == "spl_dba" and result["grids"][0]["unit"] == "dB(A)"
    assert result["summary"]["t30_500_s"] == round(t30, 6)
    _passes(result, job, job.out_dir)


def test_acoustics_decay_and_inputs(tmp_path):
    # An exponential decay of 60 dB a second: T30 and EDT are 1 s.
    hist = [10 ** (-6 * (i / 1000)) for i in range(2000)]
    t30, edt = acoustics.decay_times(hist)
    assert abs(t30 - 1.0) < 0.02 and abs(edt - 1.0) < 0.02
    assert all(math.isnan(x) for x in acoustics.decay_times([0.0] * 10))
    bad = {"schema": "truebex-acoustics-rooms/1", "rooms": [{"surfaces": [{"vertices_m": [[0, 0, 0], [1, 0, 0], [0, 1, 0]], "absorption": 2}] * 4}]}
    params = {"bands": [500], "sources": [{"position_m": [0.2, 0.2, 0.1]}], "rays": 1000}
    _job(tmp_path, "acoustics", params, inputs={"rooms": json.dumps(bad).encode()})
    assert common.main(acoustics.run, [str(tmp_path)]) == 2
    assert "absorption" in json.loads((tmp_path / "out" / "error.json").read_text())["message"]


# --- the images ------------------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
IMAGES = ROOT / "infra" / "worker" / "analysis"


def test_analysis_images_are_non_root_and_run_their_runner():
    import shutil
    import subprocess

    for kind in ("wind", "energy", "acoustics", "texture", "airflow"):
        text = (IMAGES / kind / "Dockerfile").read_text("utf-8")
        assert "COPY runners /opt/truebex/runners" in text and "COPY run.sh /opt/truebex/run.sh" in text, kind
        assert "USER 1000" in text and f'ENTRYPOINT ["/opt/truebex/run.sh", "{kind}"]' in text, kind
        assert f"-Kind {kind}" in (IMAGES / kind / "build.ps1").read_text("utf-8")
        # The profile names the image the wrapper runs by default.
        assert kinds.profile(kind)["image"] == f"truebex-analysis-{kind}:1"
    assert "opencfd/openfoam-default:2406" in (IMAGES / "wind" / "Dockerfile").read_text("utf-8")
    assert "sha256sum -c" in (IMAGES / "energy" / "Dockerfile").read_text("utf-8")
    run_sh = (IMAGES / "run.sh").read_bytes()
    assert b"python3 -m \"runners.$KIND\"" in run_sh
    if shutil.which("powershell"):
        for script in [IMAGES / "build.ps1", *[IMAGES / k / "build.ps1" for k in ("wind", "energy", "acoustics", "texture", "airflow")]]:
            cmd = (
                "$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile("
                f"'{script}', [ref]$null, [ref]$e); if ($e.Count) {{ $e | % {{ $_.Message }}; exit 1 }}"
            )
            res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=60)
            assert res.returncode == 0, (script, res.stdout, res.stderr)
