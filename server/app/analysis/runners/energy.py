"""The `energy` runner: EnergyPlus on the uploaded epJSON model (PF11).

    python3 -m runners.energy /job

1. The model AN2 wrote (`inputs/model`, epJSON) gets the outputs this runner
   reads: `Output:SQLite` (SimpleAndTabular), the AllSummary tables and, per
   zone at run-period frequency, `Zone Air System Sensible Heating Energy`
   and `... Cooling Energy`. Everything else in the model is left as AN2 wrote it.
2. `energyplus --weather inputs/weather --output-directory run model.epJSON`
   (the weather file is the library's EPW the job's `params.weather` named).
3. `parse_sql` reads `run/eplusout.sql`: the building area, total site energy
   and the heating and cooling end uses from the annual building utility
   performance summary, and each zone's heating and cooling from the report data.
4. The result: `summary` {eui_kwh_m2_y, heating_kwh_y, cooling_kwh_y,
   floor_area_m2, site_energy_kwh_y}; fields on `spaces` heating_kwh and
   cooling_kwh (one value per zone, `keys` = zone names, `entities` when the
   zones are named by their 32-hex space ids).
"""

from __future__ import annotations

import copy
import json
import re
import sqlite3
import sys
from pathlib import Path

if __package__ in (None, ""):  # pragma: no cover - `python3 runners/energy.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "runners"

from . import common

GJ_KWH = 1e9 / 3.6e6  # 277.78 kWh per GJ
J_KWH = 1 / 3.6e6
REPORT = "AnnualBuildingUtilityPerformanceSummary"
HEATING = "Zone Air System Sensible Heating Energy"
COOLING = "Zone Air System Sensible Cooling Energy"
DEFAULT_VERSION = "24.2"


def prepare_model(model: dict) -> dict:
    """The model with the outputs `parse_sql` reads added (a copy)."""
    m = copy.deepcopy(model)
    m["Output:SQLite"] = {"Output:SQLite 1": {"option_type": "SimpleAndTabular"}}
    reports = m.setdefault("Output:Table:SummaryReports", {})
    if not reports:
        reports["Output:Table:SummaryReports 1"] = {"reports": [{"report_name": "AllSummary"}]}
    variables = m.setdefault("Output:Variable", {})
    for name in (HEATING, COOLING):
        variables[f"Truebex {name}"] = {"key_value": "*", "variable_name": name, "reporting_frequency": "RunPeriod"}
    return m


def _number(value) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def parse_sql(path: str | Path) -> dict:
    """Read EnergyPlus's SQLite output (see the module docstring)."""
    path = Path(path)
    if not path.is_file():
        raise common.EngineError("EnergyPlus wrote no eplusout.sql")
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        def table(name: str, row: str) -> list[tuple[str, str, float]]:
            rows = con.execute(
                "SELECT ColumnName, Units, Value FROM TabularDataWithStrings WHERE ReportName = ? AND TableName = ? AND RowName = ?",
                (REPORT, name, row),
            ).fetchall()
            return [(str(c or "").strip(), str(u or "").strip(), v) for c, u, v in rows if _number(v) is not None]

        def first(name: str, row: str, column: str) -> float:
            for col, _units, value in table(name, row):
                if col == column:
                    return float(_number(value))
            raise common.EngineError(f"eplusout.sql has no {name} / {row} / {column}")

        area = first("Building Area", "Total Building Area", "Area")
        site = first("Site and Source Energy", "Total Site Energy", "Total Energy") * GJ_KWH

        def end_use(row: str) -> float:
            return sum(float(_number(v)) for _c, units, v in table("End Uses", row) if units == "GJ") * GJ_KWH

        heating, cooling = end_use("Heating"), end_use("Cooling")
        zones = [(str(n).strip(), float(a or 0)) for n, a in con.execute("SELECT ZoneName, FloorArea FROM Zones ORDER BY ZoneIndex")]
        per: dict[tuple[str, str], float] = {}
        for key, name, total in con.execute(
            "SELECT d.KeyValue, d.Name, SUM(r.Value) FROM ReportData r "
            "JOIN ReportDataDictionary d ON r.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex "
            "WHERE d.Name IN (?, ?) GROUP BY d.KeyValue, d.Name",
            (HEATING, COOLING),
        ):
            per[(str(key).strip().upper(), name)] = float(total or 0) * J_KWH
    except sqlite3.Error as exc:
        raise common.EngineError(f"eplusout.sql could not be read: {exc}") from None
    finally:
        con.close()
    return {
        "area_m2": area,
        "site_kwh": site,
        "heating_kwh": heating,
        "cooling_kwh": cooling,
        "eui_kwh_m2_y": site / area if area > 0 else 0.0,
        "zones": [
            {
                "name": name,
                "floor_area_m2": floor,
                "heating_kwh": per.get((name.upper(), HEATING), 0.0),
                "cooling_kwh": per.get((name.upper(), COOLING), 0.0),
            }
            for name, floor in zones
        ],
    }


def build_result(job: common.Job, parsed: dict, out_dir: Path, version: str = DEFAULT_VERSION) -> dict:
    zones = parsed["zones"]
    if not zones:
        raise common.EngineError("the model's run reported no zones")
    names = [z["name"] for z in zones]
    ids = common.space_ids(names)
    fields = [
        common.field(out_dir, "heating_kwh", "kWh", "spaces", [z["heating_kwh"] for z in zones], entities=ids, keys=names),
        common.field(out_dir, "cooling_kwh", "kWh", "spaces", [z["cooling_kwh"] for z in zones], entities=ids, keys=names),
    ]
    summary = {
        "eui_kwh_m2_y": parsed["eui_kwh_m2_y"],
        "heating_kwh_y": parsed["heating_kwh"],
        "cooling_kwh_y": parsed["cooling_kwh"],
        "floor_area_m2": parsed["area_m2"],
        "site_energy_kwh_y": parsed["site_kwh"],
        "zones": len(zones),
    }
    return common.result(job, common.engine("energyplus", version, "energy"), summary, fields, [])


def engine_version() -> str:
    try:
        lines = common.run_command(["energyplus", "--version"], cwd=Path("."), echo=False)
    except common.RunnerError:
        return DEFAULT_VERSION
    m = re.search(r"Version\s+(\d+\.\d+(?:\.\d+)?)", " ".join(lines))
    return m.group(1) if m else DEFAULT_VERSION


def run(job: common.Job) -> None:
    out = job.out_dir
    model = common.read_json(job.input("model"), "model")
    if not isinstance(model.get("Zone"), dict) or not model["Zone"]:
        raise common.BadInput("the model has no Zone")
    weather = job.input("weather")
    work = job.dir / "energy"
    run_dir = work / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    model_path = work / "model.epJSON"
    model_path.write_text(json.dumps(prepare_model(model)), encoding="utf-8")
    common.progress(out, 0.05, "simulating the year")
    days = {"n": 0}

    def on_line(line: str) -> None:
        if "Continuing Simulation at" in line or "Starting Simulation at" in line:
            days["n"] += 1
            common.progress(out, min(0.9, 0.05 + days["n"] / 400), "simulating the year")

    common.run_command(
        ["energyplus", "--weather", str(weather), "--output-directory", str(run_dir), str(model_path)],
        cwd=work, log_path=work / "energyplus.log", on_line=on_line,
    )
    common.progress(out, 0.95, "reading the results")
    result = build_result(job, parse_sql(run_dir / "eplusout.sql"), out, engine_version())
    common.write_result(out, result)
    common.progress(out, 1.0, "done")


if __name__ == "__main__":
    sys.exit(common.main(run))
