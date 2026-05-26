#!/bin/bash

# Filter out files outside Pants' source tree or not handled by Ruff (non-.py files)
files=()
for f in "$@"; do
  [[ "$f" == .claude/* ]] && continue
  [[ "$f" != *.py ]] && continue
  files+=("$f")
done

[ ${#files[@]} -eq 0 ] && exit 0

pants fmt "${files[@]}"
