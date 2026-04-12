from jinja_templates.plugin import subsystem
from jinja_templates.plugin.rules import rules as jinja_rules
from jinja_templates.plugin.target_types import JinjaTemplateTarget


def rules():

    return [*jinja_rules(), *subsystem.rules()]


def target_types():

    return [JinjaTemplateTarget]
