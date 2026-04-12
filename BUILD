python_requirements(
    name="root",
)

docker_image(
    name="base_image",
    image_tags=[env("DOCKER_DEPLOY_TAG")],
    registries=[env("DOCKER_REGISTRY")],
    build_platform=[f"linux/{env('CPU_ARCH')}"],
    extra_build_args=[
        f"CPU_ARCH={env('CPU_ARCH')}",
        f"PYTHON_VERSION={env('PYTHON_VERSION')}",
    ],
)

file(name="serverless_global_config", source="serverless_global_config.yml.tmpl")
