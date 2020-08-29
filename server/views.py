from django.shortcuts import render
from client.models import UserCode, Keys, DocumentType, Document, KeyVal
from django.contrib.auth.models import Group, Permission, User
from django.db.models import Q
from django.http import HttpResponseRedirect, FileResponse
from django.db.models.deletion import ProtectedError
from django.template.loader import get_template
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.contenttypes.models import ContentType

import dateparser
from datetime import datetime
from datetime import timedelta
import pytz
import pdfkit
from io import BytesIO
import os
import base64
from PIL import Image, UnidentifiedImageError


# custom staff check function for non primary group staff members
def isStaff(user):
    if user.is_staff:
        return True
    if user.has_perm("client.staff"):
        return True
    return False


@user_passes_test(isStaff)
def index(request):
    context = {}
    # primary group name + object
    parent_group = request.user.groups.values_list('name', flat=True)[
        0]
    group = Group.objects.get(name=parent_group)
    # users from younger to older
    users = User.objects.filter(groups__name=parent_group).order_by("-id")
    users_out = []

    # only send part of the user data, only if user is approved
    for user in users:
        if not user.has_perm("client.approved") and not user.is_staff:
            continue

        users_out.append([user.username, user.first_name,
                          user.last_name])

    # if user is staff of not primary show only public types
    if request.user.is_staff:
        public_types = DocumentType.objects.filter(
            Q(group_private=False) | Q(group=group) & Q(enabled=True)).order_by("-id")
    else:
        public_types = DocumentType.objects.filter(
            Q(group_private=False) & Q(enabled=True)).order_by("-id")

    # count documents of that type to show statistics
    docs = []
    for doc in public_types:
        ref_docs = Document.objects.filter(document_type=doc)
        docs.append([doc, len(ref_docs)])

    # don't list users if user is staff of not primary
    if request.user.is_staff:
        context = {
            'docs': docs,
            'users': users_out,
        }
    else:
        context = {
            'docs': docs,
        }
    return render(request, 'server/index.html', context)


@staff_member_required
def uapprove(request):
    context = {}
    data = []
    if request.method == "POST":
        # get group name and obj
        parent_group = request.user.groups.values_list('name', flat=True)[
            0]
        group = Group.objects.get(name=parent_group)

        # get permission object
        permission = Permission.objects.get(codename='approved')

        # parse text to array
        data = request.POST["codes"]
        data.replace("\r", "")
        data = data.split("\n")
        # check if format is right
        for i in range(len(data)):
            if not data[i].startswith("U"):
                data[i] = data[i] + " - Formato errato"
            elif not data[i][1:].isdigit():
                data[i] = data[i] + " - Formato errato"
            elif int(data[i][1:]) < 100000 or int(data[i][1:]) > 999999:
                data[i] = data[i] + " - Formato errato"
            elif len(UserCode.objects.filter(code=data[i][1:])) == 0:
                data[i] = data[i] + " - Invalido"
            else:
                user = UserCode.objects.filter(code=data[i][1:])[0].user
                user.user_permissions.add(permission)
                # if user not in any group add to the same group as staff
                if len(user.groups.values_list('name', flat=True)) == 0:
                    user.groups.add(group)
                    data[i] = data[i] + " - Ok"
                else:
                    if user.groups.values_list('name', flat=True)[0] == parent_group:
                        # if user already in group do nothing
                        data[i] = data[i] + " - Ok"
                    else:
                        # if user in another group notify staff of group change
                        user.groups.clear()
                        user.groups.add(group)
                        data[i] = data[i] + " - Ok, cambio branca"

    context = {
        'messages': data,
        'empty': len(data) == 0,
    }

    return render(request, 'server/approve_user.html', context)


