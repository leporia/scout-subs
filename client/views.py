from django.template.loader import get_template
from client.models import GroupSettings, UserCode, Keys, DocumentType, Document, PersonalData, KeyVal, MedicalData
from django.db.models import Q
from django.http import HttpResponseRedirect, FileResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from io import BytesIO
import pdfkit
from subprocess import check_output
from datetime import datetime
import pytz
from random import randint

def index(request):
    context = {}
    group_view = False
    # check if user is logged
    if (request.user.is_authenticated):
        if not (request.user.is_staff or request.user.has_perm("client.approved")):
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

            user_code = None
            usercode = UserCode.objects.filter(user=request.user)[0]
            if request.user.first_name != "" and request.user.last_name != "" and request.user.email != "" and usercode.phone != "":
                user_code = "U" + str(usercode.code)
            context = {"user_code": user_code}
        else:
            # get user group
            groups = request.user.groups.all()

            # check if any group has enabled RO documents
            if request.user.is_staff or len(groups.filter(name="capi")) == 0:
                # if user is staff then not needed
                gr = []
            elif request.user.has_perm("client.staff"):
                gr = GroupSettings.objects.filter(group__in=groups).filter(view_documents=True).filter(~Q(group=groups[0]))
            else:
                gr = GroupSettings.objects.filter(group__in=groups).filter(view_documents=True)

            group_view = len(gr) != 0

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
                    context['keys'] = KeyVal.objects.filter(container=document)
                    context['custom_message'] = document_type.custom_message
                    context['custom_message_text'] = document_type.custom_message_text
                    return edit_wrapper(request, context)

            # show only docs of the user and non archived
            documents = Document.objects.filter(
                Q(user=request.user) & ~Q(status='archive')).select_related("personal_data", "medical_data", "document_type", "user")

            vac_file = ["/server/media/", "/vac_certificate/doc"]
            health_file = ["/server/media/", "/health_care_certificate/doc"]
            sign_doc_file = ["/server/media/", "/signed_doc/doc"]

            context = {
                "docs": documents,
                "base_group": groups[0].name,
                "empty": len(documents) == 0,
                "group_view": group_view,
                "vac_file": vac_file,
                "health_file": health_file,
                "sign_doc_file": sign_doc_file
            }

    return render(request, 'client/index.html', context)


@login_required
def create(request):
    context = {}
    # group name and obj
    parent_groups = request.user.groups.values_list('name', flat=True)

    # get available types for user
    filter = (Q(group_private=False) | Q(group__name__in=parent_groups)) & Q(enabled=True)
    if not request.user.is_staff and "capi" not in request.user.groups.values_list('name',flat = True):
        filter = filter & Q(staff_only=False)

    # remove from the list documents from already used types
    doctypes = DocumentType.objects.filter(filter).values_list("id", flat=True).difference(Document.objects.filter(user=request.user).select_related("document_type").values_list("document_type", flat=True))

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
                    return

            # check if user has permission to use that type
            if document_type.staff_only and not request.user.is_staff and "capi" not in request.user.groups.values_list('name', flat = True):
                # user is cheating abort
                return

            if not document_type.custom_group and document_type.group.name not in request.user.groups.values_list('name', flat=True):
                # user is cheating abort
                return

            # get list of docs with that type
            current_docs = Document.objects.filter(user=request.user).filter(document_type=document_type)
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
                    key = KeyVal(container=document, key=Keys.objects.get(id=i).key, value=request.POST[i])
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

            # update compilation date
            document.compilation_date = pytz.timezone('Europe/Zurich').localize(datetime.now())
            document.save(update_fields=["compilation_date"])

            # save again all data
            usercode = UserCode.objects.filter(user=document.user)[0]

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
                    key = KeyVal.objects.get(id=i)
                    key.value = request.POST[i]
                    key.save()

            return HttpResponseRedirect('/')

    return render(request, 'client/doc_edit.html', context)


def about(request):
    # very simple about page, get version from text file
    version = ""

    with open("version.txt", 'r') as f:
        version = f.read()

    # parse file
    version = version[version.find("=")+1:]
    version = version.replace("\n", " ").replace("=", " ")

    if version.startswith("0"):
        version = "Beta " + version

    # get commitid using git command, a bit hacky but works
    commitid = check_output(["git", "rev-parse", "HEAD"]).decode()

    context = {"version": version, "commitid": commitid}
    return render(request, 'client/about.html', context)
