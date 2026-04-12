"""Rules for the Jinja templates plugin.

This module defines the rules that handle the rendering of Jinja2

templates and the creation of package artifacts.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from jinja2 import Template
from replace_templates.plugin.subsystem import ReplaceTemplates
from replace_templates.plugin.target_types import (
    ReplaceTemplateDependenciesField,
    ReplaceTemplateMappingsField,
    ReplaceTemplateSuffxField,
)
from pants.core.goals.package import BuiltPackage, BuiltPackageArtifact, PackageFieldSet
from pants.engine.fs import CreateDigest, Digest, DigestContents, FileContent, PathGlobs
from pants.engine.rules import Get, collect_rules, rule
from pants.engine.target import DependenciesRequest, SourcesField, Targets
from pants.engine.unions import UnionRule
from pants.util.frozendict import FrozenDict
from pants.util.logging import LogLevel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReplaceTemplateFieldSet(PackageFieldSet):
    """Field set for Jinja template targets."""

    required_fields = (ReplaceTemplateDependenciesField,)

    dependencies: ReplaceTemplateDependenciesField

    template_mappings: ReplaceTemplateMappingsField

    template_suffix: ReplaceTemplateSuffxField


def _prepare_template_mappings(mappings: FrozenDict) -> Dict[str, str]:
    """Convert template mappings to a format suitable for Jinja2 rendering.

    Args:

        mappings: The frozen dictionary of template mappings



    Returns:

        A new dictionary with tuple values converted to newline-separated strings
    """

    return {
        key: "\n".join(value) if isinstance(value, tuple) else value
        for key, value in mappings.items()
    }


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


def _create_output_path(
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

    output_path = Path(f"{target_path}/{output_name}")

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

    output_path = _create_output_path(target_path, source_file, template_suffix)

    digest = await Get(Digest, PathGlobs([str(source_file)]))

    digest_contents = await Get(DigestContents, Digest, digest)

    if len(digest_contents) != 1:

        raise ValueError(
            f"Expected exactly one file, found {len(digest_contents)} in {source_file}"
        )

    file_content = digest_contents[0]

    template_content = file_content.content.decode("utf-8")

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


@rule(level=LogLevel.DEBUG)
async def run_replace_templates(
    replace_templates: ReplaceTemplates,
    field_set: ReplaceTemplateFieldSet,
) -> BuiltPackage:
    """Rule to render Jinja templates and create package artifacts.

    Args:

        replace_templates: The Jinja templates subsystem

        field_set: The field set containing template information



    Returns:

        A built package containing the rendered templates
    """

    logger.info(f"Processing template at {field_set.address.spec_path}")

    template_mappings = _prepare_template_mappings(field_set.template_mappings.value)

    targets = await Get(Targets, DependenciesRequest(field_set.dependencies))

    output_digests: List[FileContent] = []

    output_artifacts: List[BuiltPackageArtifact] = []

    for target in targets:

        try:

            file_content, artifact = await _process_template(
                target,
                template_mappings,
                field_set.address.spec_path,
                field_set.template_suffix.value if field_set.template_suffix else None,
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

    return [*collect_rules(), UnionRule(PackageFieldSet, ReplaceTemplateFieldSet)]