@user_passes_test(isStaff)
def docapprove(request):
    context = {}
    data = []

    # group name and obj
    parent_group = request.user.groups.values_list('name', flat=True)[
        0]
    group = Group.objects.get(name=parent_group)

    # if user not staff of primary has only controll of non primary groups
    if request.user.is_staff:
        groups = request.user.groups.values_list('name', flat=True)
    else:
        groups = request.user.groups.values_list('name', flat=True)[1:]

    if request.method == "POST":
        # parse text in array
        data = request.POST["codes"]
        data.replace("\r", "")
        data = data.split("\n")
        # check if code valid
        for i in range(len(data)):
            print(Document.objects.filter(code=data[i])[0].group.name)
            if not data[i].isdigit():
                data[i] = data[i] + " - Formato errato"
            elif int(data[i]) < 100000 or int(data[i]) > 999999:
                data[i] = data[i] + " - Formato errato"
            elif len(Document.objects.filter(code=data[i])) == 0:
                data[i] = data[i] + " - Invalido"
            elif Document.objects.filter(code=data[i])[0].group.name not in groups:
                # check if user has permission to approve document
                data[i] = data[i] + " - Invalido"
            else:
                document = Document.objects.filter(code=data[i])[0]
                if document.status == 'ok':
                    # do nothing document already approved
                    data[i] = data[i] + " - Già approvato"
                else:
                    document.status = 'ok'
                    document.save()
                    data[i] = data[i] + " - Ok"

    context = {
        'messages': data,
        'empty': len(data) == 0,
    }

    return render(request, 'server/approve_doc.html', context)


@staff_member_required
def ulist(request):
    context = {}
    # group name and obj
    parent_group = request.user.groups.values_list('name', flat=True)[0]
    group = Group.objects.get(name=parent_group)

    if request.method == "POST":
        # request to download document
        if request.POST["action"][0] == 'f':
            document = Document.objects.get(id=request.POST["action"][1:])
            # check if user has permission to view document
            if document.group == group:
                vac_file = ""
                health_file = ""
                sign_doc_file = ""

                # prepare pictures in base64
                if document.medical_data:
                    if document.medical_data.vac_certificate.name:
                        with open(document.medical_data.vac_certificate.name, 'rb') as image_file:
                            vac_file = base64.b64encode(
                                image_file.read()).decode()

                    if document.medical_data.health_care_certificate.name:
                        with open(document.medical_data.health_care_certificate.name, 'rb') as image_file:
                            health_file = base64.b64encode(
                                image_file.read()).decode()
                if document.signed_doc:
                    with open(document.signed_doc.name, 'rb') as image_file:
                        sign_doc_file = base64.b64encode(
                            image_file.read()).decode()

                # get template and build context
                template = get_template('server/download_doc.html')
                doc = [document, KeyVal.objects.filter(
                    container=document), document.personal_data, document.medical_data, parent_group]
                context = {'doc': doc, 'vac': vac_file,
                           'health': health_file, 'sign_doc_file': sign_doc_file}
                # render context
                html = template.render(context)
                # render pdf using wkhtmltopdf
                pdf = pdfkit.from_string(html, False, options={'javascript-delay':'1000'})
                result = BytesIO(pdf)
                result.seek(0)

                return FileResponse(result, as_attachment=True, filename=document.user.username+"_"+document.document_type.name+".pdf")

        # deapprove user
        elif request.POST["action"][0] == 'd':
            user = User.objects.get(id=request.POST["action"][1:])
            # check if user has permission to deapprove user
            if user.groups.all()[0] == group:
                content_type = ContentType.objects.get_for_model(Document)
                permission = Permission.objects.get(
                    content_type=content_type, codename="approved")
                user.user_permissions.remove(permission)
                return HttpResponseRedirect("ulist")

    # list users with their documents
    users = User.objects.filter(
        groups__name=parent_group).order_by("first_name")
    out = []
    for user in users:
        # list only approved users
        if not user.has_perm("client.approved") and not user.is_staff:
            continue

        usercode = UserCode.objects.filter(user=user)[0]
        # get all user documents
        documents = Document.objects.filter(Q(user=user) & ~Q(
            status='archive') & Q(group__name=parent_group))

        # encode images in base64
        vac_file = ""
        health_file = ""
        sign_doc_file = ""
        if usercode.medic:
            if usercode.medic.vac_certificate.name:
                with open(usercode.medic.vac_certificate.name, 'rb') as image_file:
                    vac_file = base64.b64encode(image_file.read()).decode()

            if usercode.medic.health_care_certificate.name:
                with open(usercode.medic.health_care_certificate.name, 'rb') as image_file:
                    health_file = base64.b64encode(image_file.read()).decode()
        out.append([user, usercode, parent_group,
                    documents, vac_file, health_file])
    context = {'users': out}
    return render(request, 'server/user_list.html', context)


