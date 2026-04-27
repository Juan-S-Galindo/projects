Run Pants `check` goal (type checking via mypy or similar) on the specified targets.

If $ARGUMENTS is provided, use it as the target spec (e.g., `src/python/myapp::` or a specific file).
If no arguments are provided, default to `::` to type-check the entire repo.

Run the following command:
```
pants check <target_spec>
```

Show the full output. If type errors are found, summarize them grouped by file.
