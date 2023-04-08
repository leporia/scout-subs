import re
from django.shortcuts import render
from client.models import UserCode, Keys, DocumentType, Document, KeyVal
from django.conf import settings
from django.core.mail import send_mail
from client.models import GroupSettings, UserCode, Keys, DocumentType, Document, KeyVal
from django.contrib.auth.models import Group, Permission, User
from django.db.models import Q
from django.http import HttpResponseRedirect, FileResponse, HttpResponse
from django.db.models.deletion import ProtectedError
from django.template.loader import get_template
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.sessions.backends.db import SessionStore

import csv
import dateparser
from datetime import datetime
from datetime import timedelta
import pytz
import pdfkit
from io import BytesIO
import base64
from PIL import Image, UnidentifiedImageError
import zipfile
import json
import threading

# custom staff check function for non primary group staff members
def isStaff(user):
    if user.is_staff:
        return True
    if user.has_perm("client.staff"):
        return True
    return False

# function to check if "aggiunto" has permission to view documents
def isCapi_enabled(user):
    groups = user.groups.values_list('name', flat=True)
    group = groups[0]
    settings = GroupSettings.objects.filter(group__name=group)
    if len(settings) != 0 and "capi" in groups:
        return settings[0].view_documents
    else:
        return False

# function to get group list based on permissions of user
def getGroups(request):
    user = request.user
    if user.is_staff:
        groups = list(user.groups.all())
    else:
        groups = list(user.groups.all())[1:]

    if user.is_superuser and request.session.get("superuser"):
        groups = list(Group.objects.all())
        if "superuser_group" in request.session:
            su_group = Group.objects.get(name=request.session["superuser_group"])
            if su_group in groups:
                groups.remove(su_group)
            groups = [su_group] + groups

    return groups

@user_passes_test(isStaff)
def index(request):
    context = {}

    groups = getGroups(request)

    q_obj = Q(group__in=groups)

    doc_types = DocumentType.objects.filter(q_obj & Q(enabled=True)).order_by("-id")

    # check for settings
    group_check = []
    for i in groups:
        if i.name == "capi":
            continue

        doc_view_check = ""
        settings = GroupSettings.objects.filter(group=i)

        # create settings if non existing
        if len(settings) == 0:
            settings = GroupSettings(group=i, view_documents=False)
        else:
            settings = settings[0]

        if settings.view_documents:
            doc_view_check = 'checked="checked"'
        
        group_check.append([i.name, doc_view_check])

    # check if changing settings
    if request.method == "POST" and request.user.is_staff:
        if request.user.is_superuser and "su_status" in request.POST:
            action = request.POST["su_status"]
            if action == "change":
                if "superuser" not in request.session:
                    request.session["superuser"] = True
                else:
                    request.session["superuser"] = not request.session["superuser"]

                if "superuser_group" not in request.session:
                    request.session["superuser_group"] = "reparto"
            elif action in ["diga", "muta", "reparto", "posto", "clan"]:
                request.session["superuser_group"] = action

            return HttpResponseRedirect("/server")

        for i in groups:
            settings = GroupSettings.objects.filter(group=i)

            # create settings if non existing
            if len(settings) == 0:
                settings = GroupSettings(group=i, view_documents=False)
            else:
                settings = settings[0]

            if i.name in request.POST:
                settings.view_documents = True
                settings.save()
            else:
                settings.view_documents = False
                settings.save()

        return HttpResponseRedirect("/server")

    context = {
        'docs': doc_types,
        'groups': group_check,
        'doc_view_check': doc_view_check,
    }

    return render(request, 'server/index.html', context)


@staff_member_required
def uapprove(request):
    context = {}
    data = []
    if request.method == "POST":
        # get group name and obj
        group = getGroups(request)[0]
        parent_group = group.name

        # get permission object
        permission = Permission.objects.get(codename='approved')

        # parse text to array
        data = request.POST["codes"]
        data = split_codes(data)
        # check if format is right
        for i in range(len(data)):
            if not data[i].startswith("U"):
                data[i] = data[i] + " - Formato errato"
            elif not data[i][1:].isdigit():
                data[i] = data[i] + " - Formato errato"
            elif int(data[i][1:]) < 100000 or int(data[i][1:]) > 999999:
                data[i] = data[i] + " - Formato errato"
            elif UserCode.objects.filter(code=data[i][1:]).count() == 0:
                data[i] = data[i] + " - Invalido"
            else:
                user = UserCode.objects.filter(code=data[i][1:])[0].user
                user.user_permissions.add(permission)
                # if user not in any group add to the same group as staff
                if user.groups.values_list('name', flat=True).count() == 0:
                    user.groups.add(group)
                    data[i] = data[i] + " - Ok"
                else:
                    if user.groups.values_list('name', flat=True)[0] == parent_group:
                        # if user already in group do nothing
                        data[i] = data[i] + " - Già approvato"
                    else:
                        # if user in another group notify staff of group change
                        user.groups.remove(Group.objects.get(name=user.groups.values_list('name', flat=True)[0]))
                        user.groups.add(group)
                        data[i] = data[i] + " - Ok, cambio branca"

    context = {
        'messages': data,
        'empty': len(data) == 0,
    }

    return render(request, 'server/approve_user.html', context)

def split_codes(str):
    out = []
    buffer = ""
    for i in str:
        if i.isdigit() or i == "U":
            buffer += i
            continue
        
        if i == "\n":
            out.append(buffer)
            buffer = ""

    if buffer != "":
        out.append(buffer)

    return out

