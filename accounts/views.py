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

import dateparser
import os
from io import BytesIO
from PIL import Image, UnidentifiedImageError


@sensitive_variables("raw_passsword")
def signup(request):
    # signup form with terms
    if request.method == 'POST':
        if "terms_accept" not in request.POST:
            # if terms not accepted return error and form again
            form = UserCreationForm()
            context = {
                "form": form,
                "error": True,
                "error_text": "Accettare i termini e condizioni prego"
            }
            return render(request, 'accounts/signup.html', context)
        # terms accepted create user in db
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return HttpResponseRedirect('/')

    # create empty form to be filled
    form = UserCreationForm()
    context = {
        "form": form,
    }
    return render(request, 'accounts/signup.html', context)


@login_required
def personal(request):
    context = {}
    # additional user informations
    usercode = UserCode.objects.filter(user=request.user)[0]
    # medical info
    medic = usercode.medic
    # values for multiple choice box
    # TODO remove multiple choice
    branca_default = ""
    branca_castorini = ""
    branca_lupetti = ""
    branca_esploratori = ""
    branca_pionieri = ""
    branca_rover = ""

    # variables for throwing errors to the user
    error = False
    error_text = ""

    if request.method == "POST":
        # requested download
        if request.POST['action'] == "download_vac":
            if medic.vac_certificate != None:
                filename = os.path.basename(medic.vac_certificate.name)
                filename = filename[filename.find("_")+1:]
                if filename.rfind('.') != -1:
                    filename = filename[:filename.rfind('.')]
                filename = filename + ".jpg"

                # encode in JPEG
                im = Image.open(medic.vac_certificate.file)
                im_io = BytesIO()
                im.save(im_io, 'JPEG', quality=90)
                im_io.seek(0)
                return FileResponse(im_io, as_attachment=True, filename=filename)

        if request.POST['action'] == "download_health":
            if medic.health_care_certificate != None:
                filename = os.path.basename(medic.health_care_certificate.name)
                filename = filename[filename.find("_")+1:]
                if filename.rfind('.') != -1:
                    filename = filename[:filename.rfind('.')]
                filename = filename + ".jpg"

                # encode in JPEG
                im = Image.open(medic.health_care_certificate.file)
                im_io = BytesIO()
                im.save(im_io, 'JPEG', quality=90)
                im_io.seek(0)
                return FileResponse(im_io, as_attachment=True, filename=filename)

        # set all attributes
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
        if request.POST["year"].isdigit():
            usercode.year = request.POST["year"]
        else:
            error = True
            error_text = "L'anno scolastico deve essere un numero"

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

        # if "branca" in request.POST:
        #    if request.POST["branca"] != "":
        #        request.user.groups.clear()
        #        request.user.groups.add(
        #            Group.objects.get(name=request.POST["branca"]))

        # check if user uploaded a file
        if "vac_certificate" in request.FILES:
            files = request.FILES.getlist('vac_certificate')
            name = files[0].name
            try:
                # if multiple files concatenate pictures
                if len(files) == 1:
                    im = Image.open(files[0])
                else:
                    im = Image.open(files.pop(0))
                    for f in files:
                        i = Image.open(f)
                        dst = Image.new('RGB', (max(im.width, i.width), im.height + i.height), (255, 255, 255))
                        dst.paste(im, (0, 0))
                        dst.paste(i, (0, im.height))
                        im = dst

                im_io = BytesIO()
                # resize image if larger than max value
                if im.height > 16383:
                    im = im.resize((round(im.width/im.height*16383), 16383))
                # compress image in WEBP
                im.save(im_io, 'WEBP', quality=50, method=4)
                medic.vac_certificate.save(
                    request.user.username+"_"+name, im_io)
                medic.save()
            except UnidentifiedImageError:
                error = True
                error_text = "Il file non è un immagine valida"
            except IOError:
                error = True
                error_text = "Il file è un immagine troppo grande"

        if "health_care_certificate" in request.FILES:
            files = request.FILES.getlist('health_care_certificate')
            name = files[0].name
            try:
                # if multiple files concatenate pictures
                if len(files) == 1:
                    im = Image.open(files[0])
                else:
                    im = Image.open(files.pop(0))
                    for f in files:
                        i = Image.open(f)
                        dst = Image.new('RGB', (max(im.width, i.width), im.height + i.height), (255, 255, 255))
                        dst.paste(im, (0, 0))
                        dst.paste(i, (0, im.height))
                        im = dst

                im_io = BytesIO()
                # resize image if larger than max value
                if im.height > 16383:
                    im = im.resize((round(im.width/im.height*16383), 16383))
                # compress image in WEBP
                im.save(im_io, 'WEBP', quality=50, method=4)
                medic.health_care_certificate.save(
                    request.user.username+"_"+name, im_io)
                medic.save()
            except UnidentifiedImageError:
                error = True
                error_text = "Il file non è un immagine valida"
            except IOError:
                error = True
                error_text = "Il file è un immagine troppo grande"

        # user requested file delete
        if request.POST["delete_vac"] == 'vac':
            medic.vac_certificate = None
            medic.save()

        if request.POST["delete_health"] == 'health':
            medic.health_care_certificate = None
            medic.save()

        # if there wasn't any error redirect to clear POST
        if not error:
            return HttpResponseRedirect("")

    # check if user is in a group and set multiple choice to that
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

    # set checkbox status
    rega = ""
    if medic.rega:
        rega = "checked='checked'"
    drugs = ""
    if medic.drugs_bool:
        drugs = "checked='checked'"
    misc = ""
    if medic.misc_bool:
        misc = "checked='checked'"

    # set file name for uploaded files
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

    # fill context
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


# simple terms page, only static html
def terms(request):
    context = {}
    return render(request, 'accounts/terms.html', context)
