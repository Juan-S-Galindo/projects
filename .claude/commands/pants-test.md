Run Pants `test` goal on the specified targets.

If $ARGUMENTS is provided, use it as the target spec (e.g., `src/python/myapp::` or a specific file).
If no arguments are provided, default to `::` to run all tests in the repo.

Run the following command:
```
pants test <target_spec>
```

Show the full output. If tests fail, summarize which targets failed and why based on the output.
