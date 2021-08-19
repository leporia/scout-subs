from django import template
from django.db.models.query_utils import Q
from client.models import Document, KeyVal

register = template.Library()
@register.filter(name="doc_key")
def doc_key(doc):
    return KeyVal.objects.filter(container=doc)

@register.filter(name="user_docs")
def user_docs(admin_user, user):
    parent_group = admin_user.groups.values_list('name', flat=True)[0]
    documents = Document.objects.filter(Q(user=user) & ~Q(status='archive') & Q(group__name=parent_group))
    return documents

@register.filter(name="user_groups")
def user_groups(user):
    return user.groups.values_list('name', flat=True)

@register.filter(name="user_primary_group")
def user_primary_group(user):
    return user.groups.values_list('name', flat=True)[0]