@user_passes_test(isStaff)
def doctype(request):
    context = {}

    # error variables to throw at user
    error = False
    error_text = ""

    # init checkboxes
    public = True
    selfsign = True
    hidden = False
    personal = True
    medic = True
    custom = True
    message = True
    group_bool = True
    public_check = 'checked="checked"'
    selfsign_check = 'checked="checked"'
    hidden_check = 'checked="checked"'
    personal_check = 'checked="checked"'
    medic_check = 'checked="checked"'
    custom_check = 'checked="checked"'
    message_check = 'checked="checked"'
    group_check = 'checked="checked"'

    if request.method == "POST":
        selected = []
        # if user not staff of primary get only non primary groups
        if request.user.is_staff:
            parent_groups = request.user.groups.values_list('name', flat=True)
        else:
            parent_groups = request.user.groups.values_list('name', flat=True)[
                1:]

        # list all selected types
        for i in request.POST.keys():
            if i.isdigit():
                docc = DocumentType.objects.get(id=i)
                # check if user has permission
                if docc.group.name in parent_groups:
                    selected.append(docc)
                else:
                    error = True
                    error_text = "Non puoi modificare un documento non del tuo gruppo"

        # execute action on selected types
        for i in selected:
            if request.POST["action"] == 'delete':
                try:
                    i.delete()
                except ProtectedError:
                    error = True
                    error_text = "Non puoi eliminare un tipo a cui é collegato uno o piú documenti"
            elif request.POST["action"] == 'hide':
                i.enabled = False
                i.save()
            elif request.POST["action"] == 'show':
                i.enabled = True
                i.save()

        # check which filters are applied
        public = "filter_public" in request.POST
        selfsign = "filter_selfsign" in request.POST
        hidden = "filter_hidden" in request.POST
        personal = "filter_personal" in request.POST
        medic = "filter_medic" in request.POST
        custom = "filter_custom" in request.POST
        message = "filter_message" in request.POST
        group_bool = "filter_group" in request.POST

        # check if request to clear filters
        if request.POST["action"] == 'clear':
            public = True
            selfsign = True
            hidden = False
            personal = True
            medic = True
            custom = True
            message = True
            group_bool = True

    # group name and obj
    parent_group = request.user.groups.values_list('name', flat=True)[
        0]
    group = Group.objects.get(name=parent_group)

    # if user not staff of primary group show only public types
    if request.user.is_staff:
        public_types = DocumentType.objects.filter(
            Q(group_private=False) | Q(group=group))
    else:
        public_types = DocumentType.objects.filter(
            Q(group_private=False))

    # apply filters
    if not public:
        public_types = public_types.filter(group_private=True)
        public_check = ""
    if not selfsign:
        public_types = public_types.filter(auto_sign=False)
        selfsign_check = ""
    if not hidden:
        public_types = public_types.filter(enabled=True)
        hidden_check = ""
    if not personal:
        public_types = public_types.filter(personal_data=False)
        personal_check = ""
    if not medic:
        public_types = public_types.filter(medical_data=False)
        medic_check = ""
    if not custom:
        public_types = public_types.filter(custom_data=False)
        custom_check = ""
    if not message:
        public_types = public_types.filter(custom_message=False)
        message_check = ""
    if not group_bool:
        public_types = public_types.filter(custom_group=False)
        group_check = ""

    # get custom keys from types
    out = []
    for doc in public_types:
        custom_keys = Keys.objects.filter(container=doc)
        ref_docs = Document.objects.filter(document_type=doc)
        out.append([doc, custom_keys, len(ref_docs)])

    context = {
        'docs': out,
        'public_check': public_check,
        'selfsign_check': selfsign_check,
        'hidden_check': hidden_check,
        'personal_check': personal_check,
        'medic_check': medic_check,
        'custom_check': custom_check,
        'message_check': message_check,
        'group_check': group_check,
        'error': error,
        'error_text': error_text,
    }
    return render(request, 'server/doc_type.html', context)