@user_passes_test(isStaff)
def docapprove(request):
    context = {}
    data = []

    groups = getGroups(request)

    # setup variables for error text and success text
    error = False
    success = False
    error_text = ""
    success_text = ""

    document = None
    messages = []

    if request.method == "POST":
        # check if bulk approve or single
        if "codes" in request.POST:
            # parse text in array
            data = request.POST["codes"]
            data = split_codes(data)
            # check if code valid
            for i in range(len(data)):
                if not data[i].isdigit():
                    messages.append(data[i] + " - Formato errato")
                elif int(data[i]) < 100000 or int(data[i]) > 999999:
                    messages.append(data[i] + " - Formato errato")
                elif Document.objects.filter(code=data[i]).count() == 0:
                    messages.append(data[i] + " - Invalido")
                elif Document.objects.filter(code=data[i])[0].group not in groups:
                    # check if user has permission to approve document
                    messages.append(data[i] + " - Invalido")
                else:
                    document = Document.objects.filter(code=data[i])[0]

                    if document.group not in groups:
                        return

                    if document.status != 'wait' and document.status != 'ok':
                        return

                    if document.status == 'ok':
                        # do nothing document already approved
                        messages.append(data[i] + " - Già approvato")
                    else:
                        document.status = 'ok'
                        document.save()
                        messages.append(data[i] + " - Ok")

        elif "code" in request.POST:
            print("doing this")
            data = request.POST["code"]
            if not data.isdigit():
                error_text = "Formato codice errato"
                error = True
            elif int(data) < 100000 or int(data) > 999999:
                error_text = "Formato codice errato"
                error = True
            elif Document.objects.filter(code=data).count() == 0:
                error_text = "Codice invalido"
                error = True
            elif Document.objects.filter(code=data)[0].group not in groups:
                error_text = "Codice invalido"
                error = True
            else:
                # get document
                document = Document.objects.filter(code=data)[0]

                if document.group not in groups:
                    return

                if document.status != 'wait' and document.status != 'ok':
                    return

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
        'messages': messages,
        'empty': len(messages) == 0,
        "error": error,
        "error_text": error_text,
        "success": success,
        "success_text": success_text,
    }

    return render(request, 'server/approve_doc.html', context)

@staff_member_required
def approve_direct(request):
    # get groups that the user is manager of
    groups = getGroups(request)

    if request.method == "POST" and "doc_code" in request.POST:
        # if user submitted the form to approve a document
        doc_code = request.POST["doc_code"]
        if doc_code.isdigit():
            doc_code = int(doc_code)
        else:
            doc_code = -1

        document = Document.objects.filter(code=doc_code)

        # user modified manually the code
        if len(document) != 1:
            return

        document = document[0]

        # user modified the code to an invalid document
        if document.status != "wait":
            return

        # check if user has permission to approve document
        if document.group not in groups:
            return

        document.status = "ok"
        document.save()
        return render(request, 'server/approve_doc_direct.html', {"doc": document, "success": True})

    # if the user just opened the page
    if "code" in request.GET:
        doc_code = request.GET["code"]
        if doc_code.isdigit():
            doc_code = int(doc_code)
        else:
            doc_code = -1
    else:
        return render(request, 'server/approve_doc_direct.html', {"error": -1})

    document = Document.objects.filter(code=doc_code)

    if len(document) != 1:
        return render(request, 'server/approve_doc_direct.html', {"error": "Codice del documento invalido, riscansionare il codice"})

    document = document[0]

    if document.status != "wait":
        return render(request, 'server/approve_doc_direct.html', {"error": "Questo documento non è in attesa di approvazione"})

    # check if user has permission to approve document
    if document.group not in groups:
        return render(request, 'server/approve_doc_direct.html', {"error": "Non hai il permesso di approvare questo documento"})

    return render(request, 'server/approve_doc_direct.html', {"doc": document})

