# dictionary

from django import template 

register = template.Library() 

@register.filter() 
def get_key_based_value(dictionary, key):
    return dictionary.get(key, '')

