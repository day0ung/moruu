"""장기 토큰(60일) 갱신 — 50일 지나면 갱신하고 .env 또는 GitHub Secret 에 저장."""
from __future__ import annotations

import subprocess
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path

REFRESH_AFTER_DAYS = 50


def needs_refresh(issued: date, today: date) -> bool:
    return (today - issued).days >= REFRESH_AFTER_DAYS


def update_env_file(path: Path, updates: dict[str, str], remove: Iterable[str] = ()) -> None:
    drop = set(remove)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen, out = set(), []
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if "=" in line and key in drop:
            continue
        if "=" in line and key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in updates.items() if k not in seen]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def persist_token(token: str, issued: date, *, env_path: Path, environ: Mapping[str, str],
                  run=subprocess.run) -> None:
    updates = {"THREADS_ACCESS_TOKEN": token, "THREADS_TOKEN_ISSUED": issued.isoformat()}
    if environ.get("GITHUB_ACTIONS") == "true":
        gh_env = {**environ, "GH_TOKEN": environ["GH_PAT"]}
        for key, value in updates.items():
            run(["gh", "secret", "set", key, "--repo", environ["GITHUB_REPOSITORY"]],
                input=value, text=True, check=True, capture_output=True, env=gh_env)
    else:
        update_env_file(env_path, updates)
