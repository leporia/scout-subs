from django import template
from django.db.models.query_utils import Q
from client.models import Document, KeyVal, Keys

import json

register = template.Library()
@register.filter(name="doc_key")
def doc_key(doc):
    return KeyVal.objects.filter(container=doc)

@register.filter(name="doc_key_type")
def doc_key_type(doc_type):
    return Keys.objects.filter(container=doc_type)

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

@register.filter(name="doc_count")
def doc_count(doc):
    doc_count = str(Document.objects.filter(document_type=doc).count())
    ref_docs_archived = Document.objects.filter(document_type=doc, status="archive").count()
    if ref_docs_archived > 0:
        doc_count += "-" + str(ref_docs_archived)
    if doc.max_instances != 0:
        doc_count += "/" + str(doc.max_instances)

    return doc_count

@register.filter(name="parse_multiple_choice")
def parse_multiple_choice(str):
    if len(str) < 3:
        return [str, []]

    str = str[3:]
    arr = str.split(",")
    if len(arr) < 2:
        return [arr[0], []]

    return [arr[0], arr[1:]]

@register.filter(name="parse_userswitcher")
def parse_userswitcher(str):
    if not str:
        return []

    return json.loads(str).keys()