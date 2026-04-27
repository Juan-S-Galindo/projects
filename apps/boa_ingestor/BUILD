python_sources(
    name="lib",
    dependencies=["apps/boa_ingestor/statements:files"],
)

pex_binary(
    name="boa_ingestor",
    dependencies=[":lib"],
    entry_point='main.py',
    env={"PGHOST": env('PGHOST'), "PGUSER": env('PGUSER')},
)