@staff_member_required
def ulist(request):
    context = {}
    # group name and obj
    group = getGroups(request)[0]

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
                    container=document), document.personal_data, document.medical_data, document.user.groups.values_list('name', flat=True)[0]]
                context = {'doc': doc, 'vac': vac_file,
                           'health': health_file, 'sign_doc_file': sign_doc_file}
                # render context
                html = template.render(context)
                # render pdf using wkhtmltopdf
                pdf = pdfkit.from_string(html, False)
                result = BytesIO(pdf)
                result.seek(0)
                return FileResponse(result, filename=document.user.username+"_"+document.document_type.name+".pdf")

        # deapprove user
        elif request.POST["action"][0] == 'd':
            user = User.objects.get(id=request.POST["action"][1:])
            # check if user has permission to deapprove user
            if user.groups.all()[0] == group:
                permission = Permission.objects.get(codename="approved")
                user.user_permissions.remove(permission)
                return HttpResponseRedirect("ulist")
        # make user "capo"
        elif request.POST["action"][0] == 'c':
            user = User.objects.get(id=request.POST["action"][1:])
            capi = Group.objects.get(name="capi")
            # check if user has permission to modify
            if user.groups.all()[0] == group:
                if "capi" in user.groups.values_list('name', flat=True):
                    # remove group
                    user.groups.remove(capi)
                else:
                    # add group
                    user.groups.add(capi)
            return HttpResponseRedirect("ulist")

    # list users with their documents
    permission = Permission.objects.get(codename="approved")

    usercodes = UserCode.objects.filter(Q(user__user_permissions=permission) | Q(user__is_staff=True)).filter(user__groups__name__contains=group.name).select_related("user", "medic").order_by("user__last_name")

    vac_file = ["/server/media/", "/vac_certificate/usercode"]
    health_file = ["/server/media/", "/health_care_certificate/usercode"]

    context = {
        'users': usercodes,
        'vac_file': vac_file,
        'health_file': health_file,
    }
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

    # if user not staff of primary get only non primary groups
    groups = getGroups(request)

    if request.method == "POST":
        # check if request to edit
        if request.POST["action"][0] == 'e':
            document_type = DocumentType.objects.get(id=request.POST["action"][1:])

            # check if user has permission on the document
            if document_type.group not in groups:
                return

            enabled_check = 'checked="checked"' if document_type.enabled else ""
            sign_check = 'checked="checked"' if not document_type.auto_sign else ""
            custom_message_check = 'checked="checked"' if document_type.custom_message else ""
            staff_only_check = 'checked="checked"' if document_type.staff_only else ""
            private_check = 'checked="checked"' if document_type.group_private else ""

            context = {
                'doc': document_type,
                "group": document_type.group.name,
                "enabled_check": enabled_check,
                "private_check": private_check,
                "sign_check": sign_check,
                "staff_only_check": staff_only_check,
                "custom_message_check": custom_message_check,
            }

            return docedit_wrapper(request, context)

        # check if request to download
        elif request.POST["action"][0] == 'p':
            document_type = DocumentType.objects.get(id=request.POST["action"][1:])

            # check if user has permission on the document
            if document_type.group not in groups:
                return

            docs = Document.objects.filter(document_type=document_type).select_related("personal_data", "medical_data", "user")
            
            # get time for filename
            current_time = datetime.strftime(datetime.now(), "%H_%M__%d_%m_%y")

            response = HttpResponse()
            response['Content-Disposition'] = 'attachment; filename="' + document_type.name.replace(' ', '_') + '_export_' + current_time + '.csv"'

            writer = csv.writer(response)

            # csv header
            header = ["Nome", "Cognome", "Email", "Branca", "Capo", "Stato", "Data di compilazione"]
            if document_type.personal_data:
                header += ["Nome dei genitori", "Via", "CAP", "Comune", "Nazionalita", "Data di nascita", "Telefono di casa", "Telefono", "Scuola", "Anno scolastico", "Numero AVS"]

            keys = []
            if document_type.custom_data:
                keys = Keys.objects.filter(container=document_type).values_list("key", flat=True)
                header += keys

            writer.writerow(header)

            for doc in docs:
                capo = "no"
                if "capi" in doc.user.groups.values_list('name', flat=True) or doc.user.is_staff:
                    capo = "si"

                write_data = [
                    doc.user.first_name,
                    doc.user.last_name,
                    doc.user.email,
                    doc.user.groups.values_list('name', flat=True)[0],
                    capo,
                    doc.status,
                    doc.compilation_date,
                ]
                if document_type.personal_data:
                    write_data += [
                        doc.personal_data.parent_name,
                        doc.personal_data.via,
                        doc.personal_data.cap,
                        doc.personal_data.country,
                        doc.personal_data.nationality,
                        doc.personal_data.born_date,
                        doc.personal_data.home_phone,
                        doc.personal_data.phone,
                        doc.personal_data.school,
                        doc.personal_data.year,
                        doc.personal_data.avs_number
                    ]

                if document_type.custom_data:
                    # add empty cell if no keyval present
                    keyvals = KeyVal.objects.filter(container=doc).values_list("key", "value")
                    for key in keys:
                        for keyval in keyvals:
                            if keyval[0] == key:
                                write_data.append(keyval[1])
                                break
                        else:
                            write_data.append("")

                writer.writerow(write_data)

            return response

        #check if request to download with medic data
        elif request.POST["action"][0] == 'm':
            document_type = DocumentType.objects.get(id=request.POST["action"][1:])

            # check if user has permission on the document
            if document_type.group not in groups:
                return

            docs = Document.objects.filter(document_type=document_type)
            
            # get time for filename
            current_time = datetime.strftime(datetime.now(), "%H_%M__%d_%m_%y")

            response = HttpResponse()
            response['Content-Disposition'] = 'attachment; filename="' + document_type.name.replace(' ', '_') + '_export_medic_' + current_time + '.csv"'

            writer = csv.writer(response)

            # csv header
            header = ["Nome", "Cognome", "Email", "Branca", "Capo", "Stato", "Data di compilazione", "Nome dei genitori", "Via", "CAP", "Comune", "Nazionalita", "Data di nascita", "Telefono di casa", "Telefono", "Scuola", "Anno scolastico", "Numero AVS", "Contatto d'emergenza", "Parentela del contatto", "Telefono d'emergenza", "Cellulare emergenza", "Indirizzo completo emergenza", "Cassa malati", "Ass. Infortuni", "Ass. RC", "Socio REGA", "Nome del medico", "Telefono medico", "Indirizzo medico", "Malattie", "Vacinazioni", "Data antitetanica", "Allergie", "Assume medicamenti", "Medicamenti", "Informazioni particolari", "Informazioni"]

            if document_type.custom_data:
                header += Keys.objects.filter(container=document_type).values_list("key", flat=True)

            writer.writerow(header)

            for doc in docs:
                capo = "no"
                if "capi" in doc.user.groups.values_list('name', flat=True) or doc.user.is_staff:
                    capo = "si"

                write_data = [
                        doc.user.first_name,
                        doc.user.last_name,
                        doc.user.email,
                        doc.user.groups.values_list('name', flat=True)[0],
                        capo,
                        doc.status,
                        doc.compilation_date,
                        doc.personal_data.parent_name,
                        doc.personal_data.via,
                        doc.personal_data.cap,
                        doc.personal_data.country,
                        doc.personal_data.nationality,
                        doc.personal_data.born_date,
                        doc.personal_data.home_phone,
                        doc.personal_data.phone,
                        doc.personal_data.school,
                        doc.personal_data.year,
                        doc.personal_data.avs_number
                ]
                if doc.medical_data:
                    write_data += [
                        doc.medical_data.emer_name,
                        doc.medical_data.emer_relative,
                        doc.medical_data.emer_phone,
                        doc.medical_data.cell_phone,
                        doc.medical_data.address,
                        doc.medical_data.health_care,
                        doc.medical_data.injuries,
                        doc.medical_data.rc,
                        doc.medical_data.rega,
                        doc.medical_data.medic_name,
                        doc.medical_data.medic_phone,
                        doc.medical_data.medic_address,
                        doc.medical_data.sickness,
                        doc.medical_data.vaccine,
                        doc.medical_data.tetanus_date,
                        doc.medical_data.allergy,
                        doc.medical_data.drugs_bool,
                        doc.medical_data.drugs,
                        doc.medical_data.misc_bool,
                        doc.medical_data.misc
                    ]

                if document_type.custom_data:
                    write_data += KeyVal.objects.filter(container=doc).values_list("value", flat=True)

                writer.writerow(write_data)

            return response

        # list all selected types
        for i in request.POST.keys():
            if i.isdigit():
                docc = DocumentType.objects.get(id=i)
                # check if user has permission
                if docc.group in groups:
                    # execute action
                    if request.POST["action"] == 'delete':
                        try:
                            docc.delete()
                        except ProtectedError:
                            error = True
                            error_text = "Non puoi eliminare un tipo a cui é collegato uno o piú documenti"
                    elif request.POST["action"] == 'hide':
                        docc.enabled = False
                        docc.save()
                    elif request.POST["action"] == 'show':
                        docc.enabled = True
                        docc.save()
                else:
                    error = True
                    error_text = "Non puoi modificare un documento non del tuo gruppo"

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

    # get documents from the list
    q_obj = Q(group__in=groups)

    public_types = DocumentType.objects.filter(q_obj)

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

    context = {
        'docs': public_types,
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
def custom_parameters_preview(request):
    context = {}
    if "param" not in request.GET:
        return render(request, 'server/doc_creation_preview.html', context)

    params = request.GET["param"]
    params = base64.b64decode(params).decode("utf-8")
    params = params.splitlines()
    keys = []
    for i in range(len(params)):
        dic = {}
        val = params[i]
        if val.startswith("!"):
            if len(val) >= 3:
                val = val[3:].split(",")[0]

        dic["key"] = val
        dic["key_extra"] = params[i]
        dic["id"] = i
        keys.append(dic)

    context["keys"] = keys
    return render(request, 'server/doc_creation_preview.html', context)

@user_passes_test(isStaff)
def doccreate(request):
    context = {}

    groups = getGroups(request)
    # if user is not staff of primary set default group to secondary and default public type
    if request.user.is_staff:
        group_private = False
        private_check = 'checked="checked"'
    else:
        group_private = True
        private_check = ''

    # get group obj
    group = groups[0]

    # init checkboxes
    enabled = False
    personal_data = False
    medical_data = False
    custom_data = False
    custom_group_bool = False
    staff_only = False
    name = ""
    custom_group = ""
    max_instances = 0

    enabled_check = 'checked="checked"'
    personal_check = 'checked="checked"'
    sign_check = 'checked="checked"'
    medical_check = ""
    custom_check = ""
    custom_message_check = ""
    staff_only_check = ""

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
        staff_only = "staff_only" in request.POST.keys()
        custom_message_text = request.POST["custom_message_text"]

        # parse name with icons
        name = request.POST["name"]
        if "<" in name:
            context["error"] = "true"
            context["error_text"] = "Il nome non puo' contenere il carattere <"
            return render(request, 'server/doc_create.html', context)

        reg = r'\{[\s\S]*\}'
        name_split = re.split(reg, name)
        name_matches = re.findall(reg, name)
        name_matches = list(map(lambda x: "<i class='material-icons'>" + x[1:len(x)-1] + "</i>", name_matches)) + [""]
        name_arr = [val for pair in zip(name_split, name_matches) for val in pair]
        name = "".join(name_arr)

        custom_group = request.POST["custom_group"]

        if request.POST["max_instances"]:
            max_instances = request.POST["max_instances"]
            if not max_instances.isdigit():
                context["error"] = "true"
                context["error_text"] = "Il numero massimo di iscritti deve essere un numero"
                return render(request, 'server/doc_create.html', context)
            max_instances = int(max_instances)

        # if group not primary and not public throw error
        if group_private == True and not request.user.is_staff:
            context["error"] = "true"
            context["error_text"] = "Non puoi creare un documento non pubblico per un gruppo non primario"
            return render(request, 'server/doc_create.html', context)

        # if already existing name throw error
        if DocumentType.objects.filter(name=name).count() > 0:
            context["error"] = "true"
            context["error_text"] = "Questo nome esiste già. Prego usarne un altro."
            return render(request, 'server/doc_create.html', context)

        # check if custom group permissions not met or non public document
        if custom_group != "":
            if group_private == True:
                context["error"] = "true"
                context["error_text"] = "Non puoi creare un documento non pubblico per un gruppo non primario"
                return render(request, 'server/doc_create.html', context)
            if custom_group not in map(lambda x: x.name, groups):
                context["error"] = "true"
                context["error_text"] = "Non puoi creare un tipo assegnato ad un gruppo di cui non fai parte"
                return render(request, 'server/doc_create.html', context)
            else:
                group = Group.objects.filter(name=custom_group)[0]
                custom_group_bool = True

        # create type
        doctype = DocumentType(
            custom_group=custom_group_bool, auto_sign=auto_sign, custom_message=custom_message, custom_message_text=custom_message_text, name=name, enabled=enabled, group_private=group_private, group=group, personal_data=personal_data, medical_data=medical_data, custom_data=custom_data, staff_only=staff_only, max_instances=max_instances)
        doctype.save()

        # create custom keys
        if custom_data:
            custom = request.POST["custom"]
            custom = custom.splitlines()
            for i in custom:
                val = i
                if val.startswith("!"):
                    if len(val) >= 3:
                        val = val[3:].split(",")[0]

                key = Keys(key=val, key_extra=i, container=doctype)
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
        "staff_only_check": staff_only_check,
        "custom_message_check": custom_message_check,
    }

    return render(request, 'server/doc_create.html', context)

