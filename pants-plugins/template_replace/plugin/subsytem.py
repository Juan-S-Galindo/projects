from pants.engine.rules import collect_rules
from pants.option.subsystem import Subsystem


class JinjaTemplates(Subsystem):

    options_scope = "jinja_templates"

    help = """The JinjaTemplate utility for rendering jinja2 templates."""


def rules():

    return [*collect_rules()]
