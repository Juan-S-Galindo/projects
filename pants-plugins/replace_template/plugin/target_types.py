"""Target types for the Jinja templates plugin.

This module defines the target types and fields used by the Jinja

templates plugin to render Jinja2 templates with variable substitution.
"""

from typing import Any, Dict, Optional, Tuple, Union

from pants.engine.addresses import Address
from pants.engine.target import (
    COMMON_TARGET_FIELDS,
    Dependencies,
    Field,
    StringField,
    Target,
)
from pants.util.frozendict import FrozenDict

# Type aliases for better readability

TemplateValue = Union[str, Tuple[str, ...]]

TemplateMappings = Dict[str, TemplateValue]


class ReplaceTemplateDependenciesField(Dependencies):
    """Field for specifying dependencies of a Jinja template target."""


class ReplaceTemplateMappingsField(Field):
    """Field for specifying template variable mappings.

    This field accepts a dictionary where:

    - Keys must be strings

    - Values can be either strings or tuples of strings
    """

    alias = "template_mappings"

    value: Optional[TemplateMappings]

    help = "A dictionary of string keys and values, or string keys and arrays of strings, used for template variable substitution."

    required = False

    default = FrozenDict()

    @classmethod
    def compute_value(cls, raw_value: Any, address: Address) -> TemplateMappings:
        """Validate and compute the template mappings value.

        Args:

            raw_value: The raw input value to validate

            address: The address of the target being processed



        Returns:

            A validated dictionary of template mappings



        Raises:

            ValueError: If the input is not a valid template mapping
        """

        if raw_value is None:

            return FrozenDict()

        if not isinstance(raw_value, FrozenDict):

            raise ValueError(f"Expected a dictionary, got {type(raw_value)}")

        for key, value in raw_value.items():

            if not isinstance(key, str):

                raise ValueError(f"Expected string key, got {type(key)}")

            if not isinstance(value, (str, tuple)):

                raise ValueError(f"Expected string or tuple value, got {type(value)}")

            if isinstance(value, tuple):

                if not all(isinstance(item, str) for item in value):

                    raise ValueError("All items in tuple values must be strings")

        return raw_value


class ReplaceTemplateSuffxField(StringField):
    """Field for specifying a custom output filename.

    If provided, this field overrides the default output filename

    pattern. The file extension from the source template will be

    preserved.
    """

    alias = "templete_suffix"

    value: Optional[str]

    help = "Suffix used to identify templates. Files with this suffix will be rendered."

    required = False

    default = None


class ReplaceTemplateTarget(Target):
    """A target for rendering Jinja2 templates with variable substitution.

    This target takes a Jinja2 template file and renders it using the

    provided template mappings. The rendered output is written to a file

    in the dist directory.
    """

    alias = "replace_templates_distribution"

    core_fields = (
        *COMMON_TARGET_FIELDS,
        ReplaceTemplateDependenciesField,
        ReplaceTemplateMappingsField,
        ReplaceTemplateSuffxField,
    )

    help = "The `replace_template` target will take in a file with jinja2 templates and render them"