@user_passes_test(isStaff)
def docedit(request):
    # create an edit page with empty context
    return docedit_wrapper(request, {})

@user_passes_test(isStaff)
def docedit_wrapper(request, context):
    groups = getGroups(request)
    group = groups[0]

    if request.user.is_staff and "group" in context.keys():
        if context["group"] == group.name:
            context["group"] = ""

    if request.method == "POST":
        if "action" not in request.POST.keys():
            # get document
            doc = DocumentType.objects.get(id=request.POST["doc"])

            # check if user can edit type
            if doc.group not in groups:
                # user is cheating abort
                return

            # init variables
            custom_group_bool = False
            custom_group = ""
            max_instances = 0

            enabled_check = 'checked="checked"' if doc.enabled else ""
            sign_check = 'checked="checked"' if not doc.auto_sign else ""
            custom_message_check = 'checked="checked"' if doc.custom_message else ""
            staff_only_check = 'checked="checked"' if doc.staff_only else ""
            private_check = 'checked="checked"' if doc.group_private else ""

            context = {
                'doc': doc,
                "group": doc.group.name,
                "enabled_check": enabled_check,
                "private_check": private_check,
                "sign_check": sign_check,
                "staff_only_check": staff_only_check,
                "custom_message_check": custom_message_check,
            }

            if request.user.is_staff:
                if context["group"] == group.name:
                    context["group"] = ""

            # gather inserted data
            enabled = "enabled" in request.POST.keys()
            auto_sign = "sign" not in request.POST.keys()
            group_private = "group_private" in request.POST.keys()
            custom_message = "custom_message" in request.POST.keys()
            staff_only = "staff_only" in request.POST.keys()
            custom_message_text = request.POST["custom_message_text"]
            custom_group = request.POST["custom_group"]

            if request.POST["max_instances"]:
                max_instances = request.POST["max_instances"]
                if not max_instances.isdigit():
                    context["error"] = "true"
                    context["error_text"] = "Il numero massimo di iscritti deve essere un numero"
                    return render(request, 'server/doc_edit.html', context)
                max_instances = int(max_instances)

            # if group not primary and not public throw error
            if group_private == True and not request.user.is_staff:
                context["error"] = "true"
                context["error_text"] = "Non puoi creare un documento non pubblico per un gruppo non primario"
                return render(request, 'server/doc_edit.html', context)

            # check if custom group permissions not met or non public document
            if custom_group != "":
                if group_private == True:
                    context["error"] = "true"
                    context["error_text"] = "Non puoi creare un documento non pubblico per un gruppo non primario"
                    return render(request, 'server/doc_edit.html', context)
                if custom_group not in map(lambda x: x.name, groups):
                    context["error"] = "true"
                    context["error_text"] = "Non puoi creare un tipo assegnato ad un gruppo di cui non fai parte"
                    return render(request, 'server/doc_edit.html', context)
                else:
                    group = Group.objects.filter(name=custom_group)[0]
                    custom_group_bool = True

            # edit type
            doc.custom_group = custom_group_bool
            doc.auto_sign = auto_sign
            doc.custom_message = custom_message
            doc.custom_message_text = custom_message_text
            doc.enabled = enabled
            doc.group_private = group_private
            doc.group = group
            doc.staff_only = staff_only
            doc.max_instances = max_instances

            doc.save()

            return HttpResponseRedirect('doctype')

    return render(request, 'server/doc_edit.html', context)

