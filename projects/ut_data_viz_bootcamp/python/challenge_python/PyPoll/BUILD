# https://www.pantsbuild.org/2.18/reference/targets/python_sources
python_sources(
    name="lib",
    dependencies=[":election_data"],
)

# https://www.pantsbuild.org/2.18/reference/targets/resource
resource(
    name="election_data",
    source="Resources/election_data.csv",
)

# https://www.pantsbuild.org/2.18/docs/python/goals/package#creating-a-pex-file-from-a-pex_binary-target
# https://www.pantsbuild.org/2.18/docs/python/overview/pex-files
pex_binary(
  name="solution_dict",
  entry_point="mainDict.py",
)

# https://www.pantsbuild.org/2.18/docs/python/goals/package#creating-a-pex-file-from-a-pex_binary-target
# https://www.pantsbuild.org/2.18/docs/python/overview/pex-files
pex_binary(
  name="solution_list",
  entry_point="mainList.py",
)
