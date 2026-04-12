file(
    name = "environment",
    source = "environment.yml",
)

serverless(
    name="sls",
    stack_name="budgeting-app",
    deployment_bucket="my-deploy-bucket",
    config_files=[":environment"],
    resources = [
        "aws/budgeting_app/ingest:function"
    ],
    tags = ['serverless']
)