@user_passes_test(isStaff)
def doclist(request):
    context = {}

    # group name and obj
    parent_groups = getGroups(request)

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
            if document.group in parent_groups:
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
                    container=document), document.personal_data, document.medical_data, document.user.groups.values_list('name', flat=True)[0]]
                context = {'doc': doc, 'vac': vac_file,
                           'health': health_file, 'sign_doc_file': sign_doc_file}
                html = template.render(context)
                pdf = pdfkit.from_string(html, False)
                result = BytesIO(pdf)
                result.seek(0)
                return FileResponse(result, as_attachment=True, filename=document.user.username+"_"+document.document_type.name+".pdf")

        # get selected documents and check if user has permission to view
        selected = []
        for i in request.POST.keys():
            if i.isdigit():
                docc = Document.objects.get(id=i)
                if docc.group in parent_groups:
                    selected.append(docc)

                    # execute action on selected documents
                    if request.POST["action"] == 'delete' and settings.DEBUG:
                        docc.delete()
                    elif request.POST["action"] == 'approve' and settings.DEBUG:
                        docc.status = 'ok'
                        docc.save()
                    elif request.POST["action"] == 'archive':
                        docc.status = 'archive'
                        if docc.medical_data:
                            docc.medical_data.delete()
                            docc.medical_data.save()
                            docc.medical_data = None
                        docc.save()
                    #elif request.POST["action"] == 'unarchive':
                    #    if docc.status == 'archive':
                    #        docc.status = 'ok'
                    #        docc.save()
                    #    else:
                    #        error = True
                    #        error_text = "Non puoi dearchiviare un documento non archiviato"

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

    # filter documents based on group of staff and date range
    q_obj = Q(group__in=parent_groups) & Q(compilation_date__range=[newer, older])

    # filter documents
    if not hidden:
        q_obj &= ~Q(status="archive")
        hidden_check = ""
    if not wait:
        q_obj &= ~Q(status="wait")
        wait_check = ""
    if not selfsign:
        q_obj &= ~Q(status="autosign")
        selfsign_check = ""
    if not ok:
        q_obj &= ~Q(status="ok")
        ok_check = ""
    if signdoc:
        q_obj &= ~Q(signed_doc="")
    else:
        signdoc_check = ""

    # filter types, owner, groups using chips
    if len(types) > 0:
        if types[0] != "":
            q_obj &= Q(document_type__name__in=types)
            chips_types += types

    if len(owner) > 0:
        if owner[0] != "":
            q_obj &= Q(user__username__in=list(map(lambda x: x.split("(")[0][:-1], owner)))
            chips_owner += owner

    if len(groups) > 0:
        if groups[0] != "":
            q_obj &= Q(user__groups__name__in=groups)
            chips_groups += groups

    # run query
    documents = Document.objects.filter(q_obj).select_related("personal_data", "medical_data", "document_type", "user")

    users = documents.values("user__username", "user__first_name", "user__last_name")

    vac_file = ["/server/media/", "/vac_certificate/doc"]
    health_file = ["/server/media/", "/health_care_certificate/doc"]
    sign_doc_file = ["/server/media/", "/signed_doc/doc"]

    # get types and users for chips autocompletation
    if request.user.is_staff:
        auto_types = DocumentType.objects.filter(
            Q(group_private=False) | Q(group=getGroups(request)[0]))
    else:
        auto_types = DocumentType.objects.filter(Q(group_private=False))

    context = {
        "vac_file": vac_file,
        "health_file": health_file,
        "sign_doc_file": sign_doc_file,
        "types": auto_types,
        "users": users,
        "groups": Group.objects.all(),
        "docs": documents,
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
        'total_count': documents.count,
        'diga_count': documents.filter(user__groups__name__contains="diga").count,
        'muta_count': documents.filter(user__groups__name__contains="muta").count,
        'reparto_count': documents.filter(user__groups__name__contains="reparto").count,
        'posto_count': documents.filter(user__groups__name__contains="posto").count,
        'clan_count': documents.filter(user__groups__name__contains="clan").count,
    }

    # check if download multiple documents
    if request.method == "POST":
        if "status" not in request.session:
            request.session['status'] = True

        if request.POST["action"] == "download" and len(selected) > 0 and request.session['status']:
            # save data in session
            request.session['status'] = False
            request.session['progress'] = 0
            request.session['total'] = len(selected)
            # run job
            threading.Thread(target=zip_documents, args=(selected, request.session.session_key)).start()
            # flag the client to check for updates
            context["task_id"] = "0"

    return render(request, 'server/doc_list.html', context)

