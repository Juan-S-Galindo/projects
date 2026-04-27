Run Pants `export` goal to export a virtualenv for IDE use (e.g., to configure a Python interpreter in VS Code or PyCharm).

If $ARGUMENTS is provided, use it as additional flags or target spec (e.g., `--resolve=python-default`).
If no arguments are provided, run with no extra arguments to export the default resolve.

Run the following command:
```
pants export <args>
```

Show the full output and tell the user where the exported virtualenv was created so they can point their IDE to it.
