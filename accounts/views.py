import datetime
from django import forms
from django.shortcuts import render
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm, UserCreationForm
from django.contrib.auth.models import User, Group
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.views import LoginView
from django.http import FileResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.debug import sensitive_variables
from django.http import HttpResponseRedirect
from django.core.exceptions import ValidationError

from client.models import UserCode, MedicalData

from authlib.integrations.django_client import OAuth

import json
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

# suppress warning about dateparser deprecated dependencies
import warnings
warnings.filterwarnings(
    "ignore",
    message="The localize method is no longer necessary, as this time zone supports the fold attribute",
)

oauth = OAuth()
hitobito = oauth.register(name="hitobito")
api_url = settings.AUTHLIB_OAUTH_CLIENTS["hitobito"]["api_url"]
MIDATA_ENABLED = settings.OAUTH_ENABLED

# override to remove help text
class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super(UserCreationForm, self).__init__(*args, **kwargs)

        for fieldname in ['username', 'password1', 'password2']:
            self.fields[fieldname].help_text = None

    def save(self, commit=True):
        user = super().save()
        user.set_password(self.cleaned_data["password1"])
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user

class AuthForm(AuthenticationForm):
    error_messages = {
        'invalid_login': ("Password errata e/o utente inesistente"),
        'inactive': ("Utente disattivato"),
        'midata_user': ("Utilizza il login con MiData collegato all'utente"),
    }
    def confirm_login_allowed(self, user):
        usercode = UserCode.objects.filter(user=user)

        if len(usercode) > 0:
            if usercode[0].midata_id > 0:
                raise ValidationError(
                    self.error_messages['midata_user'],
                    code='midata_user',
                )

        if not user.is_active:
            raise ValidationError(
                self.error_messages['inactive'],
                code='inactive',
            )

# request data from user account
def get_oauth_data(token):
    headers = {
        "Authorization" : "Bearer " + token,
        "X-Scope": "with_roles",
    }

    return requests.get(api_url, headers=headers)

def copy_from_midata(request, usercode):
    resp = get_oauth_data(usercode.midata_token)

    if resp.status_code != 200:
        logout(request)
        return False

    resp_data = resp.json()

    request.user.first_name = resp_data["first_name"]
    request.user.last_name = resp_data["last_name"]
    request.user.email = resp_data["email"]
    request.user.save()

    usercode.via = resp_data["address"]
    usercode.cap = resp_data["zip_code"]
    usercode.country = resp_data["town"]
    usercode.born_date = dateparser.parse(resp_data["birthday"])
    usercode.save()

    return True

### Views ###

class CustomLoginView(LoginView):
    form_class = AuthForm
    extra_context = {'midata_enabled': MIDATA_ENABLED}

    def get(self, request, *args, **kwargs):
        # check auto-login is enabled
        if "autologin" not in request.COOKIES:
            return super(CustomLoginView, self).get(request, *args, **kwargs)

        if request.COOKIES.get("autologin") != "true":
            return super(CustomLoginView, self).get(request, *args, **kwargs)

        # check if user has a cookie saved
        response = HttpResponseRedirect("/")

        # no cookie
        if "user_switcher" not in request.COOKIES:
            return super(CustomLoginView, self).get(request, *args, **kwargs)

        sessions = json.loads(request.COOKIES.get("user_switcher"))

        # empty cookie
        if len(sessions) == 0: 
            return super(CustomLoginView, self).get(request, *args, **kwargs)

        # pick the first username to login to
        username = list(sessions.keys())[0]

        set_session_cookie(response, sessions[username][0], sessions[username][1])
        del sessions[username]

        set_switch_cookie(response, sessions)

        # disable autologin
        response.set_cookie("autologin", "false")

        return response

# send to hitobito request to get token
def oauth_login(request):
    if not MIDATA_ENABLED:
        return None

    redirect_uri = request.build_absolute_uri(reverse('auth'))

    # forward next page requested by user
    if not request.GET["next"]:
        redirect_uri += "?next=/"
    else:
        redirect_uri += "?next=" + request.GET["next"]

    return hitobito.authorize_redirect(request, redirect_uri)

