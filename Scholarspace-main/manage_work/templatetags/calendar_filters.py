from django import template

register = template.Library()

@register.filter
def lookup(dictionary, key):
    """
    Look up a key in a dictionary.
    Usage: {{ my_dict|lookup:key }}
    """
    return dictionary.get(key, [])
