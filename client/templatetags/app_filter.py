from django import template
from client.models import KeyVal

register = template.Library()
@register.filter(name="doc_key")
def doc_key(doc):
    return KeyVal.objects.filter(container=doc)