# callback after acquiring token
def auth(request):
    if not MIDATA_ENABLED:
        return None

    token = hitobito.authorize_access_token(request)

    # request data from user account
    resp_data = get_oauth_data(token["access_token"]).json()

    # find user with that id
    usercode = UserCode.objects.filter(midata_id=resp_data["id"])
    
    if len(usercode) > 0:
        # user exist
        login(request, usercode[0].user)

        usercode[0].midata_token = token["access_token"]
        usercode[0].save()

        copy_from_midata(request, usercode[0])

        return HttpResponseRedirect(request.GET["next"])

    # create new user
    user = User.objects.create_user(resp_data["email"], resp_data["email"])

    # create new usercode
    while (True):
        code = randint(100000, 999999)
        if len(UserCode.objects.filter(code=code)) == 0:
            break

    medic = MedicalData()
    medic.save()
    usercode = UserCode(user=user, code=code, medic=medic, midata_id=resp_data["id"], midata_token=token["access_token"])

    login(request, user)

    copy_from_midata(request, usercode)

    return HttpResponseRedirect(request.GET["next"])

# send to hitobito request to get token
@login_required
def oauth_connect(request):
    if not MIDATA_ENABLED:
        return None

    redirect_uri = request.build_absolute_uri(reverse('auth_connect'))
    return hitobito.authorize_redirect(request, redirect_uri)

# clear token only if user has another way to login
@login_required
def oauth_disconnect(request):
    if not request.user.has_usable_password():
        return personal_wrapper(request, ["Il tuo utente non ha una password impostata, impostare una password prima di scollegarlo da MiData"])

    usercode = UserCode.objects.filter(user=request.user)[0]
    usercode.midata_id = 0
    usercode.midata_token = ""
    usercode.save()

    return HttpResponseRedirect(reverse("personal") + "#settings")

# callback after acquiring token
@login_required
def auth_connect(request):
    if not MIDATA_ENABLED:
        return None

    token = hitobito.authorize_access_token(request)

    # request data from user account
    resp_data = get_oauth_data(token["access_token"]).json()

    # check that account is not linked to another
    existing_codes = UserCode.objects.filter(midata_id=resp_data["id"])
    if len(existing_codes) > 0:
        return personal_wrapper(request, ["Questo utente è già collegato ad un altro"])

    # save id to user
    usercode = UserCode.objects.filter(user=request.user)[0]
    usercode.midata_id = resp_data["id"]
    usercode.midata_token = token["access_token"]
    usercode.save()

    return HttpResponseRedirect(reverse("personal") + "#settings")

@sensitive_variables("sessionid")
def set_session_cookie(response, sessionid, expires):
    expires_date = datetime.datetime.fromtimestamp(int(expires))
    max_age = (expires_date - datetime.datetime.utcnow()).total_seconds()
    response.set_cookie(
        "sessionid",
        sessionid,
        max_age=max_age,
        expires=expires,
        domain=settings.SESSION_COOKIE_DOMAIN,
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )

@sensitive_variables("data")
def set_switch_cookie(response, data):

    max_age = 30 * 60 * 60 * 24
    expires = datetime.datetime.strftime(
        datetime.datetime.utcnow() + datetime.timedelta(seconds=max_age),
        "%a, %d-%b-%Y %H:%M:%S GMT",
    )
    response.set_cookie(
        "user_switcher",
        json.dumps(data),
        max_age=max_age,
        expires=expires,
        domain=settings.SESSION_COOKIE_DOMAIN,
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )

@sensitive_variables("sessions")
def user_switcher(request):
    if request.method == 'POST':
        if request.POST["metadata"] == 'new':
            response = HttpResponseRedirect('/accounts/login')

            sessions = dict()
            if "user_switcher" in request.COOKIES:
                sessions = json.loads(request.COOKIES.get("user_switcher"))

            sessions[request.user.username] = (request.session.session_key, request.session.get_expiry_date().timestamp())
            set_switch_cookie(response, sessions)

            response.set_cookie("sessionid", "")
            response.set_cookie("autologin", "false")

            return response

        elif request.POST["metadata"][0] == 's':
            response = HttpResponseRedirect("/")
            username = request.POST["metadata"][1:]

            sessions = dict()
            if "user_switcher" in request.COOKIES:
                sessions = json.loads(request.COOKIES.get("user_switcher"))

            sessions[request.user.username] = (request.session.session_key, request.session.get_expiry_date().timestamp())

            if username in sessions:
                set_session_cookie(response, sessions[username][0], sessions[username][1])
                del sessions[username]
            else:
                set_session_cookie(response, "", 0)

            set_switch_cookie(response, sessions)

            response.set_cookie("autologin", "false")

            return response
        elif request.POST["metadata"] == "logout":
            # send user to logout page
            # on the login page we check if we have a cookie set
            response = HttpResponseRedirect("/accounts/logout")
            response.set_cookie("autologin", "true")

            return response

    
    return HttpResponseRedirect("/")

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
            errors_list = [x for xs in errors.values() for x in xs]
            errors_text = list(map(lambda x: x.message, errors_list))
            out_errors += errors_text

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
    return personal_wrapper(request, [])

