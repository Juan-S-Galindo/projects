#!/bin/bash

# Filter out files outside Pants' source tree (e.g. .claude/)
files=()
for f in "$@"; do
  [[ "$f" == .claude/* ]] && continue
  files+=("$f")
done

[ ${#files[@]} -eq 0 ] && exit 0

pants fmt "${files[@]}"
