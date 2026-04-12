"""Rules for the Jinja templates plugin.

This module defines the rules that handle the rendering of Jinja2
templates and the creation of package artifacts.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from jinja2 import Template
from pants.core.goals.package import BuiltPackage, BuiltPackageArtifact, PackageFieldSet
from pants.engine.fs import CreateDigest, Digest, DigestContents, FileContent, PathGlobs
from pants.engine.rules import Get, collect_rules, rule
from pants.engine.target import DependenciesRequest, SourcesField, Targets
from pants.engine.unions import UnionRule
from pants.util.frozendict import FrozenDict
from pants.util.logging import LogLevel

from serverless.plugin.subsystem import ServerlessTemplates
from serverless.plugin.target_types import (
    ServerlessConfigDependenciesField,
    ServerlessDeployApiGatewayField,
    ServerlessDeploymentBucketNameField,
    ServerlessFunctionsDependenciesField,
    ServerlessResourcesDependenciesField,
    ServerlessS3CleanerBucketNamesField,
    ServerlessSourceTemplateDependenciesField,
    ServerlessStackNameField,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServerlessTemplateFieldSet(PackageFieldSet):
    """Field set for Jinja template targets."""

    required_fields = (ServerlessStackNameField, ServerlessDeploymentBucketNameField)

    stack_name: ServerlessStackNameField
    deployment_bucket: ServerlessDeploymentBucketNameField
    s3_cleaner_bucket_names: ServerlessS3CleanerBucketNamesField
    deploy_api_gateway: ServerlessDeployApiGatewayField

    functions: ServerlessFunctionsDependenciesField
    resources: ServerlessResourcesDependenciesField
    config_files: ServerlessConfigDependenciesField
    source_templates: ServerlessSourceTemplateDependenciesField


def _get_source_path(target: Targets) -> str:
    """Get the source file path from a target.

    Args:
        target: The target to get the source path from

    Returns:
        The source file path

    Raises:
        ValueError: If no source path is found
    """
    source_field = target.get(SourcesField)
    if not source_field or not source_field.file_path:
        raise ValueError(f"No source path found in target: {target.address}")
    return source_field.file_path


def _render_template(template_content: str, mappings: Dict[str, str]) -> str:
    """Render a Jinja2 template with the given mappings.

    Args:
        template_content: The content of the template to render
        mappings: The variable mappings to use for rendering

    Returns:
        The rendered template content
    """
    template = Template(template_content)
    return template.render(mappings)


def _create_template_output_path(
    target_path: str, source_file: Path, template_suffix: Optional[str] = None
) -> Path:
    """Create the output path for a rendered template.

    Args:
        target_path: The path of the target
        source_file: The source file being processed
        template_suffix: Optional custom filename to use

    Returns:
        The path where the rendered template should be written
    """
    output_name = source_file.name

    if template_suffix:
        output_name = output_name.replace(template_suffix, "")

    if str(source_file).startswith("serverless_global_config.yml.tmpl") or str(
        source_file
    ).endswith("serverless.yml.tmpl"):
        output_path = Path(f"{target_path}/{output_name}")
    else:
        output_path = Path(f"{source_file.parent}/{output_name}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


async def _process_template(
    target: Targets,
    template_mappings: Dict[str, str],
    target_path: str,
    template_suffix: Optional[str],
) -> Tuple[FileContent, BuiltPackageArtifact]:
    """Process a single template file.

    Args:
        target: The target containing the template
        template_mappings: The mappings to use for rendering
        target_path: The path where the output should be written
        template_suffix: Optional suffix to remove from the output filename

    Returns:
        A tuple containing the file content and artifact

    Raises:
        ValueError: If the source path is invalid or multiple files are found
    """
    source_path = _get_source_path(target)
    source_file = Path(source_path)

    digest = await Get(Digest, PathGlobs([str(source_file)]))
    digest_contents = await Get(DigestContents, Digest, digest)

    if len(digest_contents) != 1:
        raise ValueError(
            f"Expected exactly one file, found {len(digest_contents)} in {source_file}"
        )

    file_content = digest_contents[0]
    template_content = file_content.content.decode("utf-8")

    output_path = _create_template_output_path(
        target_path, source_file, template_suffix
    )

    rendered_content = (
        _render_template(template_content, template_mappings)
        if file_content.path.endswith(".tmpl")
        else template_content
    )

    logger.debug(f"Writing rendered template to {output_path}")
    return (
        FileContent(str(output_path), rendered_content.encode()),
        BuiltPackageArtifact(relpath=str(output_path)),
    )


def _get_dependencies_mappings(targets, mapping_key: str, target_path: str):
    if mapping_key == "RESOURCES":
        sls_key = "resources:"
    elif mapping_key == "FUNCTIONS":
        sls_key = "functions:"
    else:
        raise ValueError(f"Invalid mapping key: {mapping_key}")

    output_mappings = f"{sls_key}\n"
    for target in targets:
        source_path = _get_source_path(target=target)
        if not source_path.endswith("Dockerfile"):
            serverless_relative_path = source_path.replace(f"{target_path}/", "")
            output_mappings += f"  - ${{file({serverless_relative_path})}}\n"
    return output_mappings


def _get_docker_mappings(targets, target_path: str):
    header = False
    for target in targets:
        source_path = _get_source_path(target=target)
        if source_path.endswith("Dockerfile"):
            if not header:
                output_mappings = """ecr:
    images:
"""
                header = True

            serverless_relative_path = Path(source_path.replace(f"{target_path}/", ""))
            dir_name = target.address.spec_path.split("/")[-1]

            output_mappings += f"      {dir_name}_seb:\n"
            output_mappings += f"        path: ./{serverless_relative_path.parent}\n"
            output_mappings += f"        file: Dockerfile\n"
    if header:
        return output_mappings


@rule(level=LogLevel.DEBUG)
async def run_serverless_templates(
    serverless_templates: ServerlessTemplates,
    field_set: ServerlessTemplateFieldSet,
) -> BuiltPackage:
    """Rule to render Jinja templates and create package artifacts.

    Args:
        serverless_templates: The Jinja templates subsystem
        field_set: The field set containing template information

    Returns:
        A built package containing the rendered templates
    """
    stack_name = field_set.stack_name.value
    bucket_name = field_set.deployment_bucket.value
    logger.info(f"Processing template at {stack_name}")

    source_templates_targets = await Get(
        Targets, DependenciesRequest(field_set.source_templates)
    )
    config_files_targets = await Get(
        Targets, DependenciesRequest(field_set.config_files)
    )

    serverless_jinja_mappings = {
        "SERVICE_NAME": stack_name,
        "DEPLOYMENT_BUCKET": bucket_name,
    }
    resources_targets = await Get(Targets, DependenciesRequest(field_set.resources))
    if resources_targets:
        serverless_jinja_mappings["RESOURCES"] = _get_dependencies_mappings(
            resources_targets,
            "RESOURCES",
            field_set.address.spec_path,
        )

    if field_set.s3_cleaner_bucket_names.value:
        serverless_jinja_mappings["S3_CLEANER_BUCKETS_PLUGIN"] = (
            "- serverless-s3-cleaner"
        )

        serverless_jinja_mappings["S3_CLEANER_BUCKETS"] = "serverless-s3-cleaner:\n"
        serverless_jinja_mappings["S3_CLEANER_BUCKETS"] += "    buckets:\n"

        for bucket in field_set.s3_cleaner_bucket_names.value:
            serverless_jinja_mappings["S3_CLEANER_BUCKETS"] += (
                "      - " + bucket + "\n"
            )

    if field_set.deploy_api_gateway.value:
        serverless_jinja_mappings["IMPORT_API_GATEWAY_PLUGIN"] = (
            "- serverless-import-apigateway"
        )

        serverless_jinja_mappings["IMPORT_API_GATEWAY"] = "importApiGateway:\n"
        serverless_jinja_mappings["IMPORT_API_GATEWAY"] += (
            "    name: nsl-${env:AWS_ACCOUNT_NAME_ABBREVIATION}-${env:DEPLOY_TAG}\n"
        )
        serverless_jinja_mappings["IMPORT_API_GATEWAY"] += "    path: /\n"
        serverless_jinja_mappings["IMPORT_API_GATEWAY"] += "    resources:\n"
        serverless_jinja_mappings["IMPORT_API_GATEWAY"] += "      - /v3\n"

    functions_targets = await Get(Targets, DependenciesRequest(field_set.functions))
    if functions_targets:
        serverless_jinja_mappings["FUNCTIONS"] = _get_dependencies_mappings(
            functions_targets,
            "FUNCTIONS",
            field_set.address.spec_path,
        )
        docker_mappings = _get_docker_mappings(
            functions_targets,
            field_set.address.spec_path,
        )
        if docker_mappings:
            serverless_jinja_mappings["IMAGES"] = docker_mappings

    output_digests: List[FileContent] = []
    output_artifacts: List[BuiltPackageArtifact] = []

    for target in [
        *config_files_targets,
        *resources_targets,
        *functions_targets,
        *source_templates_targets,
    ]:
        try:
            file_content, artifact = await _process_template(
                target,
                serverless_jinja_mappings,
                field_set.address.spec_path,
                ".tmpl",
            )
            output_digests.append(file_content)
            output_artifacts.append(artifact)
        except ValueError as e:
            logger.error(f"Error processing template: {str(e)}")
            return BuiltPackage(
                digest=await Get(Digest, CreateDigest([])),
                artifacts=(),
            )

    digest = await Get(Digest, CreateDigest(output_digests))
    return BuiltPackage(
        digest=digest,
        artifacts=tuple(output_artifacts),
    )


def rules():
    """Return the rules for the Jinja templates plugin."""
    return [*collect_rules(), UnionRule(PackageFieldSet, ServerlessTemplateFieldSet)]
