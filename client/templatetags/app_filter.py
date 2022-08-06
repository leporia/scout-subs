from django import template
from django.db.models.query_utils import Q
from client.models import Document, GroupSettings, KeyVal, Keys

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
    parent_groups = admin_user.groups.values_list('name', flat=True)
    documents = Document.objects.filter(Q(user=user) & ~Q(status='archive') & Q(document_type__group__name__in=parent_groups))
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

@register.filter(name="is_multiple_choice")
def is_multiple_choice(str):
    return str.startswith("!m")

@register.filter(name="is_checkbox")
def is_checkbox(str):
    return str.startswith("!c")

@register.filter(name="is_heading")
def is_heading(str):
    return str.startswith("!t")

@register.filter(name="parse_multiple_choice")
def parse_multiple_choice(str):
    if len(str) < 3:
        return [str, []]

    str = str[3:]
    arr = str.split(",")
    if len(arr) < 2:
        return [arr[0], []]

    return [arr[0], arr[1:]]

@register.filter(name="parse_heading")
def parse_heading(str):
    if len(str) < 3:
        return str
    return str[3:]

@register.filter(name="parse_userswitcher")
def parse_userswitcher(str):
    if not str:
        return []

    return json.loads(str).keys()

@register.filter(name="user_list")
def user_list(user):
    # get user group
    groups = user.groups.all()

    # check if any group has enabled RO documents
    if user.is_staff or len(groups.filter(name="capi")) == 0:
        # if user is staff then not needed
        gr = []
    elif user.has_perm("client.staff"):
        gr = GroupSettings.objects.filter(group__in=groups).filter(view_documents=True).filter(~Q(group=groups[0]))
    else:
        gr = GroupSettings.objects.filter(group__in=groups).filter(view_documents=True)

    return (len(gr) != 0)