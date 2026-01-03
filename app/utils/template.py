from jinja2 import Environment, FileSystemLoader, select_autoescape

env = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html"])
)

def render_template(template_path: str, **context) -> str:
    template = env.get_template(template_path)
    return template.render(**context)
