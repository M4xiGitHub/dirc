from __future__ import annotations

from dataclasses import dataclass

from .spec import DirectoryRule, Spec, glob_has_magic


@dataclass(frozen=True)
class CompileOptions:
    ignore: list[str]
    allow_extra_everywhere: bool = False
    strict_root: bool = False


def _bash_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def _bash_array(name: str, items: list[str]) -> str:
    if not items:
        return f"{name}=()"
    quoted = " ".join([_bash_quote(x) for x in items])
    return f"{name}=({quoted})"

@dataclass(frozen=True)
class _Node:
    node_id: int
    rule: DirectoryRule
    children: list["_Node"]


def _build_nodes(rule: DirectoryRule) -> _Node:
    next_id = 1

    def walk(r: DirectoryRule) -> _Node:
        nonlocal next_id
        node = _Node(node_id=next_id, rule=r, children=[])
        next_id += 1
        children = [walk(c) for c in r.subdirs]
        object.__setattr__(node, "children", children)
        return node

    return walk(rule)


def compile_to_bash(spec: Spec, options: CompileOptions, spec_basename: str = ".dirc") -> str:
    lines: list[str] = []
    lines.append("#!/usr/bin/env bash")
    lines.append("set -euo pipefail")
    lines.append("shopt -s extglob")
    lines.append("")
    lines.append('ROOT="${1:-.}"')
    lines.append(f"ALLOW_EXTRA_EVERYWHERE={'1' if options.allow_extra_everywhere else '0'}")
    lines.append(f"STRICT_ROOT={'1' if options.strict_root else '0'}")
    lines.append(f"SPEC_BASENAME={_bash_quote(spec_basename)}")
    lines.append("")

    ignore_items = list(options.ignore or [])
    if ".git" not in ignore_items:
        ignore_items.append(".git")
    if spec_basename not in ignore_items:
        ignore_items.append(spec_basename)

    lines.append(_bash_array("IGNORE_BASENAMES", ignore_items))
    lines.append("")

    lines.append('if [[ "${1:-}" != "" ]] && [[ ! -d "$ROOT" ]]; then')
    lines.append('  ROOT="."')
    lines.append("fi")
    lines.append("")

    lines.append(
        "\n".join(
            [
                "fail() {",
                '  echo "dirc: $*" >&2',
                "  exit 1",
                "}",
                "",
                "basename_safe() {",
                "  local p=\"$1\"",
                "  echo \"${p##*/}\"",
                "}",
                "",
                "matches_any() {",
                "  local name=\"$1\"; shift",
                "  local pat",
                "  for pat in \"$@\"; do",
                "    [[ \"$name\" == $pat ]] && return 0",
                "  done",
                "  return 1",
                "}",
                "",
                "is_ignored() {",
                "  local base=\"$1\"",
                "  matches_any \"$base\" \"${IGNORE_BASENAMES[@]}\"",
                "}",
                "",
                "check_dir() {",
                "  local rel=\"$1\"",
                "  local allowed_dirs_var=\"$2\"",
                "  local allowed_files_var=\"$3\"",
                "  local required_dirs_var=\"$4\"",
                "  local required_files_var=\"$5\"",
                "  local allow_extra=\"$6\"",
                "",
                "  local path=\"$ROOT/$rel\"",
                "  [[ -d \"$path\" ]] || fail \"missing directory: $rel\"",
                "",
                "  local allowed_dirs allowed_files required_dirs required_files",
                "  eval \"allowed_dirs=(\\\"\\${${allowed_dirs_var}[@]}\\\")\"",
                "  eval \"allowed_files=(\\\"\\${${allowed_files_var}[@]}\\\")\"",
                "  eval \"required_dirs=(\\\"\\${${required_dirs_var}[@]}\\\")\"",
                "  eval \"required_files=(\\\"\\${${required_files_var}[@]}\\\")\"",
                "",
                "  local req",
                "  for req in \"${required_dirs[@]}\"; do",
                "    [[ -d \"$path/$req\" ]] || fail \"missing required directory: ${rel%/}/$req\"",
                "  done",
                "",
                "  for req in \"${required_files[@]}\"; do",
                "    [[ -f \"$path/$req\" ]] || fail \"missing required file: ${rel%/}/$req\"",
                "  done",
                "",
                "  shopt -s nullglob dotglob",
                "  local entries=(\"$path\"/*)",
                "  shopt -u dotglob",
                "",
                "  local entry base",
                "  for entry in \"${entries[@]}\"; do",
                "    base=\"$(basename_safe \"$entry\")\"",
                "    is_ignored \"$base\" && continue",
                "",
                "    if [[ -d \"$entry\" ]]; then",
                "      if matches_any \"$base\" \"${allowed_dirs[@]}\"; then",
                "        :",
                "      elif [[ \"$allow_extra\" == \"1\" ]]; then",
                "        :",
                "      else",
                "        fail \"unexpected directory: ${rel%/}/$base\"",
                "      fi",
                "    else",
                "      if matches_any \"$base\" \"${allowed_files[@]}\"; then",
                "        :",
                "      elif [[ \"$allow_extra\" == \"1\" ]]; then",
                "        :",
                "      else",
                "        fail \"unexpected file: ${rel%/}/$base\"",
                "      fi",
                "    fi",
                "  done",
                "}",
                "",
            ]
        )
    )

    root_node = _build_nodes(spec.root)

    def func_name(node_id: int) -> str:
        return f"rule_{node_id}"

    def compile_node(node: _Node) -> None:
        node_id = node.node_id
        rule = node.rule

        allowed_dirs = [c.rule.name for c in node.children]
        allowed_files = list(rule.file_patterns) + list(rule.required_files)
        required_dirs = [c.rule.name for c in node.children if not glob_has_magic(c.rule.name)]
        required_files = list(rule.required_files)

        allow_dirs_var = f"ALLOWED_DIRS_{node_id}"
        allow_files_var = f"ALLOWED_FILES_{node_id}"
        req_dirs_var = f"REQUIRED_DIRS_{node_id}"
        req_files_var = f"REQUIRED_FILES_{node_id}"

        lines.append(_bash_array(allow_dirs_var, allowed_dirs))
        lines.append(_bash_array(allow_files_var, allowed_files))
        lines.append(_bash_array(req_dirs_var, required_dirs))
        lines.append(_bash_array(req_files_var, required_files))
        lines.append("")

        lines.append(f"{func_name(node_id)}() {{")
        lines.append("  local rel=\"$1\"")

        lines.append("  local allow_extra=0")
        lines.append(
            "  if [[ \"$ALLOW_EXTRA_EVERYWHERE\" == \"1\" ]] || ([[ \"$rel\" == \".\" ]] && [[ \"$STRICT_ROOT\" != \"1\" ]]); then allow_extra=1; fi"
        )
        lines.append(
            f"  check_dir \"$rel\" {allow_dirs_var} {allow_files_var} {req_dirs_var} {req_files_var} \"$allow_extra\""
        )

        literal_children = [c for c in node.children if not glob_has_magic(c.rule.name)]
        wildcard_children = [c for c in node.children if glob_has_magic(c.rule.name)]

        if literal_children:
            for child in literal_children:
                child_name = child.rule.name
                lines.append(f"  {func_name(child.node_id)} \"${{rel%/}}/{child_name}\"")

        if wildcard_children:
            lines.append("  local path=\"$ROOT/$rel\"")
            lines.append("  shopt -s nullglob dotglob")
            lines.append("  local dirs=(\"$path\"/*)")
            lines.append("  shopt -u dotglob")
            lines.append("  local entry base")
            lines.append("  for entry in \"${dirs[@]}\"; do")
            lines.append("    [[ -d \"$entry\" ]] || continue")
            lines.append("    base=\"$(basename_safe \"$entry\")\"")
            lines.append("    is_ignored \"$base\" && continue")

            literal_names = [c.rule.name for c in literal_children]
            if literal_names:
                lines.append("    case \"$base\" in")
                for name in literal_names:
                    lines.append(f"      {_bash_quote(name)}) continue ;;")
                lines.append("    esac")

            lines.append("    local matched=0")
            for child in wildcard_children:
                pat = child.rule.name
                lines.append(f"    if [[ \"$base\" == {pat} ]]; then")
                lines.append("      if [[ \"$matched\" == \"1\" ]]; then")
                lines.append("        fail \"ambiguous directory rule for: ${rel%/}/$base\"")
                lines.append("      fi")
                lines.append("      matched=1")
                lines.append(f"      {func_name(child.node_id)} \"${{rel%/}}/$base\"")
                lines.append("    fi")
            lines.append("  done")

        lines.append("}")
        lines.append("")

        for child in node.children:
            compile_node(child)

    compile_node(root_node)

    lines.append(f"{func_name(root_node.node_id)} \".\"")
    lines.append("")

    lines.append('echo "dirc: ok"')
    lines.append("")
    return "\n".join(lines)
