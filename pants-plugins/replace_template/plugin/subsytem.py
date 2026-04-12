from pants.engine.rules import collect_rules
from pants.option.subsystem import Subsystem


class ReplaceTemplates(Subsystem):

    options_scope = "replace_templates"

    help = """The ReplaceTemplate utility for rendering jinja2 templates."""


def rules():

    return [*collect_rules()]
