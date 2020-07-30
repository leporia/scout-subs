from django.shortcuts import render
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate
from django.views import generic
from django.contrib.auth.models import Group
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.debug import sensitive_variables
from django.http import HttpResponseRedirect

from client.models import UserCode

import dateparser, os
from io import BytesIO
from PIL import Image, UnidentifiedImageError


@sensitive_variables("raw_passsword")
def signup(request):
    if request.method == 'POST':
        if "terms_accept" not in request.POST:
            form = UserCreationForm()
            context = {
                "form": form,
                "error": True,
                "error_text": "Accettare i termini e condizioni prego"
            }
            return render(request, 'accounts/signup.html', context)
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return HttpResponseRedirect('/')
    else:
        form = UserCreationForm()
    context = {
        "form": form,
    }
    return render(request, 'accounts/signup.html', context)


@login_required
def personal(request):
    context = {}
    usercode = UserCode.objects.filter(user=request.user)[0]
    medic = usercode.medic
    branca_default = ""
    branca_castorini = ""
    branca_lupetti = ""
    branca_esploratori = ""
    branca_pionieri = ""
    branca_rover = ""
    error = False
    error_text = ""

    if request.method == "POST":
        if request.POST['action'] == "download_vac":
            if medic.vac_certificate != None:
                filename = os.path.basename(medic.vac_certificate.name)
                filename = filename[filename.find("_")+1:]
                if filename.rfind('.') != -1:
                    filename = filename[:filename.rfind('.')]
                filename = filename + ".jpg"
                return FileResponse(medic.vac_certificate.file, as_attachment=True, filename=filename)

        if request.POST['action'] == "download_health":
            if medic.health_care_certificate != None:
                filename = os.path.basename(medic.health_care_certificate.name)
                filename = filename[filename.find("_")+1:]
                if filename.rfind('.') != -1:
                    filename = filename[:filename.rfind('.')]
                filename = filename + ".jpg"
                return FileResponse(medic.health_care_certificate.file, as_attachment=True, filename=filename)

        request.user.first_name = request.POST["first_name"]
        request.user.last_name = request.POST["last_name"]
        request.user.email = request.POST["email"]
        request.user.save()
        usercode.parent_name = request.POST["parent_name"]
        usercode.via = request.POST["via"]
        usercode.cap = request.POST["cap"]
        usercode.country = request.POST["country"]
        usercode.nationality = request.POST["nationality"]
        usercode.born_date = dateparser.parse(request.POST["birth_date"])
        usercode.home_phone = request.POST["home_phone"]
        usercode.phone = request.POST["phone"]
        usercode.school = request.POST["school"]
        usercode.year = request.POST["year"]
        usercode.save()

        medic.emer_name = request.POST["emer_name"]
        medic.emer_relative = request.POST["emer_relative"]
        medic.cell_phone = request.POST["cell_phone"]
        medic.address = request.POST["address"]
        medic.emer_phone = request.POST["emer_phone"]
        medic.health_care = request.POST["health_care"]
        medic.injuries = request.POST["injuries"]
        medic.rc = request.POST["rc"]
        medic.rega = "rega" in request.POST
        medic.medic_name = request.POST["medic_name"]
        medic.medic_phone = request.POST["medic_phone"]
        medic.medic_address = request.POST["medic_address"]
        medic.sickness = request.POST["sickness"]
        medic.vaccine = request.POST["vaccine"]
        medic.tetanus_date = dateparser.parse(request.POST["tetanus_date"])
        medic.allergy = request.POST["allergy"]
        medic.drugs_bool = "drugs_bool" in request.POST
        medic.drugs = request.POST["drugs"]
        medic.misc_bool = "misc_bool" in request.POST
        medic.misc = request.POST["misc"]
        medic.save()

        #if "branca" in request.POST:
        #    if request.POST["branca"] != "":
        #        request.user.groups.clear()
        #        request.user.groups.add(
        #            Group.objects.get(name=request.POST["branca"]))
        
        if "vac_certificate" in request.FILES:
            myfile = request.FILES['vac_certificate']
            try:
                im = Image.open(myfile)
                im_io = BytesIO()
                im.save(im_io, 'WEBP', quality=50)
                medic.vac_certificate.save(request.user.username+"_"+myfile.name, im_io)
                medic.save()
            except UnidentifiedImageError:
                error = True
                error_text = "Il file non è un immagine valida"

        if "health_care_certificate" in request.FILES:
            myfile = request.FILES['health_care_certificate']
            try:
                im = Image.open(myfile)
                im_io = BytesIO()
                im.save(im_io, 'WEBP', quality=50)
                medic.health_care_certificate.save(request.user.username+"_"+myfile.name, im_io)
                medic.save()
            except UnidentifiedImageError:
                error = True
                error_text = "Il file non è un immagine valida"


        if request.POST["delete_vac"] == 'vac':
            medic.vac_certificate = None
            medic.save()

        if request.POST["delete_health"] == 'health':
            medic.health_care_certificate = None
            medic.save()

        if not error:
            return HttpResponseRedirect("")

    if len(request.user.groups.values_list('name', flat=True)) == 0:
        branca_default = "selected"
    else:
        parent_group = request.user.groups.values_list('name', flat=True)[
            0]
        if parent_group == "colonia":
            branca_castorini = "selected"
        elif parent_group == "muta":
            branca_lupetti = "selected"
        elif parent_group == "reparto":
            branca_esploratori = "selected"
        elif parent_group == "posto":
            branca_pionieri = "selected"
        elif parent_group == "clan":
            branca_rover = "selected"
        else:
            branca_default = "selected"

    rega = ""
    if medic.rega:
        rega = "checked='checked'"
    drugs = ""
    if medic.drugs_bool:
        drugs = "checked='checked'"
    misc = ""
    if medic.misc_bool:
        misc = "checked='checked'"

    if (medic.vac_certificate != None):
        vac_name = os.path.basename(medic.vac_certificate.name)
        vac_name = vac_name[vac_name.find("_")+1:]
    else:
        vac_name = ''

    if (medic.health_care_certificate != None):
        card_name = os.path.basename(medic.health_care_certificate.name)
        card_name = card_name[card_name.find("_")+1:]
    else:
        card_name = ''

    context = {
        'first_name': request.user.first_name,
        'last_name': request.user.last_name,
        'email': request.user.email,
        'parent_name': usercode.parent_name,
        'via': usercode.via,
        'cap': usercode.cap,
        'country': usercode.country,
        'nationality': usercode.nationality,
        'birth_date': usercode.born_date,
        'home_phone': usercode.home_phone,
        'phone': usercode.phone,
        'school': usercode.school,
        'year': usercode.year,
        'branca_default': branca_default,
        'branca_castorini': branca_castorini,
        'branca_lupetti': branca_lupetti,
        'branca_esploratori': branca_esploratori,
        'branca_pionieri': branca_pionieri,
        'branca_rover': branca_rover,
        'emer_name': medic.emer_name,
        'emer_relative': medic.emer_relative,
        'cell_phone': medic.cell_phone,
        'address': medic.address,
        'emer_phone': medic.emer_phone,
        'health_care': medic.health_care,
        'injuries': medic.injuries,
        'rc': medic.rc,
        'rega_check': rega,
        'medic_name': medic.medic_name,
        'medic_phone': medic.medic_phone,
        'medic_address': medic.medic_address,
        'sickness': medic.sickness,
        'vaccine': medic.vaccine,
        'tetanus_date': medic.tetanus_date,
        'allergy': medic.allergy,
        'drugs_check': drugs,
        'drugs': medic.drugs,
        'misc_check': misc,
        'misc': medic.misc,
        'health_care_certificate': card_name,
        'vac_certificate': vac_name,
        'error': error,
        'error_text': error_text,
    }

    return render(request, 'accounts/index.html', context)

def terms(request):
    context = {}
    return render(request, 'accounts/terms.html', context)