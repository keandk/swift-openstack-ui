from django import template
from datetime import datetime

register = template.Library()

@register.filter(name='dateconv')
def dateconv(timestamp):
    try:
        return datetime.fromtimestamp(float(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return timestamp