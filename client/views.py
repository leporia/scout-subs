from random import randint
from django.contrib.auth.models import Group, Permission, User
from client.models import UserCode, Keys, DocumentType, Document, PersonalData, KeyVal, MedicalData
from django.db.models import Q
from django.http import HttpResponseRedirect, FileResponse, HttpResponse
from django.contrib.auth.decorators import login_required

from django.shortcuts import render

from django.template.loader import get_template
from io import BytesIO
import pdfkit
import base64


def index(request):
    context = {}
    # check if user is logged
    if (request.user.is_authenticated):
        # generate code if user has no code
        users = UserCode.objects.filter(user=request.user)
        code = None
        if (len(users) == 0):
            while (True):
                code = randint(100000, 999999)
                if len(UserCode.objects.filter(code=code)) == 0:
                    break
            medic = MedicalData()
            medic.save()
            userCode = UserCode(user=request.user, code=code, medic=medic)
            userCode.save()

        # user action
        if request.method == "POST":
            # get document id
            document = Document.objects.get(id=request.POST["action"][1:])

            # check if document is valid to modify
            if document.user != request.user:
                return

            if document.status == "ok" or document.status == "archive":
                return

            # execute action
            if request.POST["action"][0] == 'f':
                # generate approve pdf
                template = get_template('client/approve_doc_pdf.html')
                context = {'doc': document}
                html = template.render(context)
                pdf = pdfkit.from_string(html, False)
                result = BytesIO(pdf)
                result.seek(0)
                return FileResponse(result, filename=document.document_type.name+".pdf")
            elif request.POST["action"][0] == 'a':
                # sign autosign doc
                if document.status == "autosign":
                    document.status = "ok"
                    document.save()
                    return HttpResponseRedirect("/")
            elif request.POST["action"][0] == 'd':
                # delete doc
                document.delete()
                return HttpResponseRedirect("/")
            elif request.POST["action"][0] == 'e':
                # edit doc generate context and render edit page
                document_type = document.document_type
                context = {
                    'doctype': document_type,
                }
                context['doc'] = document
                context['personal_data'] = document_type.personal_data
                context['medical_data'] = document_type.medical_data
                context['custom_data'] = document_type.custom_data
                keys = Keys.objects.filter(container=document_type)
                out_keys = []
                for i in keys:
                    out_keys.append([i, KeyVal.objects.filter(
                        Q(container=document) & Q(key=i.key))[0].value])
                context['keys'] = out_keys
                context['custom_message'] = document_type.custom_message
                context['custom_message_text'] = document_type.custom_message_text
                return edit_wrapper(request, context)

        # show only docs of the user and non archived
        documents = Document.objects.filter(
            Q(user=request.user) & ~Q(status='archive'))
        out = []
        for i in documents:
            # for every document prepare images in base64
            personal = None
            medical = None
            vac_file = ""
            health_file = ""
            if i.personal_data:
                personal = i.personal_data
            if i.medical_data:
                medical = i.medical_data

                if medical.vac_certificate.name:
                    with open(medical.vac_certificate.name, 'rb') as image_file:
                        vac_file = base64.b64encode(image_file.read()).decode()

                if medical.health_care_certificate.name:
                    with open(medical.health_care_certificate.name, 'rb') as image_file:
                        health_file = base64.b64encode(
                            image_file.read()).decode()

            doc_group = i.user.groups.values_list('name', flat=True)[0]

            out.append([i, KeyVal.objects.filter(container=i),
                        personal, medical, doc_group, vac_file, health_file])

        context = {
            "docs": out,
            "empty": len(out) == 0,
        }

    return render(request, 'client/index.html', context)


@login_required
def approve(request):
    context = {}
    # if user not approved and has enough data then give instructions how to approve user
    if not (request.user.is_staff or request.user.has_perm('approved')):
        usercode = UserCode.objects.filter(user=request.user)[0]
        okay = False
        if request.user.first_name != "" and request.user.last_name != "" and request.user.email != "" and usercode.phone != "":
            okay = True
        context = {'code': 'U' + str(usercode.code), 'okay': okay}
        return render(request, 'client/approve.html', context)
    else:
        return render(request, 'client/index.html', context)