@user_passes_test(isStaff)
def doccreate(request):
    context = {}

    # if user is not staff of primary set default group to secondary and default public type
    if request.user.is_staff:
        groups = request.user.groups.values_list('name', flat=True)
        parent_group = request.user.groups.values_list('name', flat=True)[
            0]
        group_private = False
        private_check = 'checked="checked"'
    else:
        groups = request.user.groups.values_list('name', flat=True)[1:]
        parent_group = request.user.groups.values_list('name', flat=True)[
            1]
        group_private = True
        private_check = ''

    # get group obj
    group = Group.objects.get(name=parent_group)

    # init checkboxes
    enabled = False
    personal_data = False
    medical_data = False
    custom_data = False
    custom_group_bool = False
    name = ""
    custom_group = ""

    enabled_check = 'checked="checked"'
    personal_check = 'checked="checked"'
    sign_check = 'checked="checked"'
    medical_check = ""
    custom_check = ""
    custom_message_check = ""

    # if type create request sent
    if request.method == "POST":
        # gather inserted data
        enabled = "enabled" in request.POST.keys()
        auto_sign = "sign" not in request.POST.keys()
        group_private = "group_private" in request.POST.keys()
        personal_data = "personal_data" in request.POST.keys()
        medical_data = "medical_data" in request.POST.keys()
        custom_data = "custom_data" in request.POST.keys()
        custom_message = "custom_message" in request.POST.keys()
        custom_message_text = request.POST["custom_message_text"]
        name = request.POST["name"]
        custom_group = request.POST["custom_group"]

        # if group not primary and not public throw error
        if group_private == True and not request.user.is_staff:
            context["error"] = "true"
            context["error_text"] = "Non puoi creare un documento non pubblico per un gruppo non primario"
            return render(request, 'server/doc_create.html', context)

        # if already existing name throw error
        if len(DocumentType.objects.filter(name=name)) > 0:
            context["error"] = "true"
            context["error_text"] = "Questo nome esiste già. Prego usarne un altro."
            return render(request, 'server/doc_create.html', context)

        # check if custom group permissions not met or non public document
        if custom_group != "":
            if group_private == True:
                context["error"] = "true"
                context["error_text"] = "Non puoi creare un documento non pubblico per un gruppo non primario"
                return render(request, 'server/doc_create.html', context)
            if custom_group not in groups:
                context["error"] = "true"
                context["error_text"] = "Non puoi creare un tipo assegnato ad un gruppo di cui non fai parte"
                return render(request, 'server/doc_create.html', context)
            else:
                group = Group.objects.filter(name=custom_group)[0]
                custom_group_bool = True

        # create type
        doctype = DocumentType(
            custom_group=custom_group_bool, auto_sign=auto_sign, custom_message=custom_message, custom_message_text=custom_message_text, name=request.POST["name"], enabled=enabled, group_private=group_private, group=group, personal_data=personal_data, medical_data=medical_data, custom_data=custom_data)
        doctype.save()

        # create custom keys
        if custom_data:
            custom = request.POST["custom"]
            custom.replace("\r", "")
            custom = custom.split("\n")
            for i in custom:
                key = Keys(key=i, container=doctype)
                key.save()

        return HttpResponseRedirect('doctype')

    # build context
    context = {
        "enabled_check": enabled_check,
        "private_check": private_check,
        "sign_check": sign_check,
        "personal_check": personal_check,
        "medical_check": medical_check,
        "custom_check": custom_check,
        "custom_message_check": custom_message_check,
    }

    return render(request, 'server/doc_create.html', context)


