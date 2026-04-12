Run Pants `lint` goal on the specified targets.

If $ARGUMENTS is provided, use it as the target spec (e.g., `src/python/myapp::` or a glob like `'**/*.py'`).
If no arguments are provided, default to `::` to lint the entire repo.

Run the following command:
```
pants lint <target_spec>
```

Show the full output. If linting violations are found, summarize the issues per file.
