from django.shortcuts import render
from django.urls import reverse
from django.shortcuts import redirect
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth import login, authenticate, logout
from django.http import FileResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.debug import sensitive_variables
from django.http import HttpResponseRedirect

from client.models import UserCode, MedicalData

from authlib.integrations.django_client import OAuth

import dateparser
import os
import requests
from random import randint
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from pdf2image import convert_from_bytes
from pdf2image.exceptions import (
    PDFPageCountError,
    PDFSyntaxError
)

oauth = OAuth()
hitobito = oauth.register(name="hitobito")
api_url = settings.AUTHLIB_OAUTH_CLIENTS["hitobito"]["api_url"]

# override to remove help text
class RegisterForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super(RegisterForm, self).__init__(*args, **kwargs)

        for fieldname in ['username', 'password1', 'password2']:
            self.fields[fieldname].help_text = None

def get_oauth_data(token):
    # request data from user account
    headers = {
        "Authorization" : "Bearer " + token,
        "X-Scope": "with_roles",
    }

    return requests.get(api_url, headers=headers)

# send to hitobito request to get token
def oauth_login(request):
    redirect_uri = request.build_absolute_uri(reverse('auth'))
    return hitobito.authorize_redirect(request, redirect_uri)

# callback after acquiring token
def auth(request):
    code = request.GET["code"]
    token = hitobito.authorize_access_token(request)

    # request data from user account
    resp_data = get_oauth_data(token["access_token"]).json()

    # find user with that id
    usercode = UserCode.objects.filter(midata_id=resp_data["id"])
    
    if len(usercode) > 0:
        # user exist
        login(request, usercode[0].user)

        request.user.first_name = resp_data["first_name"]
        request.user.last_name = resp_data["last_name"]
        request.user.email = resp_data["email"]
        request.user.save()

        usercode[0].via = resp_data["address"]
        usercode[0].cap = resp_data["zip_code"]
        usercode[0].country = resp_data["town"]
        usercode[0].born_date = dateparser.parse(resp_data["birthday"])
        usercode[0].midata_token = token["access_token"]
        usercode[0].midata_code = code
        usercode[0].save()

        return HttpResponseRedirect('/')

    user = User.objects.create_user(resp_data["email"], resp_data["email"])

    # create new usercode
    while (True):
        code = randint(100000, 999999)
        if len(UserCode.objects.filter(code=code)) == 0:
            break

    medic = MedicalData()
    medic.save()
    userCode = UserCode(user=user, code=code, medic=medic, midata_id=resp_data["id"], midata_token=token["access_token"], midata_code=code)
    user.first_name = resp_data["first_name"]
    user.last_name = resp_data["last_name"]
    user.email = resp_data["email"]
    user.save()

    userCode.via = resp_data["address"]
    userCode.cap = resp_data["zip_code"]
    userCode.country = resp_data["town"]
    userCode.born_date = dateparser.parse(resp_data["birthday"])
    userCode.save()

    login(request, user)

    return HttpResponseRedirect('/')

# send to hitobito request to get token
@login_required
def oauth_connect(request):
    redirect_uri = request.build_absolute_uri(reverse('auth_connect'))
    return hitobito.authorize_redirect(request, redirect_uri)

@login_required
def oauth_disconnect(request):
    usercode = UserCode.objects.filter(user=request.user)[0]
    usercode.midata_id = 0
    usercode.midata_token = ""
    usercode.midata_code = ""
    usercode.save()

    return HttpResponseRedirect(reverse("personal") + "#settings")

# callback after acquiring token
@login_required
def auth_connect(request):
    token = hitobito.authorize_access_token(request)

    # request data from user account
    resp_data = get_oauth_data(token["access_token"]).json()

    # check that account is not linked to another
    existing_codes = UserCode.objects.filter(midata_id=resp_data["id"])
    if len(existing_codes) > 0:
        return personal_wrapper(request, True, "Questo utente è già collegato ad un altro")

    # save id to user
    usercode = UserCode.objects.filter(user=request.user)[0]
    usercode.midata_id = resp_data["id"]
    usercode.midata_token = token["access_token"]
    usercode.midata_code = request.GET["code"]
    usercode.save()

    return HttpResponseRedirect(reverse("personal") + "#settings")

@sensitive_variables("raw_passsword")
def signup(request):
    out_errors = []
    # signup form with terms
    if request.method == 'POST':
        # get form object
        form = RegisterForm(request.POST)

        # check if terms are accepted
        if "terms_accept" not in request.POST:
            out_errors.append("Accettare i termini e condizioni prego")

        # if form is valid and terms were accepted save user
        if form.is_valid() and len(out_errors) == 0:
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return HttpResponseRedirect('/')
        else:
            # get errors from form and add toasts
            errors = form.errors.as_data()
            for field in errors.keys():
                if field == "username":
                    out_errors.append("Il nome utente può contenere solo lettere e numeri")
                else:
                    password_errors = errors["password2"]
                    for err in password_errors:
                        if err.code == "password_mismatch":
                            out_errors.append("Le due password non sono uguali")
                        elif err.code == "password_too_similar":
                            out_errors.append("La password è troppo simile all'username")
                        elif err.code == "password_too_short":
                            out_errors.append("La password è troppo corta")
                        elif err.code == "password_too_common":
                            out_errors.append("La password è troppo comune")
                        elif err.code == "password_entirely_numeric":
                            out_errors.append("La password deve contenere lettere")

    else:
        # create empty form to be filled
        form = RegisterForm()

    context = {
        "form": form,
        "errors": out_errors,
    }
    return render(request, 'accounts/signup.html', context)