@user_passes_test(isStaff)
def doclist(request):
    context = {}

    # group name and obj
    parent_group = request.user.groups.values_list('name', flat=True)[
        0]
    group = Group.objects.get(name=parent_group)

    # if user not staff of primary get secondary groups
    if request.user.is_staff:
        parent_groups = request.user.groups.values_list('name', flat=True)
    else:
        parent_groups = request.user.groups.values_list('name', flat=True)[1:]

    # create typezone
    zurich = pytz.timezone('Europe/Zurich')

    # init error variables for users
    error = False
    error_text = ""

    # init checkboxes for filter
    hidden = False
    wait = True
    selfsign = True
    ok = True
    signdoc = False

    hidden_check = 'checked="checked"'
    wait_check = 'checked="checked"'
    selfsign_check = 'checked="checked"'
    ok_check = 'checked="checked"'
    signdoc_check = 'checked="checked"'

    # set default dates for filters
    newer = zurich.localize(dateparser.parse("1970-01-01"))
    older = zurich.localize(datetime.now())

    # init chips values
    owner = []
    types = []
    groups = []
    chips_owner = []
    chips_types = []
    chips_groups = []

    if request.method == "POST":
        # if download request
        if request.POST["action"][0] == 'k':
            document = Document.objects.get(id=request.POST["action"][1:])
            # check if user has permission to view doc
            if document.group.name in parent_groups:
                vac_file = ""
                health_file = ""
                sign_doc_file = ""

                # prepare images in base64
                if document.medical_data:
                    if document.medical_data.vac_certificate.name:
                        with open(document.medical_data.vac_certificate.name, 'rb') as image_file:
                            vac_file = base64.b64encode(
                                image_file.read()).decode()

                    if document.medical_data.health_care_certificate.name:
                        with open(document.medical_data.health_care_certificate.name, 'rb') as image_file:
                            health_file = base64.b64encode(
                                image_file.read()).decode()

                if document.signed_doc:
                    with open(document.signed_doc.name, 'rb') as image_file:
                        sign_doc_file = base64.b64encode(
                            image_file.read()).decode()

                # build with template and render
                template = get_template('server/download_doc.html')
                doc = [document, KeyVal.objects.filter(
                    container=document), document.personal_data, document.medical_data, parent_group]
                context = {'doc': doc, 'vac': vac_file,
                           'health': health_file, 'sign_doc_file': sign_doc_file}
                html = template.render(context)
                pdf = pdfkit.from_string(html, False, options={'javascript-delay':'1000'})
                result = BytesIO(pdf)
                result.seek(0)

                return FileResponse(result, as_attachment=True, filename=document.user.username+"_"+document.document_type.name+".pdf")

        # get selected documents and check if user has permission to view
        selected = []
        for i in request.POST.keys():
            if i.isdigit():
                docc = Document.objects.get(id=i)
                if docc.group.name in parent_groups:
                    selected.append(docc)

        # execute action on selected documents
        for i in selected:
            if request.POST["action"] == 'delete' and settings.DEBUG:
                i.delete()
            elif request.POST["action"] == 'approve' and settings.DEBUG:
                i.status = 'ok'
                i.save()
            elif request.POST["action"] == 'archive':
                if i.status == 'ok':
                    i.status = 'archive'
                    if i.medical_data:
                        i.medical_data.delete()
                        i.medical_data.save()
                    i.save()
                else:
                    error = True
                    error_text = "Non puoi archiviare un documento non approvato"
            elif request.POST["action"] == 'unarchive':
                if i.status == 'archive':
                    i.status = 'ok'
                    i.save()
                else:
                    error = True
                    error_text = "Non puoi dearchiviare un documento non archiviato"

        # get filter values
        hidden = "filter_hidden" in request.POST
        wait = "filter_wait" in request.POST
        selfsign = "filter_selfsign" in request.POST
        ok = "filter_ok" in request.POST
        signdoc = "filter_signdoc" in request.POST
        newer = zurich.localize(dateparser.parse(request.POST["newer"]))
        older = zurich.localize(dateparser.parse(
            request.POST["older"]) + timedelta(days=1))
        owner = request.POST["owner"].split("^|")
        types = request.POST["type"].split("^|")
        groups = request.POST["groups"].split("^|")

        # clear filters
        if request.POST["action"] == 'clear':
            hidden = False
            wait = True
            selfsign = True
            ok = True
            signdoc = False
            newer = zurich.localize(dateparser.parse("1970-01-01"))
            older = zurich.localize(datetime.now())
            owner = []
            types = []
            groups = []

    # filter documents based on group of staff
    q_obj = Q()
    for i in parent_groups:
        q_obj |= Q(group__name=i)

    documents = Document.objects.filter(q_obj)

    # filter documents
    if not hidden:
        documents = documents.filter(~Q(status="archive"))
        hidden_check = ""
    if not wait:
        documents = documents.filter(~Q(status="wait"))
        wait_check = ""
    if not selfsign:
        documents = documents.filter(~Q(status="autosign"))
        selfsign_check = ""
    if not ok:
        documents = documents.filter(~Q(status="ok"))
        ok_check = ""
    if not signdoc:
        signdoc_check = ""

    # filter date range
    documents = documents.filter(compilation_date__range=[newer, older])

    # filter types, owner, groups using chips
    if len(types) > 0:
        if types[0] != "":
            q_obj = Q()
            for t in types:
                q_obj |= Q(document_type__name=t)
                chips_types.append(t)

            documents = documents.filter(q_obj)

    if len(owner) > 0:
        if owner[0] != "":
            q_obj = Q()
            for u in owner:
                user = u.split("(")[0][:-1]
                q_obj |= Q(user__username=user)
                chips_owner.append(u)

            documents = documents.filter(q_obj)

    if len(groups) > 0:
        if groups[0] != "":
            q_obj = Q()
            for g in groups:
                q_obj |= Q(group__name=g)
                chips_groups.append(g)

            documents = documents.filter(q_obj)

    out = []
    for i in documents:
        # filter for confirmed with attachment documents and approved
        if signdoc:
            if i.status == "ok" and not i.signed_doc:
                continue

        # prepare images in base64
        personal = None
        medical = None
        vac_file = ""
        health_file = ""
        sign_doc_file = ""
        if i.personal_data:
            personal = i.personal_data
        if i.medical_data:
            medical = i.medical_data
            if medical.vac_certificate.name:
                with open(medical.vac_certificate.name, 'rb') as image_file:
                    vac_file = base64.b64encode(image_file.read()).decode()

            if medical.health_care_certificate.name:
                with open(medical.health_care_certificate.name, 'rb') as image_file:
                    health_file = base64.b64encode(image_file.read()).decode()

        if i.signed_doc:
            with open(i.signed_doc.name, 'rb') as image_file:
                sign_doc_file = base64.b64encode(
                    image_file.read()).decode()

        doc_group = i.user.groups.values_list('name', flat=True)[0]

        out.append([i, KeyVal.objects.filter(container=i), personal,
                    medical, doc_group, vac_file, health_file, sign_doc_file])

    # get types and users for chips autocompletation
    auto_types = DocumentType.objects.filter(
        Q(group_private=False) | Q(group=group))
    users = User.objects.filter(groups__name=parent_group)

    context = {
        "types": auto_types,
        "users": users,
        "groups": parent_groups,
        "docs": out,
        "hidden_check": hidden_check,
        "wait_check": wait_check,
        "selfsign_check": selfsign_check,
        "ok_check": ok_check,
        "signdoc_check": signdoc_check,
        "newer": newer,
        "older": older,
        "chips_owner": chips_owner,
        "chips_type": chips_types,
        "chips_groups": chips_groups,
        'error': error,
        'error_text': error_text,
        'settings': settings,
    }
    return render(request, 'server/doc_list.html', context)


