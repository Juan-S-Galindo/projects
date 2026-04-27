# https://www.pantsbuild.org/2.30/reference/targets/python_sources
python_sources(
    name="lib",
    dependencies=["//:root"],
)

# https://www.pantsbuild.org/2.30/docs/python/goals/package#creating-a-pex-file-from-a-pex_binary-target
pex_binary(
    name="chase_cc_ingestor",
    entry_point="apps/chase_cc_ingestor/main.py",
    dependencies=[":lib"],
)