@login_required
def personal_wrapper(request, errors):
    context = {}
    ok_message = ""

    if request.method == "POST":
        if request.POST['action'] == "password":
            # get form object
            if request.user.has_usable_password():
                form2 = PasswordChangeForm(data=request.POST, user=request.user)
            else:
                form2 = SetPasswordForm(data=request.POST, user=request.user)

            # if form is valid and terms were accepted save user
            if form2.is_valid():
                form2.save()
                ok_message = "Password modificata con successo"
            else:
                for field in form2.errors.as_data().values():
                    for err in field:
                        if err.code == "password_mismatch":
                            errors.append("Le due password non sono uguali")
                        elif err.code == "password_too_similar":
                            errors.append("La password è troppo simile all'username")
                        elif err.code == "password_too_short":
                            errors.append("La password è troppo corta")
                        elif err.code == "password_too_common":
                            errors.append("La password è troppo comune")
                        elif err.code == "password_entirely_numeric":
                            errors.append("La password deve contenere lettere")
                        elif err.code == "password_incorrect":
                            errors.append("La password attuale è incorretta")

    usable_password = request.user.has_usable_password()

    # fill context
    context = {
        'email': request.user.email,
        'errors': errors,
        'ok_message': ok_message,
        'usable_password': usable_password,
    }

    return render(request, 'accounts/index.html', context)

