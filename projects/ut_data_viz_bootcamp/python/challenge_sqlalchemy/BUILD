# https://www.pantsbuild.org/2.18/reference/targets/python_sources
python_sources(
    name="lib",
    dependencies=[":hawaii_sqlite"],
)

# https://www.pantsbuild.org/2.18/reference/targets/resource
resource(
    name="hawaii_sqlite",
    source="Resources/hawaii.sqlite",
)

# https://www.pantsbuild.org/2.18/docs/python/goals/package#creating-a-pex-file-from-a-pex_binary-target
# https://www.pantsbuild.org/2.18/docs/python/overview/pex-files
pex_binary(
  name="app",
  entry_point="app.py",
)

# https://www.pantsbuild.org/2.18/docs/using-pants/assets-and-archives#archive-create-a-zip-or-tar-file
archive(
    name="app_package",
    packages=[":app"],
    format="zip",
)