@user_passes_test(isCapi_enabled)
def doclist_readonly(request):
    context = {}

    # group name and obj
    groups = request.user.groups.all()
    if request.user.is_staff:
        groups_view = []
    elif request.user.has_perm("client.staff"):
        groups_view = list(map(lambda x: x.group, GroupSettings.objects.filter(group=groups[0]).filter(view_documents=True)))
    else:
        groups_view = list(map(lambda x: x.group, GroupSettings.objects.filter(group__in=groups).filter(view_documents=True)))

    perm = Permission.objects.get(codename='staff')

    for i in groups_view:
        # get all users that are part of the group and are administrators but not request.user
        emails = User.objects.filter(groups__name=i).filter(Q(is_staff=True) | Q(user_permissions=perm)).filter(~Q(id=request.user.id)).values_list("email", flat=True)

        if not settings.DEBUG:
            send_mail(
                'Attenzione! ' + request.user.username + ' ha visionato i documenti del gruppo "' + i.name + '"',
                "Questo messaggio è stato inviato automaticamente dal sistema di iscrizioni digitali. Ti è arrivata questa mail perchè hai abilitato la possibilità a persone del gruppo capi di visionare i documenti. L'utente con username " + request.user.username + " e con nome registrato " + request.user.first_name + " " + request.user.last_name + " ha visionato dei documenti.",
                settings.DEFAULT_FROM_EMAIL,
                emails,
                fail_silently=False,
            )


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
            if document.group in groups_view:
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
                    container=document), document.personal_data, document.medical_data, document.user.groups.values_list('name', flat=True)[0]]
                context = {'doc': doc, 'vac': vac_file,
                           'health': health_file, 'sign_doc_file': sign_doc_file}
                html = template.render(context)
                pdf = pdfkit.from_string(html, False)
                result = BytesIO(pdf)
                result.seek(0)
                return FileResponse(result, as_attachment=True, filename=document.user.username+"_"+document.document_type.name+".pdf")

        # get selected documents and check if user has permission to view
        selected = []
        for i in request.POST.keys():
            if i.isdigit():
                docc = Document.objects.get(id=i)
                if docc.group in groups_view:
                    selected.append(docc)

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

    # filter documents based on group of staff and date range
    q_obj = Q(group__name__in=groups_view) & Q(compilation_date__range=[newer, older])

    # filter documents
    if not hidden:
        q_obj &= ~Q(status="archive")
        hidden_check = ""
    if not wait:
        q_obj &= ~Q(status="wait")
        wait_check = ""
    if not selfsign:
        q_obj &= ~Q(status="autosign")
        selfsign_check = ""
    if not ok:
        q_obj &= ~Q(status="ok")
        ok_check = ""
    if signdoc:
        q_obj &= ~Q(signed_doc="")
    else:
        signdoc_check = ""

    # filter types, owner, groups using chips
    if len(types) > 0:
        if types[0] != "":
            q_obj &= Q(document_type__name__in=types)
            chips_types += types

    if len(owner) > 0:
        if owner[0] != "":
            q_obj &= Q(user__username__in=list(map(lambda x: x.split("(")[0][:-1], owner)))
            chips_owner += owner

    if len(groups) > 0:
        if groups[0] != "":
            q_obj &= Q(user__groups__name__in=groups)
            chips_groups += groups

    # run query
    documents = Document.objects.filter(q_obj).select_related("personal_data", "medical_data", "document_type", "user")

    users = documents.values("user__username", "user__first_name", "user__last_name")

    vac_file = ["/server/media/", "/vac_certificate/doc"]
    health_file = ["/server/media/", "/health_care_certificate/doc"]
    sign_doc_file = ["/server/media/", "/signed_doc/doc"]

    # get types and users for chips autocompletation
    auto_types = DocumentType.objects.filter(
        Q(group_private=False) | Q(group__in=groups_view))

    context = {
        "vac_file": vac_file,
        "health_file": health_file,
        "sign_doc_file": sign_doc_file,
        "types": auto_types,
        "users": users,
        "groups": Group.objects.all(),
        "docs": documents,
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
        'total_count': documents.count,
        'diga_count': documents.filter(user__groups__name__contains="diga").count,
        'muta_count': documents.filter(user__groups__name__contains="muta").count,
        'reparto_count': documents.filter(user__groups__name__contains="reparto").count,
        'posto_count': documents.filter(user__groups__name__contains="posto").count,
        'clan_count': documents.filter(user__groups__name__contains="clan").count,
    }

    # check if download multiple documents
    if request.method == "POST":
        if "status" not in request.session:
            request.session['status'] = True

        if request.POST["action"] == "download" and len(selected) > 0 and request.session['status']:
            # save data in session
            request.session['status'] = False
            request.session['progress'] = 0
            request.session['total'] = len(selected)
            # run job
            threading.Thread(target=zip_documents, args=(selected, request.session.session_key)).start()
            # flag the client to check for updates
            context["task_id"] = "0"

    return render(request, 'server/doc_list_readonly.html', context)

