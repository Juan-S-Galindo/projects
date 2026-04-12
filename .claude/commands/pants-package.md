Run Pants `package` goal to build a distributable artifact (e.g., a `.pex` file, wheel, or Docker image) for the specified targets.

If $ARGUMENTS is provided, use it as the target spec (e.g., `src/python/myapp:main` or `::` for all packageable targets).
If no arguments are provided, default to `::` to package all packageable targets in the repo.

Run the following command:
```
pants package <target_spec>
```

Show the full output and list the artifacts that were produced along with their output paths.
