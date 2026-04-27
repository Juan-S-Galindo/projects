Run Pants `fmt` goal to auto-format the specified targets.

If $ARGUMENTS is provided, use it as the target spec (e.g., `src/python/myapp::` or a specific file).
If no arguments are provided, default to `::` to format the entire repo.

Run the following command:
```
pants fmt <target_spec>
```

Show the full output and list any files that were reformatted.