@user_passes_test(isStaff)
def upload_doc(request):
    # setup group based on staff primary or not
    parent_group = request.user.groups.values_list('name', flat=True)[
        0]
    group = Group.objects.get(name=parent_group)
    if request.user.is_staff:
        groups = request.user.groups.values_list('name', flat=True)
    else:
        groups = request.user.groups.values_list('name', flat=True)[1:]

    # setup variables for error text and success text
    error = False
    success = False
    error_text = ""
    success_text = ""

    document = None
    # parse document code and check for permissions
    if request.method == "POST":
        data = request.POST["code"]
        if not data.isdigit():
            error_text = "Formato codice errato"
            error = True
        elif int(data) < 100000 or int(data) > 999999:
            error_text = "Formato codice errato"
            error = True
        elif len(Document.objects.filter(code=data)) == 0:
            error_text = "Codice invalido"
            error = True
        elif Document.objects.filter(code=data)[0].group.name not in groups:
            error_text = "Codice invalido"
            error = True
        else:
            # get document
            document = Document.objects.filter(code=data)[0]

            # prepare success message
            if document.status == 'ok':
                success_text = "File caricato"
                success = True
            else:
                document.status = 'ok'
                document.save()
                success_text = "Documento approvato e file caricato"
                success = True

            # check for errors and upload files
            if "doc_sign" in request.FILES and not error:
                myfile = request.FILES['doc_sign']
                try:
                    im = Image.open(myfile)
                    im_io = BytesIO()
                    # compress image in WEBP
                    im.save(im_io, 'WEBP', quality=50)
                    document.signed_doc.save(data+"_"+myfile.name, im_io)
                    document.save()
                except UnidentifiedImageError:
                    error = True
                    error_text = "Il file non è un immagine valida"
            else:
                error = True
                error_text = "Prego caricare un file"

    context = {
        "error": error,
        "error_text": error_text,
        "success": success,
        "success_text": success_text,
    }

    return render(request, 'server/upload_doc.html', context)


