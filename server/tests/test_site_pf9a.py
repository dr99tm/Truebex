"""PF9a: an edit an agent made (the assistant, or an API key through /v1:
project-log §6.2 `author_kind` agent) is named with one label on the web and
on Android, not as "Someone". The copy checks read the sources; the build
checks read out/ after the verify gate's `npm run build` (skipped when out/ is
absent, e.g. a server-only test run)."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
ANDROID = ROOT / "mobile" / "android"
L10N = ANDROID / "lib" / "l10n"

AGENT = "An assistant or script"
CONFLICT = "{name} changed this first — your edit was replaced"
# Brand voice: the label names no other product, assistant or engine.
OTHER_NAMES = re.compile(
    r"\b(claude|chatgpt|gpt|copilot|gemini|openai|anthropic|siri|alexa|cortana|unreal|unity|bot|ai)\b", re.I
)

needs_out = pytest.mark.skipif(not (OUT / "index.html").exists(), reason="out/ not built (run npm run build)")


def _app_copy() -> str:
    constants = (ROOT / "src" / "lib" / "constants.ts").read_text("utf-8")
    return constants.split("export const APP = {", 1)[1].split("} as const;", 1)[0]


def _top_string(block: str, key: str) -> str:
    """A top-level string of the APP object (two-space indent)."""
    found = re.search(rf'^  {key}: "([^"]*)",$', block, re.M)
    assert found, key
    return found.group(1)


def test_site_pf9a_one_agent_label_on_web_and_android():
    app = _app_copy()
    assert _top_string(app, "agentAuthor") == AGENT
    assert _top_string(app, "someone") == "Someone"
    assert _top_string(app, "conflict") == CONFLICT
    arb = json.loads((L10N / "app_en.arb").read_text("utf-8"))
    assert arb["agentAuthor"] == AGENT
    assert arb["someone"] == "Someone"
    assert arb["conflict"] == CONFLICT
    assert not OTHER_NAMES.search(AGENT)
    # The Dart strings are generated from the ARB (flutter gen-l10n), never edited by hand.
    generated = (L10N / "app_localizations_en.dart").read_text("utf-8")
    assert f"String get agentAuthor => '{AGENT}';" in generated
    assert "String get agentAuthor;" in (L10N / "app_localizations.dart").read_text("utf-8")


def test_site_pf9a_clients_carry_author_kind():
    # The web outbox keeps the winner's author_kind and names a rejection through one rule.
    outbox = (ROOT / "src" / "viewer" / "outbox.ts").read_text("utf-8")
    assert "author_kind: w.author_kind" in outbox
    assert "export function conflictLine(" in outbox
    panels = (ROOT / "src" / "components" / "app" / "ProjectPanels.tsx").read_text("utf-8")
    assert "conflictLine(" in panels and "APP.agentAuthor" in panels
    # Android: the winner and the history items carry it; the notification text has the label.
    assert "authorKind" in (ANDROID / "lib" / "outbox" / "outbox.dart").read_text("utf-8")
    assert "final String authorKind;" in (ANDROID / "lib" / "replica" / "replica.dart").read_text("utf-8")
    assert "agent: s.agentAuthor" in (ANDROID / "lib" / "services.dart").read_text("utf-8")


@needs_out
def test_site_pf9a_app_bundle_carries_agent_label():
    html = (OUT / "app" / "project" / "index.html").read_text("utf-8")
    scripts = re.findall(r'src="(/_next/static/[^"]+\.js)"', html)
    assert scripts
    carrying = [s for s in scripts if AGENT in (OUT / s.lstrip("/")).read_text("utf-8", errors="ignore")]
    assert carrying, "no script of /app/project/ carries the agent label"


@needs_out
def test_site_pf9a_selftest_names_authors():
    node = shutil.which("node")
    assert node, "node is needed for the PF9 self-tests"
    run = subprocess.run([node, str(OUT / "viewer" / "selftest.mjs")], capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "authors" in run.stdout and "checks passed" in run.stdout
