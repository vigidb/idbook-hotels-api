import os
from jinja2 import Environment, FileSystemLoader
from pyhtml2pdf import converter

root = os.path.dirname(os.path.abspath(__file__))

templates_dir = os.path.join(root, '')
env = Environment(loader=FileSystemLoader(templates_dir))
html_template = "pdf.html"
template = env.get_template(html_template)
filename = os.path.join(root, '', html_template)

