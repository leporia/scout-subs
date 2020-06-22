from django.shortcuts import render
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy
from django.views import generic
from django.contrib.auth.models import Group
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse

from client.models import UserCode

import dateparser, os


class SignUp(generic.CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy('login')
    template_name = 'accounts/signup.html'


def personal(request):
    context = {}
    if request.user.is_authenticated:
        usercode = UserCode.objects.filter(user=request.user)[0]
        medic = usercode.medic
        debug = ""
        branca_default = ""
        branca_castorini = ""
        branca_lupetti = ""
        branca_esploratori = ""
        branca_pionieri = ""
        branca_rover = ""

        if request.method == "POST":
            if request.POST['action'] == "download_vac":
                if medic.vac_certificate != None:
                    filename = os.path.basename(medic.vac_certificate.name)
                    filename = filename[filename.find("_")+1:]
                    return FileResponse(medic.vac_certificate.file, as_attachment=True, filename=filename)

            if request.POST['action'] == "download_health":
                if medic.health_care_certificate != None:
                    filename = os.path.basename(medic.health_care_certificate.name)
                    filename = filename[filename.find("_")+1:]
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

            if request.POST["branca"] != "":
                request.user.groups.clear()
                request.user.groups.add(
                    Group.objects.get(name=request.POST["branca"]))
            
            if "vac_certificate" in request.FILES:
                myfile = request.FILES['vac_certificate']
                medic.vac_certificate.save(request.user.username+"_"+myfile.name, myfile)
                medic.save()

            if "health_care_certificate" in request.FILES:
                myfile = request.FILES['health_care_certificate']
                medic.health_care_certificate.save(request.user.username+"_"+myfile.name, myfile)
                medic.save()

            if request.POST["delete_vac"] == 'vac':
                medic.vac_certificate.delete()
                medic.save()

            if request.POST["delete_health"] == 'health':
                medic.health_care_certificate.delete()
                medic.save()

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
        }

        return render(request, 'accounts/index.html', context)
    else:
        return render(request, 'client/index.html', context)