# create wrapper to send custom error from other views (oauth connect/disconnect)
@login_required
def personal(request):
    return personal_wrapper(request, False, "")

@login_required
def personal_wrapper(request, error, error_text):
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

    # variables for validation
    validation_dic = {}
    required_fields = ["first_name", "last_name", "email", "parent_name", "via", "cap", "country", "nationality", "phone", "avs_number", "emer_name", "emer_relative", "cell_phone", "address", "health_care", "injuries", "rc", "medic_name", "medic_phone", "medic_address"]

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
        usercode.avs_number = request.POST["avs_number"]

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

        if request.POST["birth_date"] == "" or request.POST["birth_date"] == "01 Gennaio 1970" or request.POST["birth_date"] == "None":
            validation_dic["birth_date"] = 'class="datepicker validate invalid" required="" aria-required="true"'
            error = True
            error_text = "Alcuni campi richiesti non sono stati compilati"
        else:
            validation_dic["birth_date"] = 'class="datepicker validate" required="" aria-required="true"'

        for i in required_fields:
            if request.POST[i] == "":
                error = True
                error_text = "Alcuni campi richiesti non sono stati compilati"
                validation_dic[i] = 'class="validate invalid" required="" aria-required="true"'
            else:
                validation_dic[i] = 'class="validate" required="" aria-required="true"'

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
                im = Image.new("RGB", (0, 0), (255, 255, 255))
                for f in files:
                    if f.name.endswith(".pdf"):
                        images = convert_from_bytes(f.read())
                        for i in images:
                            dst = Image.new('RGB', (max(im.width, i.width), im.height + i.height), (255, 255, 255))
                            dst.paste(im, (0, 0))
                            dst.paste(i, (0, im.height))
                            im = dst
                    else:
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
            except PDFPageCountError:
                error = True
                error_text = "Il file non è un pdf valido"
            except PDFSyntaxError:
                error = True
                error_text = "Il file non è un pdf valido"
            except IOError:
                error = True
                error_text = "Il file è un immagine troppo grande"

        if "health_care_certificate" in request.FILES:
            files = request.FILES.getlist('health_care_certificate')
            name = files[0].name
            try:
                # if multiple files concatenate pictures
                im = Image.new("RGB", (0, 0), (255, 255, 255))
                for f in files:
                    if f.name.endswith(".pdf"):
                        images = convert_from_bytes(f.read())
                        for i in images:
                            dst = Image.new('RGB', (max(im.width, i.width), im.height + i.height), (255, 255, 255))
                            dst.paste(im, (0, 0))
                            dst.paste(i, (0, im.height))
                            im = dst
                    else:
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
            except PDFPageCountError:
                error = True
                error_text = "Il file non è un pdf valido"
            except PDFSyntaxError:
                error = True
                error_text = "Il file non è un pdf valido"
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

    else:
        # no post, create empty validation
        validation_dic["birth_date"] = 'class="datepicker validate" required="" aria-required="true"'
        for i in required_fields:
            validation_dic[i] = 'class="validate" required="" aria-required="true"'

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

    midata_user = (usercode.midata_id > 0)
    midata_disable = ""

    if midata_user:
        resp = get_oauth_data(usercode.midata_token)

        if resp.status_code != 200:
            request.GET["code"] = usercode.midata_code
            token = hitobito.authorize_access_token(request)
            usercode.midata_token = token["access_token"]
            usercode.save()
            resp = get_oauth_data(usercode.midata_token)

        if resp.status_code != 200:
            logout(request)
            return HttpResponseRedirect("/")

        resp_data = resp.json()

        midata_disable = " disabled"
        request.user.first_name = resp_data["first_name"]
        request.user.last_name = resp_data["last_name"]
        request.user.email = resp_data["email"]
        request.user.save()

        usercode.via = resp_data["address"]
        usercode.cap = resp_data["zip_code"]
        usercode.country = resp_data["town"]
        usercode.born_date = dateparser.parse(resp_data["birthday"])
        usercode.save()

    # fill context
    context = {
        'validation_dic': validation_dic,
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
        'avs_number': usercode.avs_number,
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
        'midata_user': midata_user,
        'midata_disable': midata_disable,
    }

    return render(request, 'accounts/index.html', context)


# simple terms page, only static html
def terms(request):
    context = {}
    return render(request, 'accounts/terms.html', context)
