from pants.engine.rules import collect_rules
from pants.option.subsystem import Subsystem


class ServerlessTemplates(Subsystem):
    options_scope = "serverless_templates"
    help = """The Serverless utility for managing and deploying serverless applications to AWS."""


def rules():
    return [*collect_rules()]
