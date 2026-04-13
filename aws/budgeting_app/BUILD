file(
    name = "environment",
    source = "environment.yml",
)

file(
    name = "resources",
    source = "resources.s3.yml",
)

serverless(
    name="sls",
    service="budgeting-app-${env:DEPLOY_TAG}",
    config_files=[":environment"],
    resources = [
        "aws/budgeting_app:resources"
    ],
    functions = [
        "aws/budgeting_app/ingest:function"
    ],
    tags = ['serverless'],
    provider_config =
    {
        "stackName": "budgeting-app-${env:DEPLOY_TAG}",
        "architecture": "${env:CPU_ARCH}",
        "region": "${env:AWS_REGION}",
        "versionFunctions": "false",
        "environment": "${file(environment.yml):environment}",
        "stackTags": "${file(environment.yml):stackTags.common}",
        "timeout": "60",
        "tracing": {"lambda": "true"},
        "vpc": {
            "securityGroupIds": "${file(serverless_global_config.yml):${env:AWS_ACCOUNT_NAME}.${env:AWS_REGION}.vpc.securityGroupIds}",
            "subnetIds": "${file(serverless_global_config.yml):${env:AWS_ACCOUNT_NAME}.${env:AWS_REGION}.vpc.subnetIds}",
        },
        "deploymentBucket": {
            "name": "my-deploy-bucket",
        },
    },
    global_iam_statements = [
  {
    "Effect": "Allow",
    "Action": [
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords",
      "xray:GetSamplingRules",
      "xray:GetSamplingTargets",
      "xray:GetSamplingStatisticSummaries"
    ],
    "Resource": "*"
  },
  {
    "Effect": "Allow",
    "Action": [
      "ec2:DescribeNetworkInterfaces",
      "ec2:CreateNetworkInterface",
      "ec2:DeleteNetworkInterface",
      "ec2:DescribeInstances",
      "ec2:AttachNetworkInterface",
      "ec2:AssignPrivateIpAddresses",
      "ec2:UnassignPrivateIpAddresses"
    ],
    "Resource": "*"
  },
  {
    "Effect": "Allow",
    "Action": [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams"
    ],
    "Resource": "*"
  },
  {
    "Effect": "Allow",
    "Action": [
      "kms:Sign"
    ],
    "Resource": "${file(serverless_global_config.yml):${env:AWS_ACCOUNT_NAME}.${env:AWS_REGION}.iam_kms_permissions.kms_aliases}"
  },
  {
    "Effect": "Allow",
    "Action": [
      "kms:GenerateDataKey",
      "kms:Decrypt"
    ],
    "Resource": "${file(serverless_global_config.yml):${env:AWS_ACCOUNT_NAME}.${env:AWS_REGION}.iam_kms_permissions.kms_keys}"
  },
],
custom_config = {
  "retryLambdaServiceFailure": [
    {
      "ErrorEquals": [
        "Lambda.ServiceException",
        "Lambda.AWSLambdaException",
        "Lambda.SdkClientException"
      ],
      "IntervalSeconds": 2,
      "MaxAttempts": 6,
      "BackoffRate": 2
    }
  ],
  "authorizer": {
    "type": "CUSTOM",
    "authorizerId": "!ImportValue ApiGatewayAuthorizerId-${env:DEPLOY_TAG}"
  },
  "aws": {
    "tags": "${file(serverless_global_config.yml):tags}",
    "KmsMasterKeyId": "${file(serverless_global_config.yml):common.kms.key.${env:AWS_ACCOUNT_NAME}}"
  }
},
s3_cleaner_bucket_names = ['test-bucket-to-clean'],
import_gateway={
        "importApiGateway": {
            "name": "${env:AWS_ACCOUNT_NAME_ABBREVIATION}-${env:DEPLOY_TAG}",
            "path": "/",
            "resources": ["/v3"],
        }
    },
)