def get_progress(request):
    # if user wants to download result
    if 'download' in request.GET:
        # if job is completed
        if request.session['status']:
            data = BytesIO(base64.b64decode(request.session['result']))
            data.seek(0)
            return FileResponse(data, as_attachment=True, filename="documents_" + datetime.now().strftime("%H_%M-%d_%m_%y") + ".zip")

    # otherwise return status
    data = [request.session['progress'], request.session['total'], request.session['status']]
    return HttpResponse(json.dumps(data))

def zip_documents(docs, session_key):
    files = []
    # get session
    session = SessionStore(session_key=session_key)
    for i in docs:
        vac_file = ""
        health_file = ""
        sign_doc_file = ""

        # prepare pictures in base64
        if i.medical_data:
            if i.medical_data.vac_certificate.name:
                with open(i.medical_data.vac_certificate.name, 'rb') as image_file:
                    vac_file = base64.b64encode(
                        image_file.read()).decode()

            if i.medical_data.health_care_certificate.name:
                with open(i.medical_data.health_care_certificate.name, 'rb') as image_file:
                    health_file = base64.b64encode(
                        image_file.read()).decode()
        if i.signed_doc:
            with open(i.signed_doc.name, 'rb') as image_file:
                sign_doc_file = base64.b64encode(
                    image_file.read()).decode()

        template = get_template('server/download_doc.html')
        doc = [i, KeyVal.objects.filter(
            container=i), i.personal_data, i.medical_data, i.user.groups.values_list('name', flat=True)[0]]
        context = {'doc': doc, 'vac': vac_file,
                    'health': health_file, 'sign_doc_file': sign_doc_file}
        # render context
        html = template.render(context)
        # render pdf using wkhtmltopdf
        pdf = pdfkit.from_string(html, False)
        filename = i.user.username+"_"+i.document_type.name+".pdf"
        # append file
        files.append((filename, pdf))
        session['progress'] += 1
        session.save()

    # zip documents
    mem_zip = BytesIO()
    with zipfile.ZipFile(mem_zip, mode="w",compression=zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.writestr(f[0], f[1])

    mem_zip.seek(0)
    # save result
    session['result'] = base64.b64encode(mem_zip.getvalue()).decode()
    session['status'] = True
    session.save()


@user_passes_test(isStaff)
def upload_doc(request):
    # setup group based on staff primary or not
    groups = getGroups(request)

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
        elif Document.objects.filter(code=data).count() == 0:
            error_text = "Codice invalido"
            error = True
        elif Document.objects.filter(code=data)[0].group not in groups:
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
    groups = getGroups(request)

    if request.method == "POST":
        # get document code
        code = request.POST["preview"]

        # check if code valid and user has permission
        if not code.isdigit():
            return render(request, 'server/download_doc.html', context)
        if Document.objects.filter(code=code).count() == 0:
            return render(request, 'server/download_doc.html', context)
        if Document.objects.filter(code=code)[0].group not in groups:
            return render(request, 'server/download_doc.html', context)

        # get document
        document = Document.objects.filter(code=code)[0]
        doc_group = document.group
        parent_group = document.user.groups.values_list('name', flat=True)[0]

        # user has not permission to view document
        if doc_group not in groups:
            return

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


@user_passes_test(isStaff)
def data_request(request):
    context = {}
    parent_group = getGroups(request)[0]

    if request.method == "POST":
        if "request" not in request.POST.keys():
            context["error"] = "Selezionare una richesta"
        elif request.POST["request"] == "email_all":
            perm = Permission.objects.get(codename="approved")
            users_email = User.objects.filter(groups=parent_group, user_permissions=perm).values_list("email", flat=True)
            data = ", ".join(users_email)
            context["data"] = data
        elif request.POST["request"] == "email_non_staff":
            perm = Permission.objects.get(codename="approved")
            users_email = User.objects.filter(groups=parent_group, user_permissions=perm).exclude(groups__name="capi").values_list("email", flat=True)
            data = ", ".join(users_email)
            context["data"] = data
        elif request.POST["request"] == "data_user":
            perm = Permission.objects.get(codename="approved")
            users = User.objects.filter(groups=parent_group, user_permissions=perm)

            # get time for filename
            current_time = datetime.strftime(datetime.now(), "%H_%M__%d_%m_%y")

            response = HttpResponse()
            response['Content-Disposition'] = 'attachment; filename="data_export_' + current_time + '.csv"'

            writer = csv.writer(response)

            # csv header
            writer.writerow(["Codice", "Nome", "Cognome", "Email", "Nome dei genitori", "Indirizzo", "NAP", "Luogo", "Nazionalita", "Nazionalità secondo G+S", "Data di nascita", "numero di telefono Altro", "numero di telefono Cellulare", "Scuola", "Classe scolastica", "Numero AVS"])

            for user in users:
                usercode = UserCode.objects.filter(user=user)[0]
                nationality = usercode.nationality

                nat_gs = ""
                if "svizzera" in nationality.lower():
                    nat_gs = "CH"
                elif "ch" == nationality.lower():
                    nat_gs = "CH"
                else:
                    nat_gs = "DIV"

                writer.writerow([
                    "U"+str(usercode.code),
                    user.first_name,
                    user.last_name,
                    user.email,
                    usercode.parent_name,
                    usercode.via,
                    usercode.cap,
                    usercode.country,
                    usercode.nationality,
                    nat_gs,
                    usercode.born_date,
                    usercode.home_phone,
                    usercode.phone,
                    usercode.school,
                    usercode.year,
                    usercode.avs_number
                ])

            return response

        elif request.POST["request"] == "data_user_medic":
            perm = Permission.objects.get(codename="approved")
            users = User.objects.filter(groups=parent_group, user_permissions=perm)

            # get time for filename
            current_time = datetime.strftime(datetime.now(), "%H_%M__%d_%m_%y")

            response = HttpResponse()
            response['Content-Disposition'] = 'attachment; filename="data_export_' + current_time + '.csv"'

            writer = csv.writer(response)

            # csv header
            writer.writerow(["Codice", "Nome", "Cognome", "Email", "Nome dei genitori", "Indirizzo", "NAP", "Luogo", "Nazionalita", "Nazionalità secondo G+S", "Data di nascita", "numero di telefono Altro", "numero di telefono Cellulare", "Scuola", "Classe scolastica", "Numero AVS", "Contatto d'emergenza", "Parentela del contatto", "Telefono d'emergenza", "Cellulare emergenza", "Indirizzo completo emergenza", "Cassa malati", "Ass. Infortuni", "Ass. RC", "Socio REGA", "Nome del medico", "Telefono medico", "Indirizzo medico", "Malattie", "Vacinazioni", "Data antitetanica", "Allergie", "Assume medicamenti", "Medicamenti", "Informazioni particolari", "Informazioni"])

            for user in users:
                usercode = UserCode.objects.filter(user=user)[0]
                medic = usercode.medic
                nationality = usercode.nationality

                nat_gs = ""
                if "svizzera" in nationality.lower():
                    nat_gs = "CH"
                elif "ch" == nationality.lower():
                    nat_gs = "CH"
                else:
                    nat_gs = "DIV"

                writer.writerow([
                    "U"+str(usercode.code),
                    user.first_name,
                    user.last_name,
                    user.email,
                    usercode.parent_name,
                    usercode.via,
                    usercode.cap,
                    usercode.country,
                    usercode.nationality,
                    nat_gs,
                    usercode.born_date,
                    usercode.home_phone,
                    usercode.phone,
                    usercode.school,
                    usercode.year,
                    usercode.avs_number,
                    medic.emer_name,
                    medic.emer_relative,
                    medic.emer_phone,
                    medic.cell_phone,
                    medic.address,
                    medic.health_care,
                    medic.injuries,
                    medic.rc,
                    medic.rega,
                    medic.medic_name,
                    medic.medic_phone,
                    medic.medic_address,
                    medic.sickness,
                    medic.vaccine,
                    medic.tetanus_date,
                    medic.allergy,
                    medic.drugs_bool,
                    medic.drugs,
                    medic.misc_bool,
                    medic.misc
                ])

            return response
    return render(request, 'server/data_request.html', context)

def media_request(request, id=0, t="", flag=""):
    if flag == "usercode":
        usercode = UserCode.objects.get(id=id)
        if request.user.is_staff:
            groups = getGroups(request)
            usercode_group = usercode.user.groups[0]
            if usercode_group not in groups:
                return
        else:
            if usercode.user != request.user:
                return

        if t == "health_care_certificate":
            image_file = usercode.medic.health_care_certificate
        elif t == "vac_certificate":
            image_file = usercode.medic.vac_certificate

    elif flag == "doc":
        doc = Document.objects.get(id=id)
        doc_group = doc.group

        groups = getGroups(request)
        group_view = Group.objects.filter(name="capi") in groups and GroupSettings.objects.filter(group__name=doc_group).filter(view_documents=True).count() != 0

        # check if user can view media
        if request.user.is_staff:
            # user is staff
            if doc_group not in groups:
                return
        elif request.user.has_perm("client.staff"):
            # user is psudo-staff
            if doc_group not in groups[1:] and not group_view:
                return
        else:
            # is normal user
            if doc.user != request.user and not group_view:
                return

        if t == "health_care_certificate":
            image_file = doc.medical_data.health_care_certificate
        elif t == "vac_certificate":
            image_file = doc.medical_data.vac_certificate
        elif t == "signed_doc":
            image_file = doc.signed_doc

    return FileResponse(image_file, filename=image_file.name)
