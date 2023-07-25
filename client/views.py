from django.db.models.expressions import OuterRef, Subquery
from django.template.loader import get_template
from django.urls import reverse
from client.models import HideGroup, UserCode, Keys, DocumentType, Document, PersonalData, KeyVal, MedicalData
from django.db.models import Q
from django.http import HttpResponseRedirect, FileResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from accounts.views import copy_from_midata
from django.conf import settings

from io import BytesIO
import pdfkit
from datetime import datetime
import pytz
from random import randint

def migration_usercode(void):
    usercodes = UserCode.objects.all()
    for uc in usercodes:
        user = uc.user
        uc.first_name = user.first_name
        uc.last_name = user.last_name
        uc.email = user.email
        uc.branca = user.groups.all()[0]
        uc.save()

    # also iterate all docs and set usercode
    for d in Document.objects.all():
        uc = UserCode.objects.filter(user=d.user)[0]
        d.usercode = uc
        d.save()

@login_required()
def index(request):
    context = {}
    ucs = UserCode.objects.filter(user=request.user)

    if (len(ucs) == 0):
        # the user has no person
        return render(request, 'client/index.html', {})

    # user action
    if request.method == "POST":
        # get document id
        document = Document.objects.get(id=request.POST["action"][1:])

        # check if document is valid to modify
        if document.usercode not in ucs:
            return HttpResponseRedirect("/")

        if document.status == "ok" or document.status == "archive":
            return HttpResponseRedirect("/")

        # execute action
        if request.POST["action"][0] == 'f':
            # generate approve pdf
            template = get_template('client/approve_doc_pdf.html')
            context = {'doc': document, 'uri': settings.FQD_BASE_URL + reverse('approve_direct') + "?code=" + str(document.code)}
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
            keys = Keys.objects.filter(container=document_type).annotate(value=Subquery(
                KeyVal.objects.filter(container=document, key=OuterRef('key')).values('value')
            ))
            context['keys'] = keys
            context['custom_message'] = document_type.custom_message
            context['custom_message_text'] = document_type.custom_message_text
            return edit_wrapper(request, context)

    # divide the docs for each uc
    docs = []
    for uc in ucs:
        documents = Document.objects.filter(
            Q(usercode=uc) & ~Q(status='archive')).select_related("personal_data", "medical_data", "document_type", "user")
        color_mapping = {
            "diga": "#ffeb3b",
            "muta": "#03a9f4",
            "reparto": "#795548",
            "posto": "#f44336",
            "clan": "#4caf50"
        }
        if uc.branca == None:
            color = "black"
        else:
            color = color_mapping[uc.branca.name]
        docs.append([uc, documents, color])
    # show only docs of the user and non archived

    vac_file = ["/server/media/", "/vac_certificate/doc"]
    health_file = ["/server/media/", "/health_care_certificate/doc"]
    sign_doc_file = ["/server/media/", "/signed_doc/doc"]

    context = {
        "docs": docs,
        "vac_file": vac_file,
        "health_file": health_file,
        "sign_doc_file": sign_doc_file
    }

    return render(request, 'client/index.html', context)


