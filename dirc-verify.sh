#!/usr/bin/env bash
set -euo pipefail
shopt -s extglob

ROOT="${1:-.}"
ALLOW_EXTRA_EVERYWHERE=0
STRICT_ROOT=0
SPEC_BASENAME='.dirc'

IGNORE_BASENAMES=('.git' '.dirc')

fail() {
  echo "dirc: $*" >&2
  exit 1
}

basename_safe() {
  local p="$1"
  echo "${p##*/}"
}

matches_any() {
  local name="$1"; shift
  local pat
  for pat in "$@"; do
    [[ "$name" == $pat ]] && return 0
  done
  return 1
}

is_ignored() {
  local base="$1"
  matches_any "$base" "${IGNORE_BASENAMES[@]}"
}

check_dir() {
  local rel="$1"
  local allowed_dirs_var="$2"
  local allowed_files_var="$3"
  local required_dirs_var="$4"
  local required_files_var="$5"
  local allow_extra="$6"

  local path="$ROOT/$rel"
  [[ -d "$path" ]] || fail "missing directory: $rel"

  local allowed_dirs allowed_files required_dirs required_files
  eval "allowed_dirs=(\"\${${allowed_dirs_var}[@]}\")"
  eval "allowed_files=(\"\${${allowed_files_var}[@]}\")"
  eval "required_dirs=(\"\${${required_dirs_var}[@]}\")"
  eval "required_files=(\"\${${required_files_var}[@]}\")"

  local req
  for req in "${required_dirs[@]}"; do
    [[ -d "$path/$req" ]] || fail "missing required directory: ${rel%/}/$req"
  done

  for req in "${required_files[@]}"; do
    [[ -f "$path/$req" ]] || fail "missing required file: ${rel%/}/$req"
  done

  shopt -s nullglob dotglob
  local entries=("$path"/*)
  shopt -u dotglob

  local entry base
  for entry in "${entries[@]}"; do
    base="$(basename_safe "$entry")"
    is_ignored "$base" && continue

    if [[ -d "$entry" ]]; then
      if matches_any "$base" "${allowed_dirs[@]}"; then
        :
      elif [[ "$allow_extra" == "1" ]]; then
        :
      else
        fail "unexpected directory: ${rel%/}/$base"
      fi
    else
      if matches_any "$base" "${allowed_files[@]}"; then
        :
      elif [[ "$allow_extra" == "1" ]]; then
        :
      else
        fail "unexpected file: ${rel%/}/$base"
      fi
    fi
  done
}

ALLOWED_DIRS_1=('folder1' 'folder2' 'folder3')
ALLOWED_FILES_1=()
REQUIRED_DIRS_1=('folder1' 'folder2' 'folder3')
REQUIRED_FILES_1=()

rule_1() {
  local rel="$1"
  local allow_extra=0
  if [[ "$ALLOW_EXTRA_EVERYWHERE" == "1" ]] || ([[ "$rel" == "." ]] && [[ "$STRICT_ROOT" != "1" ]]); then allow_extra=1; fi
  check_dir "$rel" ALLOWED_DIRS_1 ALLOWED_FILES_1 REQUIRED_DIRS_1 REQUIRED_FILES_1 "$allow_extra"
  rule_2 "${rel%/}/folder1"
  rule_5 "${rel%/}/folder2"
  rule_6 "${rel%/}/folder3"
}

ALLOWED_DIRS_2=('pngs' 'photos')
ALLOWED_FILES_2=()
REQUIRED_DIRS_2=('pngs' 'photos')
REQUIRED_FILES_2=()

rule_2() {
  local rel="$1"
  local allow_extra=0
  if [[ "$ALLOW_EXTRA_EVERYWHERE" == "1" ]] || ([[ "$rel" == "." ]] && [[ "$STRICT_ROOT" != "1" ]]); then allow_extra=1; fi
  check_dir "$rel" ALLOWED_DIRS_2 ALLOWED_FILES_2 REQUIRED_DIRS_2 REQUIRED_FILES_2 "$allow_extra"
  rule_3 "${rel%/}/pngs"
  rule_4 "${rel%/}/photos"
}

ALLOWED_DIRS_3=()
ALLOWED_FILES_3=('*.png')
REQUIRED_DIRS_3=()
REQUIRED_FILES_3=()

rule_3() {
  local rel="$1"
  local allow_extra=0
  if [[ "$ALLOW_EXTRA_EVERYWHERE" == "1" ]] || ([[ "$rel" == "." ]] && [[ "$STRICT_ROOT" != "1" ]]); then allow_extra=1; fi
  check_dir "$rel" ALLOWED_DIRS_3 ALLOWED_FILES_3 REQUIRED_DIRS_3 REQUIRED_FILES_3 "$allow_extra"
}

ALLOWED_DIRS_4=()
ALLOWED_FILES_4=('*.@(svg|jpg|png)')
REQUIRED_DIRS_4=()
REQUIRED_FILES_4=()

rule_4() {
  local rel="$1"
  local allow_extra=0
  if [[ "$ALLOW_EXTRA_EVERYWHERE" == "1" ]] || ([[ "$rel" == "." ]] && [[ "$STRICT_ROOT" != "1" ]]); then allow_extra=1; fi
  check_dir "$rel" ALLOWED_DIRS_4 ALLOWED_FILES_4 REQUIRED_DIRS_4 REQUIRED_FILES_4 "$allow_extra"
}

ALLOWED_DIRS_5=()
ALLOWED_FILES_5=('folder2-*.*')
REQUIRED_DIRS_5=()
REQUIRED_FILES_5=()

rule_5() {
  local rel="$1"
  local allow_extra=0
  if [[ "$ALLOW_EXTRA_EVERYWHERE" == "1" ]] || ([[ "$rel" == "." ]] && [[ "$STRICT_ROOT" != "1" ]]); then allow_extra=1; fi
  check_dir "$rel" ALLOWED_DIRS_5 ALLOWED_FILES_5 REQUIRED_DIRS_5 REQUIRED_FILES_5 "$allow_extra"
}

ALLOWED_DIRS_6=('f3' 'f3-*')
ALLOWED_FILES_6=()
REQUIRED_DIRS_6=('f3')
REQUIRED_FILES_6=()

rule_6() {
  local rel="$1"
  local allow_extra=0
  if [[ "$ALLOW_EXTRA_EVERYWHERE" == "1" ]] || ([[ "$rel" == "." ]] && [[ "$STRICT_ROOT" != "1" ]]); then allow_extra=1; fi
  check_dir "$rel" ALLOWED_DIRS_6 ALLOWED_FILES_6 REQUIRED_DIRS_6 REQUIRED_FILES_6 "$allow_extra"
  rule_7 "${rel%/}/f3"
  local path="$ROOT/$rel"
  shopt -s nullglob dotglob
  local dirs=("$path"/*)
  shopt -u dotglob
  local entry base
  for entry in "${dirs[@]}"; do
    [[ -d "$entry" ]] || continue
    base="$(basename_safe "$entry")"
    is_ignored "$base" && continue
    case "$base" in
      'f3') continue ;;
    esac
    local matched=0
    if [[ "$base" == f3-* ]]; then
      if [[ "$matched" == "1" ]]; then
        fail "ambiguous directory rule for: ${rel%/}/$base"
      fi
      matched=1
      rule_8 "${rel%/}/$base"
    fi
  done
}

ALLOWED_DIRS_7=()
ALLOWED_FILES_7=('cmd-*.sh')
REQUIRED_DIRS_7=()
REQUIRED_FILES_7=()

rule_7() {
  local rel="$1"
  local allow_extra=0
  if [[ "$ALLOW_EXTRA_EVERYWHERE" == "1" ]] || ([[ "$rel" == "." ]] && [[ "$STRICT_ROOT" != "1" ]]); then allow_extra=1; fi
  check_dir "$rel" ALLOWED_DIRS_7 ALLOWED_FILES_7 REQUIRED_DIRS_7 REQUIRED_FILES_7 "$allow_extra"
}

ALLOWED_DIRS_8=()
ALLOWED_FILES_8=('cmd-*.sh')
REQUIRED_DIRS_8=()
REQUIRED_FILES_8=()

rule_8() {
  local rel="$1"
  local allow_extra=0
  if [[ "$ALLOW_EXTRA_EVERYWHERE" == "1" ]] || ([[ "$rel" == "." ]] && [[ "$STRICT_ROOT" != "1" ]]); then allow_extra=1; fi
  check_dir "$rel" ALLOWED_DIRS_8 ALLOWED_FILES_8 REQUIRED_DIRS_8 REQUIRED_FILES_8 "$allow_extra"
}

rule_1 "."

echo "dirc: ok"
