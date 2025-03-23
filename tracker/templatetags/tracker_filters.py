from django import template

register = template.Library()


@register.filter
def subtract(value, arg):
    return value - arg


@register.filter
def percentage(value, arg):
    if arg == 0:
        return 0
    return round((value / arg) * 100, 2)
