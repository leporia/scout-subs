from django.shortcuts import render
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy
from django.views import generic
from django.contrib.auth.models import Group

from client.models import UserCode

import dateparser


class SignUp(generic.CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy('login')
    template_name = 'accounts/signup.html'


def personal(request):
    context = {}
    if request.user.is_authenticated:
        usercode = UserCode.objects.filter(user=request.user)[0]
        debug = ""
        branca_default = ""
        branca_castorini = ""
        branca_lupetti = ""
        branca_esploratori = ""
        branca_pionieri = ""
        branca_rover = ""

        if request.method == "POST":
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

            if request.POST["branca"] != "":
                request.user.groups.clear()
                request.user.groups.add(
                    Group.objects.get(name=request.POST["branca"]))

        if len(request.user.groups.values_list('name', flat=True)) == 0:
            branca_default = "selected"
        else:
            parent_group = request.user.groups.values_list('name', flat=True)[
                0]
            if parent_group == "muta":
                branca_lupetti = "selected"
            elif parent_group == "reparto":
                branca_esploratori = "selected"
            else:
                branca_default = "selected"

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
        }

        return render(request, 'accounts/index.html', context)
    else:
        return render(request, 'client/index.html', context)
