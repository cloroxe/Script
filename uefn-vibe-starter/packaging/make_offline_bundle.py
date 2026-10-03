"""Rassemble les paquets Windows (wheels) pour construire / installer SANS Internet.

À lancer sur une machine avec Internet, avec Python 3.11+ et `uv` (pip install uv) :
    python packaging/make_offline_bundle.py --python-version 3.14 --python-version 3.13

Crée ./wheels : le wheel de Vibe Starter + toutes ses dépendances + PyInstaller, pour Windows 64 bits.
La résolution est faite POUR Windows (dépendances pywin32, pefile, colorama… incluses), puis le script
vérifie que chaque paquet résolu est bien présent. Les .bat l'utilisent en priorité (pip --no-index).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(*args: str, capture: bool = False) -> str:
    print("+", " ".join(args))
    result = subprocess.run(args, check=True, capture_output=capture, text=True)
    return result.stdout if capture else ""


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def resolve_for_windows(version: str, requirements: list[str]) -> list[tuple[str, str]]:
    """Versions exactes à installer sous Windows / CPython `version` (uv pip compile)."""
    lines = subprocess.run(
        ["uv", "pip", "compile", "-", "--python-platform", "windows", "--python-version", version,
         "--no-header", "--no-annotate", "-q"],
        input="\n".join(requirements), check=True, capture_output=True, text=True,
    ).stdout
    pins = []
    for line in lines.splitlines():
        match = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)", line.strip())
        if match:
            pins.append((match.group(1), match.group(2)))
    return pins


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--python-version", action="append", required=True, help="ex. 3.14 (répétable)")
    parser.add_argument("--out", type=Path, default=ROOT / "wheels")
    args = parser.parse_args()

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("uefn_vibe_starter-*.whl"):
        old.unlink()
    run(sys.executable, "-m", "pip", "wheel", str(ROOT), "--no-deps", "-w", str(out))

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    requirements = [*project["dependencies"], "pyinstaller"]

    missing_total = 0
    for version in args.python_version:
        tag = "cp" + version.replace(".", "")
        pins = resolve_for_windows(version, requirements)
        lock = out / f"_lock-{tag}.txt"
        lock.write_text("\n".join(f"{n}=={v}" for n, v in pins) + "\n", encoding="utf-8")
        run(
            sys.executable, "-m", "pip", "download", "-r", str(lock), "--no-deps", "-d", str(out),
            "--only-binary=:all:", "--platform", "win_amd64", "--python-version", version,
            "--implementation", "cp", "--abi", tag,
        )
        lock.unlink()
        have = {(norm(p.name.split("-")[0]), p.name.split("-")[1]) for p in out.glob("*.whl")}
        absent = [f"{n}=={v}" for n, v in pins if (norm(n), v) not in have]
        print(f"[{version}] {len(pins)} paquets résolus pour Windows ; manquants : {absent or 'aucun'}")
        missing_total += len(absent)

    print(f"\n{len(list(out.glob('*.whl')))} wheels dans {out}")
    return 1 if missing_total else 0


if __name__ == "__main__":
    raise SystemExit(main())
