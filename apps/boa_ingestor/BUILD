python_sources(
    name="lib",
    dependencies=[
        "apps/boa_ingestor/statements/bills:files",
        "apps/boa_ingestor/statements/main:files"
        ],
)

pex_binary(
    name="boa_ingestor",
    dependencies=[":lib"],
    entry_point='main.py',
    env={"PGHOST": env('PGHOST'), "PGUSER": env('PGUSER')},
)