@user_passes_test(isStaff)
def docpreview(request):
    context = {}
    # check for permissions
    if request.user.is_staff:
        groups = request.user.groups.values_list('name', flat=True)
    else:
        groups = request.user.groups.values_list('name', flat=True)[1:]

    if request.method == "POST":
        # get document code
        code = request.POST["preview"]

        # check if code valid and user has permission
        if not code.isdigit():
            return render(request, 'server/download_doc.html', context)
        if len(Document.objects.filter(code=code)) == 0:
            return render(request, 'server/download_doc.html', context)
        if Document.objects.filter(code=code)[0].group.name not in groups:
            return render(request, 'server/download_doc.html', context)

        # get document
        document = Document.objects.filter(code=code)[0]
        parent_group = document.user.groups.values_list('name', flat=True)[0]

        # prepare images in base64
        vac_file = ""
        health_file = ""
        sign_doc_file = ""
        if document.medical_data:
            if document.medical_data.vac_certificate.name:
                with open(document.medical_data.vac_certificate.name, 'rb') as image_file:
                    vac_file = base64.b64encode(image_file.read()).decode()

            if document.medical_data.health_care_certificate.name:
                with open(document.medical_data.health_care_certificate.name, 'rb') as image_file:
                    health_file = base64.b64encode(image_file.read()).decode()
        if document.signed_doc:
            with open(document.signed_doc.name, 'rb') as image_file:
                sign_doc_file = base64.b64encode(image_file.read()).decode()

        # prepare context
        doc = [document, KeyVal.objects.filter(
            container=document), document.personal_data, document.medical_data, parent_group]
        context = {'doc': doc, 'vac': vac_file,
                   'health': health_file, 'sign_doc_file': sign_doc_file}

    return render(request, 'server/download_doc.html', context)
