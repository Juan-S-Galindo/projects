from serverless.plugin import subsystem
from serverless.plugin.rules import rules as jinja_rules
from serverless.plugin.target_types import ServerlessTemplateTarget


def rules():
    return [*jinja_rules(), *subsystem.rules()]


def target_types():
    return [ServerlessTemplateTarget]
