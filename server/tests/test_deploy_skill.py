"""The deploy skill carries every release step and secret (PF14a).

Reads `.claude/skills/truebex-deploy/SKILL.md`; no build needed. A feature that
adds a release step, a billing or licence setting or a VM secret fails here
until the skill tells the owner how to run or set it.
"""

import json
import re
from pathlib import Path

from app.config import Settings

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / ".claude" / "skills" / "truebex-deploy" / "SKILL.md"
SECRET_TEMPLATES = ROOT / "infra" / "secrets"

# config.py settings the owner sets per environment for billing and licences.
BILLING_AND_LICENCE = ("billing_", "paddle_", "stripe_", "wayl_", "licence_", "release_", "signing_")
# A template variable holding a credential (VM secrets folder).
SECRET_NAME = re.compile(r"(KEY|KEYS|SECRET|PASSWORD|TOKEN)(_ID)?$")


def _skill() -> str:
    return SKILL.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    start = text.index(f"\n## {heading}")
    end = text.find("\n## ", start + 1)
    return text[start : end if end >= 0 else len(text)]


def _settings(prefixes: tuple[str, ...]) -> list[str]:
    return sorted(name.upper() for name in Settings.model_fields if name.startswith(prefixes))


def _missing(names, text: str) -> list[str]:
    return [n for n in names if not re.search(rf"(?<![A-Z0-9_]){re.escape(n)}(?![A-Z0-9_])", text)]


def test_deploy_skill_names_release_steps():
    text = _skill()
    for step in (
        "npm run sync:releases",
        "npm run sync:roadmap",
        "sync_prices.py",
        "prices_final",
        "npm run indexnow -- --sitemap",
        "publish_release.py",
    ):
        assert step in text, step
    # The release-publishing command names the symbols flag.
    releases = _section(text, "App releases")
    assert re.search(r"publish_release\.py(?:(?!\n\n).)*?--symbols \S", releases, re.S)
    # sync_prices.py: a dry run first, against the target environment.
    assert re.search(r"sync_prices[^\n]*--dry-run", text)
    assert re.search(r"sync_prices[^\n]*--env production", text)


def test_deploy_skill_website_steps_in_order():
    website = _section(_skill(), "Website")
    order = [
        "npm run sync:releases",
        "npm run sync:roadmap",
        "prices_final",
        "sync_prices",
        "npm run build",
        "git push origin main",
        "npm run indexnow -- --sitemap",
    ]
    at = [website.find(step) for step in order]
    assert -1 not in at, dict(zip(order, at))
    assert at == sorted(at), dict(zip(order, at))


def test_deploy_skill_sync_roadmap_names_both_trackers():
    # The script takes the app tracker first, then the platform tracker.
    script = (ROOT / "scripts" / "sync-roadmap.mjs").read_text(encoding="utf-8")
    assert "<app tracker README.md> <platform tracker README.md>" in script
    line = next(ln for ln in _skill().splitlines() if "npm run sync:roadmap --" in ln)
    norm = line.replace("\\", "/")
    app = norm.lower().find("truebex_compact/docs/roadmap/40/readme.md")
    platform = norm.find(" docs/roadmap/40/README.md")
    assert 0 <= app < platform, line


def test_deploy_skill_names_every_paddle_setting():
    names = _settings(("paddle_",))
    assert {"PADDLE_ENV", "PADDLE_API_KEY", "PADDLE_WEBHOOK_SECRET", "PADDLE_CLIENT_TOKEN"} <= set(names)
    assert _missing(names, _skill()) == []


def test_deploy_skill_names_every_billing_and_licence_setting():
    text = _skill()
    names = _settings(BILLING_AND_LICENCE)
    assert {"BILLING_PROVIDER", "WAYL_ENABLED", "LICENCE_SIGNING_KEY", "RELEASE_PUBLIC_KEYS"} <= set(names)
    assert _missing(names, text) == []
    # Paddle is the default provider; Wayl is dormant behind its switch.
    assert "BILLING_PROVIDER=paddle" in text
    assert "WAYL_ENABLED=false" in text


def test_deploy_skill_names_every_vm_secret():
    text = _skill()
    assert "/opt/truebex/secrets/" in text
    names = set()
    for template in sorted(SECRET_TEMPLATES.glob("*.env.example")):
        assert template.name.replace(".env.example", ".sops.env") in text, template.name
        for line in template.read_text(encoding="utf-8").splitlines():
            name = line.split("=", 1)[0].strip()
            if "=" in line and not line.lstrip().startswith("#") and SECRET_NAME.search(name):
                names.add(name)
    assert {"SECRET_KEY", "S3_SECRET_ACCESS_KEY", "SMTP_PASSWORD", "POSTGRES_PASSWORD", "WALG_LIBSODIUM_KEY"} <= names
    assert _missing(sorted(names), text) == []


def test_deploy_skill_site_config_keys_exist():
    text = _skill()
    constants = (ROOT / "src" / "lib" / "constants.ts").read_text(encoding="utf-8")
    for key in ("ANALYTICS.cloudflareToken", "VERIFICATION.google", "VERIFICATION.bing", "SOCIAL"):
        assert key in text, key
    assert re.search(r"export const ANALYTICS = \{\s*cloudflareToken:", constants)
    assert re.search(r"export const VERIFICATION = \{\s*google:[^}]*bing:", constants)
    assert "export const SOCIAL" in constants
    for owner_step in ("Cloudflare", "Web Analytics", "Search Console", "Bing Webmaster Tools", "sitemap.xml"):
        assert owner_step in text, owner_step


def test_deploy_skill_live_checks():
    text = _skill()
    for route in ("/pricing/", "/changelog/", "/download/", "/checkout/"):
        assert route in text, route
        assert (ROOT / "src" / "app" / route.strip("/")).is_dir(), route
    assert re.search(r"/checkout/[^\n]*noindex", text)
    assert "/billing/plans" in text


def test_deploy_skill_commands_exist():
    """Every npm script and server script the skill names exists."""
    text = _skill()
    scripts = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["scripts"]
    for name in set(re.findall(r"npm run ([\w:-]+)", text)):
        assert name in scripts, f"npm run {name}"
    py = set(re.findall(r"scripts[\\/](\w+)\.py", text)) | set(re.findall(r"-m scripts\.(\w+)", text))
    assert {"publish_release", "sync_prices", "upload_symbols"} <= py
    for name in py:
        assert (ROOT / "server" / "scripts" / f"{name}.py").exists() or (ROOT / "scripts" / f"{name}.py").exists(), name
