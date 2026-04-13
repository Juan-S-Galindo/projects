"""Target types for the Serverless plugin.

This module defines the target types and fields used by the Serverless
plugin to manage and deploy serverless applications.
"""

from typing import Any, Dict, Mapping, Optional, Tuple, Union

from pants.engine.addresses import Address
from pants.engine.target import (
    COMMON_TARGET_FIELDS,
    BoolField,
    Dependencies,
    Field,
    InvalidFieldTypeException,
    StringField,
    StringSequenceField,
    Target,
)
from pants.util.frozendict import FrozenDict

# Type aliases for better readability
TemplateValue = Union[str, Tuple[str, ...]]
TemplateMappings = Dict[str, TemplateValue]


class ServerlessFunctionsDependenciesField(Dependencies):
    """Field for specifying Lambda function dependencies.

    This field defines the list of Lambda functions that will be
    deployed as part of the serverless stack. Each dependency should
    reference a Lambda function target.
    """

    alias = "functions"
    value: Optional[list]
    help = "Array with all the lambda function targets that will be deployed."
    required = False
    default = None


class ServerlessResourcesDependenciesField(Dependencies):
    """Field for specifying resource dependencies.

    This field defines the list of AWS resources (like S3 buckets,
    DynamoDB tables, etc.) that will be deployed as part of the
    serverless stack. Each dependency should reference a resource
    target.
    """

    alias = "resources"
    value: Optional[list]
    help = "Array with all the resource targets that will be deployed."
    required = False
    default = None


class ServerlessConfigDependenciesField(Dependencies):
    """Field for specifying configuration file dependencies.

    This field defines the list of configuration files that will be used
    during deployment. These files typically contain environment-
    specific settings and parameters for the serverless stack.
    """

    alias = "config_files"
    value: Optional[list]
    help = "Array with all the config files that will be deployed."
    required = False
    default = None


class ServerlessSourceTemplateDependenciesField(Dependencies):
    """Field for specifying configuration file dependencies.

    This field defines the list of configuration files that will be used
    during deployment. These files typically contain environment-
    specific settings and parameters for the serverless stack.
    """

    alias = "source_templates"
    value: Optional[list]
    help = "Array with all the config files that will be deployed."
    required = False
    default = ["pants-plugins/serverless/plugin/serverless_templates:service", "//:serverless_global_config"]


class ServerlessServiceField(StringField):
    """Field for specifying the CloudFormation stack name.

    This field defines the name of the CloudFormation stack that will be
    created or updated during deployment. The stack name must be unique
    within an AWS account and region.
    """

    alias = "service"
    help = "The name of the stack to deploy."
    required = True



class ServerlessS3CleanerBucketNamesField(StringSequenceField):
    """Field for specifying the S3 bucket names to clean.

    This field defines the name of the S3 bucket that will be cleaned
    during the removal of stacks.
    """

    alias = "s3_cleaner_bucket_names"
    value: Optional[list]
    default = None
    help = "The name of the buckets to clean during the removal of stacks."
    required = False



def _freeze_config(raw: Any) -> Any:
    """Recursively freeze an arbitrary config value into hashable types.

    - Mappings become FrozenDicts.
    - Lists/tuples become tuples (items frozen recursively).
    - Everything else is coerced to str.
    """
    if isinstance(raw, Mapping):
        return FrozenDict({k: _freeze_config(v) for k, v in raw.items()})
    if isinstance(raw, (list, tuple)):
        return tuple(_freeze_config(item) for item in raw)
    return str(raw)


class ServerlessProviderConfigField(Field):
    """Field for configuring the serverless provider section.

    Each key maps to a top-level property under ``provider:`` in
    serverless.yml.  Values may be plain strings (SLS references like
    ``${env:FOO}`` are preserved verbatim) or nested dicts for multi-level
    YAML blocks (e.g. ``vpc``, ``tracing``).

    Use ``{{SERVICE_NAME}}`` in any string value to reference the resolved
    stack name.
    """

    alias = "provider_config"
    help = "Key/value pairs for the provider section of serverless.yml. Values may be strings or nested dicts."
    required = False
    default = FrozenDict({})

    @classmethod
    def compute_value(cls, raw_value: Optional[Any], address: Address) -> FrozenDict:
        if raw_value is None:
            return cls.default
        if not isinstance(raw_value, Mapping):
            raise InvalidFieldTypeException(
                address, cls.alias, raw_value, expected_type="a dict"
            )
        return _freeze_config(raw_value)


