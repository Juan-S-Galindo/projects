# https://www.pantsbuild.org/2.18/reference/targets/python_sources
python_sources(
    name="lib",
    dependencies=[":budget_data"],
)

# https://www.pantsbuild.org/2.18/reference/targets/resource
resource(
    name="budget_data",
    source="Resources/budget_data.csv",
)

# https://www.pantsbuild.org/2.18/docs/python/goals/package#creating-a-pex-file-from-a-pex_binary-target
# https://www.pantsbuild.org/2.18/docs/python/overview/pex-files
pex_binary(
  name="app",
  entry_point="main.py",
)
