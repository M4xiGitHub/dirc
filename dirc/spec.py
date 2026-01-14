from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple


class SpecError(RuntimeError):
    pass


_GLOB_MAGIC = re.compile(r"[*?[]")
_EXT_SHORTHAND = re.compile(r"^\.[A-Za-z0-9]{1,5}$")


def glob_has_magic(s: str) -> bool:
    return bool(_GLOB_MAGIC.search(s))


def _is_file_pattern(token: str) -> bool:
    token = token.strip()
    return (
        bool(_EXT_SHORTHAND.match(token))
        or "*" in token
        or "?" in token
        or "[" in token
        or "{" in token
    )


def _normalize_pattern(raw: str) -> str:
    s = re.sub(r"\s+", "", raw.strip())
    if s == "*.*":
        return "*"
    if s.startswith(".") and "/" not in s:
        return f"*{s}"
    if "{" in s and "}" in s:
        s = re.sub(
            r"\{([^}]+)\}",
            lambda m: "@(" + "|".join([p for p in m.group(1).split(",") if p]) + ")",
            s,
        )
    return s


def _expand_tabs(line: str, tabsize: int = 4) -> str:
    return line.expandtabs(tabsize)


@dataclass
class DirectoryRule:
    name: str
    subdirs: list["DirectoryRule"] = field(default_factory=list)
    file_patterns: list[str] = field(default_factory=list)
    required_files: list[str] = field(default_factory=list)


@dataclass
class Spec:
    root: DirectoryRule


def load_spec(path: Path) -> Spec:
    text = path.read_text(encoding="utf-8")
    return parse_spec(text, source=str(path))


def parse_spec(text: str, source: str = "<spec>") -> Spec:
    root = DirectoryRule(name=".")
    stack: list[DirectoryRule] = [root]
    indent_unit: Optional[int] = None
    last_was_file_at_level: Optional[int] = None

    raw_lines = text.splitlines()

    def next_nonempty_line(i: int) -> Optional[Tuple[int, str]]:
        for j in range(i + 1, len(raw_lines)):
            candidate = raw_lines[j]
            if not candidate.strip():
                continue
            if candidate.lstrip().startswith("#"):
                continue
            return j, candidate
        return None

    for idx0, raw in enumerate(raw_lines):
        idx = idx0 + 1
        if not raw.strip():
            continue
        stripped = raw.lstrip()
        if stripped.startswith("#"):
            continue

        expanded = _expand_tabs(raw)
        indent = len(expanded) - len(expanded.lstrip(" "))
        content_raw = expanded[indent:].rstrip()
        for j, ch in enumerate(content_raw):
            if ch == "#" and (j == 0 or content_raw[j - 1].isspace()):
                content_raw = content_raw[:j].rstrip()
                break
        if not content_raw:
            continue
        content = content_raw.strip()

        if indent == 0:
            level = 0
        else:
            if indent_unit is None:
                indent_unit = indent
            if indent_unit <= 0:
                raise SpecError(f"{source}:{idx}: invalid indentation")
            if indent % indent_unit != 0:
                raise SpecError(
                    f"{source}:{idx}: indentation must be a multiple of {indent_unit} spaces"
                )
            level = indent // indent_unit

        if last_was_file_at_level is not None and level > last_was_file_at_level:
            raise SpecError(f"{source}:{idx}: file patterns cannot have children")

        while len(stack) > level + 1:
            stack.pop()

        if len(stack) != level + 1:
            raise SpecError(f"{source}:{idx}: indentation jumps are not allowed")

        parent = stack[-1]

        # Allow an explicit directory marker to disambiguate dot-directories, etc.
        dir_forced = content.endswith("/") and content != "/"
        if dir_forced:
            content = content[:-1]

        nxt = next_nonempty_line(idx0)
        has_children = False
        if nxt is not None:
            nxt_expanded = _expand_tabs(nxt[1])
            nxt_indent = len(nxt_expanded) - len(nxt_expanded.lstrip(" "))
            if indent_unit is None:
                has_children = nxt_indent > indent
            else:
                if nxt_indent > indent and nxt_indent % indent_unit == 0:
                    has_children = (nxt_indent // indent_unit) > level

        if not dir_forced and not has_children and _is_file_pattern(content):
            parent.file_patterns.append(_normalize_pattern(content))
            last_was_file_at_level = level
            continue

        # Required literal file (no globs), e.g. cmd-must.sh
        if not dir_forced and not has_children and "." in content and not glob_has_magic(content) and "{" not in content:
            parent.required_files.append(content)
            last_was_file_at_level = level
            continue

        child = DirectoryRule(name=content)
        parent.subdirs.append(child)
        stack.append(child)
        last_was_file_at_level = None

    return Spec(root=root)
