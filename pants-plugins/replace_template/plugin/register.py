from replace_templates.plugin import subsystem
from replace_templates.plugin.rules import rules as replace_rules
from replace_templates.plugin.target_types import ReplaceTemplateTarget


def rules():

    return [*replace_rules(), *subsystem.rules()]


def target_types():

    return [ReplaceTemplateTarget]