class ServerlessCustomConfigField(Field):
    """Field for configuring the serverless custom section.

    Each key maps to a top-level property under ``custom:`` in
    serverless.yml.  Values may be plain strings, nested dicts, or lists
    (e.g. ``retryLambdaServiceFailure``).

    Use ``{{SERVICE_NAME}}`` in any string value to reference the resolved
    stack name.
    """

    alias = "custom_config"
    help = "Key/value pairs for the custom section of serverless.yml. Values may be strings, nested dicts, or lists."
    required = False
    default = FrozenDict({})

    @classmethod
    def compute_value(cls, raw_value: Optional[Any], address: Address) -> FrozenDict:
        if raw_value is None:
            return cls.default
        if not isinstance(raw_value, Mapping):
            raise InvalidFieldTypeException(
                address, cls.alias, raw_value, expected_type="a dict"
            )
        return _freeze_config(raw_value)


class ServerlessImportGatewayField(Field):
    """Optional dict for the importApiGateway custom section entry.

    When set, ``- serverless-import-apigateway`` is automatically added
    to the plugins section and the value is merged into the ``custom:``
    block. Values may be plain strings, nested dicts, or lists.
    """

    alias = "import_gateway"
    help = (
        "Dict for the importApiGateway custom section entry. "
        "Setting this also enables the serverless-import-apigateway plugin."
    )
    required = False
    default = None

    @classmethod
    def compute_value(cls, raw_value: Optional[Any], address: Address) -> Optional[FrozenDict]:
        if raw_value is None:
            return None
        if not isinstance(raw_value, Mapping):
            raise InvalidFieldTypeException(
                address, cls.alias, raw_value, expected_type="a dict"
            )
        return _freeze_config(raw_value)


def _freeze_iam_statement(raw: dict) -> FrozenDict:
    return _freeze_config(raw)


class ServerlessGlobalIamStatementsField(Field):
    """Optional list of IAM statements for the provider iamRoleStatements
    block.

    When set, ``- serverless-iam-roles-per-function`` is automatically
    added to the plugins section. Each entry is a dict with ``Effect``,
    ``Action`` (list), and ``Resource`` (string or list) keys.
    """

    alias = "global_iam_statements"
    help = (
        "List of IAM statement dicts for the provider iamRoleStatements block. "
        "Setting this also enables the serverless-iam-roles-per-function plugin."
    )
    required = False
    default = None

    @classmethod
    def compute_value(
        cls, raw_value: Optional[Any], address: Address
    ) -> Optional[Tuple[FrozenDict, ...]]:
        if raw_value is None:
            return None
        if not isinstance(raw_value, (list, tuple)):
            raise InvalidFieldTypeException(
                address,
                cls.alias,
                raw_value,
                expected_type="a list of IAM statement dicts",
            )
        return tuple(_freeze_iam_statement(s) for s in raw_value)


class ServerlessTemplateTarget(Target):
    """A target for managing serverless application deployments.

    This target type is used to define and manage serverless application
    deployments. It combines Lambda functions, AWS resources, and
    configuration files into a single deployable unit. The target
    handles the packaging and deployment of all components to AWS using
    CloudFormation.
    """

    alias = "serverless"
    core_fields = (
        *COMMON_TARGET_FIELDS,
        ServerlessFunctionsDependenciesField,
        ServerlessResourcesDependenciesField,
        ServerlessServiceField,
        ServerlessConfigDependenciesField,
        ServerlessSourceTemplateDependenciesField,
        ServerlessS3CleanerBucketNamesField,
        ServerlessProviderConfigField,
        ServerlessCustomConfigField,
        ServerlessImportGatewayField,
        ServerlessGlobalIamStatementsField,
    )
    help = "A target for managing and deploying serverless applications to AWS"