@login_required
def edit(request, code):
    errors = []
    context = {}
    ok_message = ""
    usercode = None

    # additional user information
    if (code == 0):
        # generate code
        while (True):
            code = randint(100000, 999999)
            if len(UserCode.objects.filter(code=code)) == 0:
                break

        # create empty usercode
        # if render before save this is a dummy never used
        medic = MedicalData()
        usercode = [UserCode(user=request.user, code=code, medic=medic, branca=None)]
    else:
        usercode = UserCode.objects.filter(code=code)

    if (len(usercode) == 0):
        # no avaiable code, create dummy
        medic = MedicalData()
        usercode = [UserCode(user=request.user, code=code, medic=medic, branca=None)]

    usercode = usercode[0]
    if (usercode.user != request.user):
        # code is not authorised for this user
        return
        
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
    required_fields = ["first_name", "last_name", "parent_name", "via", "cap", "country", "nationality", "phone", "avs_number", "emer_name", "emer_relative", "cell_phone", "address", "health_care", "injuries", "rc", "medic_name", "medic_phone", "medic_address", "sickness", "vaccine"]

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

        elif request.POST['action'] == "download_health":
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

        elif request.POST['action'] == "delete_uc":
            confirm_name = request.POST['del_name']
            correct_name = usercode.first_name + " " + usercode.last_name
            if (confirm_name == correct_name):
                usercode.delete()
                medic.delete()
                return HttpResponseRedirect("/")

            errors.append("Il nome inserito non corrisponde al nome salvato")

        else:
            if not request.POST["first_name"] or not request.POST["last_name"]:
                errors.append("Nome e cognome sono obbligatori per salvare l'utente")

            # set all attributes
            usercode.first_name = request.POST["first_name"]
            usercode.last_name = request.POST["last_name"]
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
                errors.append("L'anno scolastico deve essere un numero")

            if "branca" in request.POST:
                if request.POST["branca"] != "" and request.POST["branca"] in ["diga", "muta", "reparto", "posto", "clan"]:
                    usercode.branca = Group.objects.get(name=request.POST["branca"])

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

            missing_fields = False

            if request.POST["birth_date"] == "" or request.POST["birth_date"].lower() == "01 gennaio 1970" or request.POST["birth_date"] == "None" or request.POST["birth_date"] == "Giovedì 01 Gennaio 1970 00:00" or request.POST["birth_date"] == "Giovedì 01 Gennaio 1970 01:00":
                validation_dic["birth_date"] = 'class="datepicker validate invalid" required="" aria-required="true"'
                missing_fields = True
            else:
                validation_dic["birth_date"] = 'class="datepicker validate" required="" aria-required="true"'

            if request.POST["tetanus_date"] == "" or request.POST["tetanus_date"].lower() == "01 gennaio 1970" or request.POST["tetanus_date"] == "None" or request.POST["tetanus_date"] == "Giovedì 01 Gennaio 1970 00:00" or request.POST["tetanus_date"] == "Giovedì 01 Gennaio 1970 01:00":
                validation_dic["tetanus_date"] = 'class="datepicker validate invalid" required="" aria-required="true"'
                missing_fields = True
            else:
                validation_dic["tetanus_date"] = 'class="datepicker validate" required="" aria-required="true"'

            for i in required_fields:
                if request.POST[i] == "":
                    missing_fields = True
                    validation_dic[i] = 'class="validate invalid" required="" aria-required="true"'
                else:
                    validation_dic[i] = 'class="validate" required="" aria-required="true"'

            if missing_fields:
                errors.append("Alcuni campi richiesti non sono stati compilati")

            # check if user uploaded a file
            if "vac_certificate" in request.FILES:
                files = request.FILES.getlist('vac_certificate')
                name = files[0].name
                try:
                    # if multiple files concatenate pictures
                    im = Image.new("RGB", (0, 0), (255, 255, 255))
                    for f in files:
                        if f.name.endswith(".pdf") or f.name.endswith(".PDF"):
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
                except UnidentifiedImageError:
                    errors.append("Il certificato delle vaccinazioni non è un immagine valida")
                except PDFPageCountError:
                    errors.append("Il certificato delle vaccinazioni non è un pdf valido")
                except PDFSyntaxError:
                    errors.append("Il certificato delle vaccinazioni non è un pdf valido")
                except IOError:
                    errors.append("Il certificato delle vaccinazioni è un immagine troppo grande")

            if "health_care_certificate" in request.FILES:
                files = request.FILES.getlist('health_care_certificate')
                name = files[0].name
                try:
                    # if multiple files concatenate pictures
                    im = Image.new("RGB", (0, 0), (255, 255, 255))
                    for f in files:
                        if f.name.endswith(".pdf") or f.name.endswith(".PDF"):
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
                except UnidentifiedImageError:
                    errors.append("La tessera della cassa malati non è un immagine valida")
                except PDFPageCountError:
                    errors.append("La tessera della cassa malati non è un pdf valido")
                except PDFSyntaxError:
                    errors.append("La tessera della cassa malati non è un pdf valido")
                except IOError:
                    errors.append("La tessera della cassa malati è un immagine troppo grande")

            # user requested file delete
            if request.POST["delete_vac"] == 'vac':
                medic.vac_certificate = None

            if request.POST["delete_health"] == 'health':
                medic.health_care_certificate = None

            if request.POST["first_name"] and request.POST["last_name"]:
                medic.save()

            if request.POST["first_name"] and request.POST["last_name"]:
                usercode.save()

            # if there wasn't any error redirect to clear POST
            if len(errors) == 0:
                return HttpResponseRedirect(request.get_full_path())

    else:
        # no post, create empty validation
        validation_dic["birth_date"] = 'class="datepicker validate" required="" aria-required="true"'
        for i in required_fields:
            validation_dic[i] = 'class="validate" required="" aria-required="true"'

    # check if user is in a group and set multiple choice to that
    if usercode.branca == None:
        branca_default = "selected"
    else:
        branca = usercode.branca.name
        if branca == "diga":
            branca_castorini = "selected"
        elif branca == "muta":
            branca_lupetti = "selected"
        elif branca == "reparto":
            branca_esploratori = "selected"
        elif branca == "posto":
            branca_pionieri = "selected"
        elif branca == "clan":
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

    # check if user has saved the form
    home_tooltip = False
    if "saved" in request.GET:
        # show tooltip only if user is not approved and there are no errors
        home_tooltip = (len(errors) == 0)

    print("date", usercode.born_date)

    # fill context
    context = {
        'ucode': code,
        'validation_dic': validation_dic,
        'first_name': usercode.first_name,
        'last_name': usercode.last_name,
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
        'errors': errors,
        'ok_message': ok_message,
        'home_tooltip': home_tooltip,
    }

    return render(request, 'accounts/user_edit.html', context)

# simple terms page, only static html
def terms(request):
    context = {}
    return render(request, 'accounts/terms.html', context)


def logout_view(request):
    logout(request)
    return HttpResponseRedirect('/')