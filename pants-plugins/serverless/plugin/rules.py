"""Rules for the Jinja templates plugin.

This module defines the rules that handle the rendering of Jinja2
templates and the creation of package artifacts.
"""

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    ServerlessCustomConfigField,
    ServerlessFunctionsDependenciesField,
    ServerlessGlobalIamStatementsField,
    ServerlessImportGatewayField,
    ServerlessProviderConfigField,
    ServerlessResourcesDependenciesField,
    ServerlessS3CleanerBucketNamesField,
    ServerlessServiceField,
    ServerlessSourceTemplateDependenciesField,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServerlessTemplateFieldSet(PackageFieldSet):
    """Field set for Jinja template targets."""

    required_fields = (ServerlessServiceField,)

    service: ServerlessServiceField
    s3_cleaner_bucket_names: ServerlessS3CleanerBucketNamesField

    provider_config: ServerlessProviderConfigField
    custom_config: ServerlessCustomConfigField
    import_gateway: ServerlessImportGatewayField
    global_iam_statements: ServerlessGlobalIamStatementsField

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


def _config_to_yaml(value: Any, indent: int = 2) -> str:
    """Recursively serialise a config value to indented YAML text.

    - Mappings become ``key:\\n  <value>`` blocks.
    - Lists/tuples become ``- item`` sequences; list items that are Mappings
      use the standard YAML block-sequence style.
    - Scalars are emitted verbatim so SLS references (``${env:FOO}``) survive.

    Args:
        value: The value to serialise (Mapping, list/tuple, or scalar string).
        indent: Number of spaces for the current indentation level.

    Returns:
        Multi-line YAML string (no trailing newline).
    """
    spaces = " " * indent
    lines: List[str] = []

    if isinstance(value, Mapping):
        for k, v in value.items():
            if isinstance(v, (Mapping, list, tuple)):
                lines.append(f"{spaces}{k}:")
                lines.append(_config_to_yaml(v, indent + 2))
            else:
                lines.append(f"{spaces}{k}: {v}")

    elif isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, Mapping):
                item_pairs = list(item.items())
                first_k, first_v = item_pairs[0]
                if isinstance(first_v, (Mapping, list, tuple)):
                    lines.append(f"{spaces}- {first_k}:")
                    lines.append(_config_to_yaml(first_v, indent + 4))
                else:
                    lines.append(f"{spaces}- {first_k}: {first_v}")
                for k, v in item_pairs[1:]:
                    if isinstance(v, (Mapping, list, tuple)):
                        lines.append(f"{spaces}  {k}:")
                        lines.append(_config_to_yaml(v, indent + 4))
                    else:
                        lines.append(f"{spaces}  {k}: {v}")
            else:
                lines.append(f"{spaces}- {item}")

    else:
        lines.append(f"{spaces}{value}")

    return "\n".join(lines)


def _iam_statements_to_yaml(statements: tuple, indent: int = 2) -> str:
    """Serialise a tuple of frozen IAM statement dicts to indented YAML.

    Produces the ``iamRoleStatements:`` block ready for template substitution.
    String values are emitted verbatim so SLS references are preserved.

    Args:
        statements: Tuple of frozen IAM statement dicts.
        indent: Base indentation for the block key (default 2).

    Returns:
        Multi-line YAML string starting with ``  iamRoleStatements:``.
    """
    base = " " * indent
    item = " " * (indent + 2)
    field = " " * (indent + 4)
    lines: List[str] = [f"{base}iamRoleStatements:"]
    for stmt in statements:
        effect = stmt.get("Effect", "Allow")
        actions = stmt.get("Action", ())
        resource = stmt.get("Resource", "*")

        lines.append(f"{item}- Effect: {effect}")
        lines.append(f"{field}Action:")
        for action in (actions if isinstance(actions, (list, tuple)) else (actions,)):
            lines.append(f"{field}  - {action}")
        if isinstance(resource, (list, tuple)):
            lines.append(f"{field}Resource:")
            for r in resource:
                lines.append(f"{field}  - {r}")
        else:
            lines.append(f"{field}Resource: {resource}")
    return "\n".join(lines)


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
    service = field_set.service.value
    logger.info(f"Processing template at {service}")

    source_templates_targets = await Get(
        Targets, DependenciesRequest(field_set.source_templates)
    )
    config_files_targets = await Get(
        Targets, DependenciesRequest(field_set.config_files)
    )

    def _resolve_service_name(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {k: _resolve_service_name(v) for k, v in value.items()}
        if isinstance(value, tuple):
            return tuple(_resolve_service_name(item) for item in value)
        return value.replace("{{SERVICE_NAME}}", service)

    resolved_provider_config = _resolve_service_name(field_set.provider_config.value)

    serverless_jinja_mappings = {
        "SERVICE_NAME": service,
        "PROVIDER_CONFIG": _config_to_yaml(resolved_provider_config),
    }

    if field_set.global_iam_statements.value is not None:
        serverless_jinja_mappings["IAM_ROLE_STATEMENTS"] = _iam_statements_to_yaml(
            field_set.global_iam_statements.value
        )

    resources_targets = await Get(Targets, DependenciesRequest(field_set.resources))
    if resources_targets:
        serverless_jinja_mappings["RESOURCES"] = _get_dependencies_mappings(
            resources_targets,
            "RESOURCES",
            field_set.address.spec_path,
        )

    custom_lines: List[str] = []
    if field_set.custom_config.value:
        custom_lines.append(_config_to_yaml(field_set.custom_config.value))
    if field_set.import_gateway.value is not None:
        custom_lines.append(_config_to_yaml(field_set.import_gateway.value))

    if field_set.s3_cleaner_bucket_names.value:
        s3_block = "  serverless-s3-cleaner:\n    buckets:"
        for bucket in field_set.s3_cleaner_bucket_names.value:
            s3_block += f"\n      - {bucket}"
        custom_lines.append(s3_block)
    if custom_lines:
        serverless_jinja_mappings["CUSTOM"] = "custom:\n" + "\n".join(custom_lines)

    plugins: List[str] = []
    if field_set.global_iam_statements.value is not None:
        plugins.append("  - serverless-iam-roles-per-function")
    if field_set.import_gateway.value is not None:
        plugins.append("  - serverless-import-apigateway")

    if field_set.s3_cleaner_bucket_names.value:
        plugins.append("  - serverless-s3-cleaner")
    if plugins:
        serverless_jinja_mappings["PLUGINS"] = "plugins:\n" + "\n".join(plugins)

    functions_targets = await Get(Targets, DependenciesRequest(field_set.functions))
    if functions_targets:
        serverless_jinja_mappings["FUNCTIONS"] = _get_dependencies_mappings(
            functions_targets,
            "FUNCTIONS",
            field_set.address.spec_path,
        )

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
