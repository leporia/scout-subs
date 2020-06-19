from django.shortcuts import render
from client.models import UserCode
from django.contrib.auth.models import Group, Permission, User

# Create your views here.


def index(request):
    context = {}
    if (request.user.is_staff):
        parent_group = request.user.groups.values_list('name', flat=True)[
            0]
        users = User.objects.filter(groups__name=parent_group)
        out = []
        for user in users:
            code = ""
            if len(UserCode.objects.filter(user=user)) > 0:
                code = 'U' + str(UserCode.objects.filter(user=user)[0].code)
            status = ""
            if user.is_staff:
                status = "Staff"
            elif user.has_perm("client.approved"):
                status = "Attivo"
            else:
                status = "In attesa"
            out.append([user.username, user.first_name,
                        user.last_name, code, status])
        context = {'users': out}
        return render(request, 'server/index.html', context)
    else:
        return render(request, 'client/index.html', context)


def uapprove(request):
    context = {}
    if (request.user.is_staff):
        if request.method == "POST":
            parent_group = request.user.groups.values_list('name', flat=True)[
                0]
            group = Group.objects.get(name=parent_group)
            permission = Permission.objects.get(codename='approved')
            data = request.POST["codes"]
            data += " "
            data = data.split("\n")
            for i in range(len(data)):
                if not data[i].startswith("U"):
                    data[i] = data[i] + " - Formato errato"
                elif not data[i][1:-1].isdigit():
                    data[i] = data[i] + " - Formato errato"
                elif int(data[i][1:-1]) < 100000 or int(data[i][1:-1]) > 999999:
                    data[i] = data[i] + " - Formato errato"
                elif len(UserCode.objects.filter(code=data[i][1:-1])) == 0:
                    data[i] = data[i] + " - Invalido"
                else:
                    user = UserCode.objects.filter(code=data[i][1:-1])[0].user
                    if len(user.groups.values_list('name', flat=True)) == 0:
                        user.groups.add(group)
                        user.user_permissions.add(permission)
                        data[i] = data[i] + " - Ok"
                    else:
                        if user.groups.values_list('name', flat=True)[0] == parent_group:
                            user.user_permissions.add(permission)
                            data[i] = data[i] + " - Gia` aggiunto"
                        else:
                            user.groups.clear()
                            user.groups.add(group)
                            user.user_permissions.add(permission)
                            data[i] = data[i] + " - Ok, cambio branca"

            context = {'messages': data}

        return render(request, 'server/approve_user.html', context)
    else:
        return render(request, 'client/index.html', context)


def ulist(request):
    context = {}
    if (request.user.is_staff):
        parent_group = request.user.groups.values_list('name', flat=True)[
            0]
        users = User.objects.filter(groups__name=parent_group)
        out = []
        for user in users:
            code = ""
            parent_name = ""
            via = ""
            cap = ""
            country = ""
            nationality = ""
            born_date = ""
            home_phone = ""
            phone = ""
            school = ""
            year = ""
            status = ""
            if user.is_staff:
                status = "Staff"
            elif user.has_perm("approved"):
                status = "Attivo"
            else:
                status = "In attesa"
            if len(UserCode.objects.filter(user=user)) > 0:
                usercode = UserCode.objects.filter(user=user)[0]
                code = 'U' + str(usercode.code)
                parent_name = usercode.parent_name
                via = usercode.via
                cap = usercode.cap
                country = usercode.country
                nationality = usercode.nationality
                born_date = usercode.born_date
                home_phone = usercode.home_phone
                phone = usercode.phone
                school = usercode.school
                year = usercode.year
            else:
                status = "Non registrato"
            out.append([
                status,
                user.username,
                user.first_name,
                user.last_name,
                born_date,
                parent_name,
                user.email,
                phone,
                home_phone,
                via,
                cap,
                country,
                nationality,
                school,
                year,
                code])
        context = {'users': out}
        return render(request, 'server/user_list.html', context)
    else:
        return render(request, 'client/index.html', context)
