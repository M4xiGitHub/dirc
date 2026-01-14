from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .compiler import CompileOptions, compile_to_bash
from .spec import SpecError, load_spec


DEFAULT_SPEC_CANDIDATES = (".dirc", "dirc.dirc", "dirc.spec")


def _find_default_spec(start: Path) -> Optional[Path]:
    for name in DEFAULT_SPEC_CANDIDATES:
        candidate = start / name
        if candidate.is_file():
            return candidate
    return None


@dataclass(frozen=True)
class CommonArgs:
    spec_path: Path
    root: Path
    ignore: tuple[str, ...]


def _parse_common_args(ns: argparse.Namespace) -> CommonArgs:
    root = Path(ns.root).resolve()

    spec_path: Optional[Path]
    if ns.spec:
        spec_path = Path(ns.spec).resolve()
    else:
        spec_path = _find_default_spec(root)

    if spec_path is None:
        candidates = ", ".join(DEFAULT_SPEC_CANDIDATES)
        raise SpecError(f"no spec file found (looked for: {candidates}); pass --spec")
    if not spec_path.is_file():
        raise SpecError(f"spec file not found: {spec_path}")

    ignore: list[str] = []
    ignore.extend(ns.ignore or [])
    ignore.append(".git")
    ignore.append(spec_path.name)

    return CommonArgs(spec_path=spec_path, root=root, ignore=tuple(dict.fromkeys(ignore)))


def _cmd_check(ns: argparse.Namespace) -> int:
    common = _parse_common_args(ns)
    spec = load_spec(common.spec_path)

    options = CompileOptions(
        ignore=list(common.ignore),
        allow_extra_everywhere=bool(ns.allow_extra),
        strict_root=bool(ns.strict_root),
    )
    script = compile_to_bash(spec, options=options, spec_basename=common.spec_path.name)

    proc = subprocess.run(
        ["bash", "-s", "--", str(common.root)],
        input=script,
        text=True,
    )
    return int(proc.returncode)


def _cmd_compile(ns: argparse.Namespace) -> int:
    common = _parse_common_args(ns)
    spec = load_spec(common.spec_path)

    options = CompileOptions(
        ignore=list(common.ignore),
        allow_extra_everywhere=bool(ns.allow_extra),
        strict_root=bool(ns.strict_root),
    )
    script = compile_to_bash(spec, options=options, spec_basename=common.spec_path.name)

    if ns.out:
        out_path = Path(ns.out)
        out_path.write_text(script, encoding="utf-8")
        os.chmod(out_path, 0o755)
    else:
        sys.stdout.write(script)
    return 0


def _cmd_init(ns: argparse.Namespace) -> int:
    path = Path(ns.path)
    if path.exists():
        raise SpecError(f"refusing to overwrite existing file: {path}")
    path.write_text(
        "\n".join(
            [
                "folder1",
                "    pngs",
                "        .png",
                "    photos",
                "        *.{svg, jpg, png}",
                "folder2",
                "    folder2-*.*",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="dirc", description="Directory structure linter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--spec", help="Path to spec file (default: .dirc/dirc.dirc/dirc.spec)")
        p.add_argument("--root", default=".", help="Project root to validate (default: .)")
        p.add_argument(
            "--ignore",
            action="append",
            default=[],
            help="Basename glob to ignore (repeatable). Always ignores .git and the spec file itself.",
        )
        p.add_argument(
            "--allow-extra",
            action="store_true",
            help="Allow extra files/dirs everywhere (disables strictness).",
        )
        p.add_argument(
            "--strict-root",
            action="store_true",
            help="Make the project root strict as well (by default only listed dirs are linted).",
        )

    p_check = sub.add_parser("check", help="Validate directory structure")
    add_common(p_check)
    p_check.set_defaults(func=_cmd_check)

    p_compile = sub.add_parser("compile", help="Compile spec to a standalone Bash verifier")
    add_common(p_compile)
    p_compile.add_argument("--out", help="Write script to this path (chmod +x). Default: stdout.")
    p_compile.set_defaults(func=_cmd_compile)

    p_init = sub.add_parser("init", help="Create a starter .dirc spec")
    p_init.add_argument("--path", default=".dirc", help="Output path (default: .dirc)")
    p_init.set_defaults(func=_cmd_init)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except SpecError as e:
        print(f"dirc: {e}", file=sys.stderr)
        return 2
