# https://www.pantsbuild.org/2.30/reference/targets/python_sources
python_sources(
    name="lib",
    dependencies=["apps/chase_cc_ingestor/statements:files"],
)

# https://www.pantsbuild.org/2.30/docs/python/goals/package#creating-a-pex-file-from-a-pex_binary-target
pex_binary(
    name="chase_cc_ingestor",
    dependencies=[":lib"],
    entry_point='main.py',
    env={"PGHOST":env('PGHOST'), "PGUSER":env('PGUSER')},
)
