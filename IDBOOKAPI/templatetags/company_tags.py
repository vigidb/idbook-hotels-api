"""Template tag to expose the central COMPANY info inside any Django template.

Usage in a template:

    {% load company_tags %}
    {% company_info as company %}
    {{ company.legal_name }}
    {{ company.address.hq.line }}

This avoids having to thread ``company`` through every render_to_string / task
call site, and keeps ``IDBOOKAPI/company_info.py`` as the single source of truth.
"""

from django import template

from IDBOOKAPI.company_info import COMPANY

register = template.Library()


@register.simple_tag
def company_info():
    return COMPANY