@login_required
def create(request):
    context = {}
    # group name and obj
    parent_group = request.user.groups.values_list('name', flat=True)[
        0]
    group = Group.objects.get(name=parent_group)

    # get available types for user
    doctypes = DocumentType.objects.filter(
        (Q(group_private=False) | Q(group=group)) & Q(enabled=True))
    out = []
    for doc in doctypes:
        # check if user has already that document type
        if len(Document.objects.filter(Q(user=request.user) & Q(document_type=doc))) == 0:
            out.append(doc)

    context['docs'] = out
    if request.method == "POST":
        if request.POST["action"] == "details":
            # user has to select a document type
            if "doctype" not in request.POST.keys():
                # if no type selected throw error
                context['error'] = True
                context['error_text'] = "Seleziona un documento"
            else:
                # gather data to ask to the user
                context['next'] = True
                document_type = DocumentType.objects.get(
                    id=request.POST["doctype"])
                context['doctype'] = document_type
                context['personal_data'] = document_type.personal_data
                context['medical_data'] = document_type.medical_data
                context['custom_data'] = document_type.custom_data
                keys = Keys.objects.filter(container=document_type)
                out_keys = []
                for i in keys:
                    out_keys.append([i, ""])
                context['keys'] = out_keys
                context['custom_message'] = document_type.custom_message
                context['custom_message_text'] = document_type.custom_message_text
        elif request.POST["action"] == "save":
            # after type was selected it shows details to complete

            # get selected type
            document_type = DocumentType.objects.get(
                id=request.POST["doctype"])

            # get list of docs with that type
            current_docs = Document.objects.filter(document_type=document_type)
            if len(current_docs) > 0:
                # if there is already a document with that type abort (user is cheating)
                return

            # set default values
            usercode = UserCode.objects.filter(user=request.user)[0]
            code = 0
            status = "wait"
            personal_data = None
            medical_data = None

            # set to auto_sign if it is the case
            if document_type.auto_sign:
                status = "autosign"

            keys = []
            # copy personal data and medical data
            if document_type.personal_data:
                personal_data = PersonalData(email=request.user.email, parent_name=usercode.parent_name, via=usercode.via, cap=usercode.cap, country=usercode.country,
                                             nationality=usercode.nationality, born_date=usercode.born_date, home_phone=usercode.home_phone, phone=usercode.phone)
                personal_data.save()

            if document_type.medical_data:
                medic = usercode.medic
                medical_data = MedicalData(vac_certificate=medic.vac_certificate, health_care_certificate=medic.health_care_certificate, emer_name=medic.emer_name, emer_relative=medic.emer_relative, cell_phone=medic.cell_phone, address=medic.address, emer_phone=medic.emer_phone, health_care=medic.health_care, injuries=medic.injuries,
                                           rc=medic.rc, rega=medic.rega, medic_name=medic.medic_name, medic_phone=medic.medic_phone, medic_address=medic.medic_address, sickness=medic.sickness, vaccine=medic.vaccine, tetanus_date=medic.tetanus_date, allergy=medic.allergy, drugs_bool=medic.drugs_bool, drugs=medic.drugs, misc_bool=medic.misc_bool, misc=medic.misc)
                medical_data.save()

            # generate document code
            while (True):
                code = randint(100000, 999999)
                if len(Document.objects.filter(code=code)) == 0:
                    break

            # save document
            document = Document(
                user=request.user, group=document_type.group, code=code, status=status, document_type=document_type, personal_data=personal_data, medical_data=medical_data)
            document.save()

            # attach custom keys
            if document_type.custom_data:
                for i in request.POST.keys():
                    if i == "doctype" or i == "csrfmiddlewaretoken" or i == "action":
                        continue
                    key = KeyVal(container=document, key=Keys.objects.get(
                        id=i).key, value=request.POST[i])
                    key.save()

            return HttpResponseRedirect('/')

    return render(request, 'client/doc_create.html', context)


# helper function to call edit_wrapper with empty context
@login_required
def edit(request):
    return edit_wrapper(request, {})


@login_required
def edit_wrapper(request, context):
    if request.method == "POST":
        if "action" not in request.POST.keys():
            # get document
            document = Document.objects.get(id=request.POST["doc"])

            # check if user has permission
            if document.user != request.user:
                return

            # save again all data
            usercode = UserCode.objects.filter(user=document.user)[0]

            if document.document_type.personal_data:
                personal_data = PersonalData(email=request.user.email, parent_name=usercode.parent_name, via=usercode.via, cap=usercode.cap, country=usercode.country,
                                             nationality=usercode.nationality, born_date=usercode.born_date, home_phone=usercode.home_phone, phone=usercode.phone)
                personal_data.save()
                old_data = document.personal_data
                document.personal_data = personal_data
                document.save()
                old_data.delete()

            if document.document_type.medical_data:
                medic = usercode.medic
                medical_data = MedicalData(vac_certificate=medic.vac_certificate, health_care_certificate=medic.health_care_certificate, emer_name=medic.emer_name, emer_relative=medic.emer_relative, cell_phone=medic.cell_phone, address=medic.address, emer_phone=medic.emer_phone, health_care=medic.health_care, injuries=medic.injuries,
                                           rc=medic.rc, rega=medic.rega, medic_name=medic.medic_name, medic_phone=medic.medic_phone, medic_address=medic.medic_address, sickness=medic.sickness, vaccine=medic.vaccine, tetanus_date=medic.tetanus_date, allergy=medic.allergy, drugs_bool=medic.drugs_bool, drugs=medic.drugs, misc_bool=medic.misc_bool, misc=medic.misc)
                medical_data.save()
                old_data = document.medical_data
                document.medical_data = medical_data
                document.save()
                old_data.delete()

            # update again custom keys
            if document.document_type.custom_data:
                for i in request.POST.keys():
                    if i == "doc" or i == "csrfmiddlewaretoken":
                        continue
                    key = KeyVal.objects.filter(Q(container=document) & Q(
                        key=Keys.objects.get(id=i).key))[0]
                    key.value = request.POST[i]
                    key.save()

            return HttpResponseRedirect('/')

    return render(request, 'client/doc_edit.html', context)


def about(request):
    # very simple about page, get version from text file
    version = ""
    with open("version.txt", 'r') as f:
        version = f.read()
        if version.startswith("0"):
            version = "Beta " + version
    context = {"version": version}
    return render(request, 'client/about.html', context)
