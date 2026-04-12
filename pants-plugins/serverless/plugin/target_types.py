"""Target types for the Serverless plugin.

This module defines the target types and fields used by the Serverless
plugin to manage and deploy serverless applications.
"""

from typing import Any, Dict, Optional, Tuple, Union

from pants.engine.addresses import Address
from pants.engine.target import (
    COMMON_TARGET_FIELDS,
    BoolField,
    Dependencies,
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
    default = ["internal/serverless_templates:service", "//:serverless_global_config"]


class ServerlessStackNameField(StringField):
    """Field for specifying the CloudFormation stack name.

    This field defines the name of the CloudFormation stack that will be
    created or updated during deployment. The stack name must be unique
    within an AWS account and region.
    """

    alias = "stack_name"
    help = "The name of the stack to deploy."
    required = True


class ServerlessDeploymentBucketNameField(StringField):
    """Field for specifying the S3 deployment bucket name.

    This field defines the name of the S3 bucket that will be used to
    store deployment artifacts. The bucket must exist and be accessible
    to the deployment process.
    """

    alias = "deployment_bucket"
    help = "The name of the bucket to deploy deployment artifacts to."
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


class ServerlessDeployApiGatewayField(BoolField):
    """Field for specifying if the API Gateway should be deployed.

    This field defines if the API Gateway should be deployed.
    """

    alias = "deploy_api_gateway"
    value: Optional[bool]
    default = False
    help = "If the API Gateway should be deployed."
    required = False


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
        ServerlessStackNameField,
        ServerlessDeploymentBucketNameField,
        ServerlessConfigDependenciesField,
        ServerlessSourceTemplateDependenciesField,
        ServerlessS3CleanerBucketNamesField,
        ServerlessDeployApiGatewayField,
    )
    help = "A target for managing and deploying serverless applications to AWS"