@login_required
def create(request, code):
    context = {}
    usercode = UserCode.objects.filter(user=request.user, code=code)
    if (len(usercode) == 0):
        # the user has no person
        return HttpResponseRedirect("/")
    
    usercode = usercode[0]

    if usercode.branca == None:
        return HttpResponseRedirect("/")

    # get available types for user
    filter = (Q(group_private=False) | Q(group__name=usercode.branca.name)) & Q(enabled=True)
    if not request.user.is_staff and "capi" not in request.user.groups.values_list('name',flat = True):
        filter = filter & Q(staff_only=False)

    # remove from the list documents from already used types
    doctypes = DocumentType.objects.filter(filter).values_list("id", flat=True).difference(Document.objects.filter(Q(usercode=usercode) & ~Q(status="archive")).select_related("document_type").values_list("document_type", flat=True))
    doctypes = doctypes.difference(HideGroup.objects.filter(group__name=usercode.branca.name).select_related("doc_type").values_list("doc_type", flat=True))

    context["uc"] = usercode
    context['docs'] = DocumentType.objects.filter(id__in=doctypes)
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

                # check if there are still free spaces
                context['no_free_places'] = False
                if document_type.max_instances != 0:
                    if len(Document.objects.filter(document_type=document_type)) - len(Document.objects.filter(document_type=document_type, status="archive")) >= document_type.max_instances:
                        context['no_free_places'] = True

                context['personal_data'] = document_type.personal_data
                context['medical_data'] = document_type.medical_data
                context['custom_data'] = document_type.custom_data
                context['keys'] = Keys.objects.filter(container=document_type)
                context['custom_message'] = document_type.custom_message
                context['custom_message_text'] = document_type.custom_message_text
        elif request.POST["action"] == "save":
            # after type was selected it shows details to complete

            # get selected type
            document_type = DocumentType.objects.get(
                id=request.POST["doctype"])

            # check if there are free spaces
            if document_type.max_instances != 0:
                if len(Document.objects.filter(document_type=document_type)) - len(Document.objects.filter(document_type=document_type, status="archive")) >= document_type.max_instances:
                    # there aren't user is cheating
                    return HttpResponseRedirect("/")

            # check if user has permission to use that type
            if document_type.staff_only and not request.user.is_staff and "capi" not in request.user.groups.values_list('name', flat = True):
                # user is cheating abort
                return HttpResponseRedirect("/")

            if document_type.group_private and document_type.group.name != usercode.branca.name:
                # user is cheating abort
                return HttpResponseRedirect("/")

            # get list of docs with that type
            current_docs = Document.objects.filter(usercode=usercode).filter(Q(document_type=document_type) & ~Q(status="archive"))
            if len(current_docs) > 0:
                # if there is already a document with that type abort (user is cheating)
                return HttpResponseRedirect("/")

            # set default values
            code = 0
            status = "wait"
            personal_data = None
            medical_data = None

            # set to auto_sign if it is the case
            if document_type.auto_sign:
                status = "autosign"

            # copy personal data and medical data
            if document_type.personal_data:
                personal_data = PersonalData(email=request.user.email, parent_name=usercode.parent_name, via=usercode.via, cap=usercode.cap, country=usercode.country,
                                             nationality=usercode.nationality, born_date=usercode.born_date, home_phone=usercode.home_phone, phone=usercode.phone, school=usercode.school, year=usercode.year, avs_number=usercode.avs_number)
                personal_data.save()

            if document_type.medical_data:
                medic = usercode.medic
                medical_data = MedicalData(vac_certificate=medic.vac_certificate, health_care_certificate=medic.health_care_certificate, emer_name=medic.emer_name, emer_relative=medic.emer_relative, cell_phone=medic.cell_phone, address=medic.address, emer_phone=medic.emer_phone, health_care=medic.health_care, injuries=medic.injuries,
                                           rc=medic.rc, rega=medic.rega, medic_name=medic.medic_name, medic_phone=medic.medic_phone, medic_address=medic.medic_address, sickness=medic.sickness, vaccine=medic.vaccine, tetanus_date=medic.tetanus_date, allergy=medic.allergy, drugs_bool=medic.drugs_bool, drugs=medic.drugs, misc_bool=medic.misc_bool, misc=medic.misc)
                medical_data.save()

            # generate document code
            while (True):
                dcode = randint(100000, 999999)
                if len(Document.objects.filter(code=dcode)) == 0:
                    break

            # save document
            document = Document(
                usercode=usercode, group=document_type.group, code=dcode, status=status, document_type=document_type, personal_data=personal_data, medical_data=medical_data)
            document.save()

            # attach custom keys
            if document_type.custom_data:
                for i in request.POST.keys():
                    if i == "doctype" or i == "csrfmiddlewaretoken" or i == "action":
                        continue
                    key = KeyVal(container=document, key=Keys.objects.get(id=i).key, value=request.POST[i])
                    key.save()

            return HttpResponseRedirect('/?approve_doc=' + str(document.id))

    return render(request, 'client/doc_create.html', context)


# helper function to call edit_wrapper with empty context
@login_required
def edit(request):
    return edit_wrapper(request, {})


@login_required
def edit_wrapper(request, context):
    if request.method == "POST":
        usercode = UserCode.objects.filter(user=request.user)[0]
        if usercode.midata_id > 0:
            if not copy_from_midata(request, usercode):
                return HttpResponseRedirect(request.path_info)

        if "action" not in request.POST.keys():
            # get document
            document = Document.objects.get(id=request.POST["doc"])

            # check if user has permission
            if document.user != request.user:
                return HttpResponseRedirect("/")

            # check if document is editable
            if document.status != "wait" and document.status != "autosign":
                # user is cheating
                return HttpResponseRedirect("/")

            # update compilation date
            document.compilation_date = pytz.timezone('Europe/Zurich').localize(datetime.now())
            document.save(update_fields=["compilation_date"])

            # save again all data
            if document.document_type.personal_data:
                personal_data = PersonalData(email=request.user.email, parent_name=usercode.parent_name, via=usercode.via, cap=usercode.cap, country=usercode.country,
                                             nationality=usercode.nationality, born_date=usercode.born_date, home_phone=usercode.home_phone, phone=usercode.phone, school=usercode.school, year=usercode.year, avs_number=usercode.avs_number)
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
                    key = KeyVal.objects.filter(key=i, container=document)
                    if len(key) == 0:
                        new_key = KeyVal(container=document, key=i, value=request.POST[i])
                        new_key.save()
                    else:
                        key[0].value = request.POST[i]
                        key[0].save()

            return HttpResponseRedirect('/')

    return render(request, 'client/doc_edit.html', context)


def about(request):
    # very simple about page, get version from text file
    version = settings.VERSION

    # parse file
    version = version[version.find("=")+1:]
    version = version.replace("\n", " ").replace("=", " ")

    # get branch
    branch = settings.BRANCH
    version += " (" + branch[:-1] + ")"

    if version.startswith("0"):
        version = "Beta " + version

    context = {"version": version, "commitid": settings.COMMIT_ID}
    return render(request, 'client/about.html', context)
