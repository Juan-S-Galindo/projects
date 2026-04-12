Run Pants `run` goal to execute a binary or script target.

$ARGUMENTS must be provided and should be the target address to run (e.g., `src/python/myapp:main`).
Arguments to pass to the binary itself can be appended after `--`, e.g.: `src/python/myapp:main -- --flag value`

Run the following command:
```
pants run <target_spec>
```

If no arguments are provided, ask the user which target they want to run before proceeding.

Show the full output of the executed binary.
