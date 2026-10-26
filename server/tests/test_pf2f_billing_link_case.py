"""PF2f: the billing page reads a link's ?tier= and ?plan= without (ASCII) case.

The app's "See plans" opens /dashboard/billing/?plan=<plan> with the plan
written by FName::ToString, and a packaged build does not keep an FName's
case (`team` comes out as `Team`). src/lib/billing-link.ts linkedTierId
answers the tier id a link asks for; server/tests/billing_link.cjs runs it
with the project's own TypeScript and says what the page then preselects
(the tier shown, the interval it is sold at, the seats and the unit price),
beside what master's exact reading gave (`before`)."""

import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlencode

import pytest

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "src" / "app" / "dashboard" / "billing" / "page.tsx"
CATALOGUE = ROOT / "server" / "app" / "catalogue.json"

KELVIN = chr(0x212A)  # lower-cases to an ASCII "k" in JavaScript and Python
GREEK_EPSILON = chr(0x0395)


def _link(cases: list[tuple[dict, bool]], tmp_path: Path) -> list[dict]:
    """Each (query parameters, organisation?) through billing_link.cjs."""
    exe = shutil.which("node")
    if not exe:
        pytest.skip("node not on PATH")
    if not (ROOT / "node_modules" / "typescript").exists():
        pytest.skip("node_modules not installed")
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([{"query": urlencode(q), "org": org} for q, org in cases]), encoding="utf-8")
    res = subprocess.run(
        [exe, str(ROOT / "server" / "tests" / "billing_link.cjs"), str(path)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=180,
    )  # fmt: skip
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def _shown(answer: dict) -> tuple:
    return answer["tier"], answer["interval"], answer["seats"], answer["unit"]


def test_pf2f_plan_in_any_case_preselects_its_tier(tmp_path):
    """?plan=Team (a Shipping build's link), TEAM and tEaM preselect Team, and
    ?plan=Pro Pro, exactly as the lower-case link does: the same tier,
    interval (Team is annual only), seats (Team's minimum 2) and price."""
    spellings = ["Team", "TEAM", "tEaM", "team", "Pro", "pro"]
    got = dict(zip(spellings, _link([({"plan": s}, False) for s in spellings], tmp_path)))
    for s in ("Team", "TEAM", "tEaM"):
        assert got[s]["id"] == "team", s
        assert _shown(got[s]) == _shown(got["team"]) == ("team", "year", 2, 119000), s
        assert got[s]["before"]["tier"] == "pro", s  # master: the first buyable tier
    assert got["Pro"]["id"] == "pro"
    assert _shown(got["Pro"]) == _shown(got["pro"]) == ("pro", "month", 1, 2400)


def test_pf2f_tier_in_any_case_and_tier_before_plan(tmp_path):
    """?tier= in any case the same, with ?interval=, ?currency= and ?seats=
    applied to the preselected tier as for the lower-case link; ?tier= wins
    over ?plan=."""
    queries = [
        {"tier": "Studio"},
        {"tier": "studio"},
        {"tier": "team", "plan": "Pro"},
        {"tier": "Team", "plan": "pro"},
        {"tier": "TEAM", "interval": "month", "currency": "usd", "seats": "5"},
        {"tier": "team", "interval": "month", "currency": "usd", "seats": "5"},
        {"tier": "Studio", "interval": "year", "currency": "EUR"},
        {"tier": "studio", "interval": "year", "currency": "EUR"},
    ]
    studio, studio_lc, team_over_pro, team_over_pro_lc, team5, team5_lc, studio_y, studio_y_lc = _link(
        [(q, False) for q in queries], tmp_path
    )
    assert studio["id"] == "studio" and _shown(studio) == _shown(studio_lc) == ("studio", "month", 1, 7900)
    assert team_over_pro["id"] == team_over_pro_lc["id"] == "team"
    assert _shown(team_over_pro) == _shown(team_over_pro_lc) == ("team", "year", 2, 119000)
    assert team5["id"] == "team" and _shown(team5) == _shown(team5_lc)
    assert _shown(team5)[:3] == ("team", "year", 5)  # annual only, the link's seats
    assert studio_y["id"] == "studio" and _shown(studio_y) == _shown(studio_y_lc)
    assert _shown(studio_y)[:2] == ("studio", "year")
    assert studio["before"]["tier"] == team5["before"]["tier"] == "pro"  # master's reading


def test_pf2f_lower_case_links_unchanged(tmp_path):
    """The links that already worked answer exactly what master answered: the
    pricing page's ?tier=<id>&interval=&currency= for every buyable tier,
    interval and currency (TierCards.tsx), the app's editor builds' ?plan=pro,
    and no parameter (Pro, or Team for an organisation). The catalogue's ids
    are lower-case ASCII, so the lower-cased value is the id."""
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    assert all(re.fullmatch(r"[a-z]+", t["id"]) for t in catalogue["tiers"])
    buyable = [t["id"] for t in catalogue["tiers"] if t["purchasable"]]
    assert buyable == ["pro", "studio", "team"]
    pricing = [
        {"tier": tid, "interval": iv, "currency": cur}
        for tid in buyable
        for iv in ("month", "year")
        for cur in catalogue["currencies"]
    ]
    cases = [(q, False) for q in pricing] + [({"plan": "pro"}, False), ({}, False), ({}, True), ({"plan": "pro"}, True)]
    answers = _link(cases, tmp_path)
    for (q, org), a in zip(cases, answers):
        before = a.pop("before")
        assert a == before, (q, org)
    assert [a["tier"] for a in answers[: len(pricing)]] == [q["tier"] for q in pricing]
    no_param, for_org = answers[-3], answers[-2]
    assert no_param["id"] == "pro" and for_org["id"] == "team"
    assert _shown(for_org) == ("team", "year", 2, 119000)


def test_pf2f_not_a_buyable_tier_as_before(tmp_path):
    """A value that names no buyable tier shows the first buyable tier, as on
    master: a misspelling (Teams), free and enterprise in any case (not
    purchasable), and an empty value, which today also wins over the
    organisation's default and over ?plan=."""
    queries = [
        ({"plan": "Teams"}, False),
        ({"plan": "Teams"}, True),
        ({"plan": "enterprise"}, False),
        ({"plan": "Enterprise"}, True),
        ({"plan": "free"}, False),
        ({"plan": "Free"}, False),
        ({"plan": ""}, False),
        ({"plan": ""}, True),
        ({"tier": "", "plan": "Team"}, False),
        ({"tier": " team"}, False),
    ]
    for (q, org), a in zip(queries, _link(queries, tmp_path)):
        assert a["tier"] == a["before"]["tier"] == "pro", (q, org)
        assert _shown(a) == _shown(a["before"]), (q, org)
    empty = _link([({"plan": ""}, True)], tmp_path)[0]
    assert empty["id"] == empty["before"]["id"] == ""


def test_pf2f_non_ascii_value_passed_through(tmp_path):
    """Only an all-ASCII value is lower-cased (PF14f's enums.canonical rule):
    JavaScript's toLowerCase folds the Kelvin sign to "k" and the Greek
    capital epsilon to its small letter, so such a value is answered as given
    and matches no tier, as today."""
    values = ["TEAM" + KELVIN, "T" + GREEK_EPSILON + "AM", "Stud" + KELVIN + "io"]
    for v in values:
        assert v.lower() != v and not v.isascii()
    for v, a in zip(values, _link([({"plan": v}, False) for v in values], tmp_path)):
        assert a["id"] == v, ascii(v)
        assert a["tier"] == a["before"]["tier"] == "pro", ascii(v)
    tier = _link([({"tier": "Team" + KELVIN, "plan": "team"}, False)], tmp_path)[0]
    assert tier["id"] == "Team" + KELVIN and tier["tier"] == "pro"


def test_pf2f_page_reads_the_tier_through_the_helper():
    """page.tsx takes its tierId from linkedTierId and no longer reads
    ?tier= or ?plan= itself; the other parameters are read as before."""
    src = PAGE.read_text(encoding="utf-8")
    assert 'params.get("plan")' not in src
    assert 'params.get("tier")' not in src
    assert re.search(r'^import \{ linkedTierId \} from "@/lib/billing-link";$', src, re.M)
    assert re.search(r"useState<string>\(\s*linkedTierId\(params, org !== null\)\s*\)", src)
    for kept in (
        'params.get("interval") === "year" ? "year" : "month"',
        'params.get("currency")?.toUpperCase() ?? localeCurrency()',
        'Math.floor(Number(params.get("seats")) || 0)',
        'useState(params.get("code") ?? "")',
        'const returned = params.get("checkout");',
        'const tier = buyable.find((t) => t.id === tierId) ?? buyable[0];',
    ):
        assert kept in src, kept
