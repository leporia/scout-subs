from django.shortcuts import render
from client.models import UserCode, Keys, DocumentType, Document, KeyVal
from django.contrib.auth.models import Group, Permission, User
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.db.models.deletion import ProtectedError

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
        data = []
        if request.method == "POST":
            parent_group = request.user.groups.values_list('name', flat=True)[
                0]
            group = Group.objects.get(name=parent_group)
            permission = Permission.objects.get(codename='approved')
            data = request.POST["codes"]
            data = "".join(data.split())
            data.replace("\r", "")
            data = data.split("\n")
            for i in range(len(data)):
                if not data[i].startswith("U"):
                    data[i] = data[i] + " - Formato errato"
                elif not data[i][1:].isdigit():
                    data[i] = data[i] + " - Formato errato"
                elif int(data[i][1:]) < 100000 or int(data[i][1:]) > 999999:
                    data[i] = data[i] + " - Formato errato"
                elif len(UserCode.objects.filter(code=data[i][1:])) == 0:
                    data[i] = data[i] + " - Invalido"
                else:
                    user = UserCode.objects.filter(code=data[i][1:])[0].user
                    if len(user.groups.values_list('name', flat=True)) == 0:
                        user.groups.add(group)
                        user.user_permissions.add(permission)
                        data[i] = data[i] + " - Ok"
                    else:
                        if user.groups.values_list('name', flat=True)[0] == parent_group:
                            user.user_permissions.add(permission)
                            data[i] = data[i] + " - Ok"
                        else:
                            user.groups.clear()
                            user.groups.add(group)
                            user.user_permissions.add(permission)
                            data[i] = data[i] + " - Ok, cambio branca"

        context = {
            'messages': data,
            'empty': len(data) == 0,
        }

        return render(request, 'server/approve_user.html', context)
    else:
        return render(request, 'client/index.html', context)


def docapprove(request):
    context = {}
    if (request.user.is_staff):
        data = []
        if request.method == "POST":
            data = request.POST["codes"]
            data = "".join(data.split())
            data.replace("\r", "")
            data = data.split("\n")
            for i in range(len(data)):
                if not data[i].isdigit():
                    data[i] = data[i] + " - Formato errato"
                elif int(data[i]) < 100000 or int(data[i]) > 999999:
                    data[i] = data[i] + " - Formato errato"
                elif len(Document.objects.filter(code=data[i])) == 0:
                    data[i] = data[i] + " - Invalido"
                else:
                    document = Document.objects.filter(code=data[i])[0]
                    if document.status == 'ok':
                        data[i] = data[i] + " - Gia` approvato"
                    else:
                        document.status = 'ok'
                        document.save()
                        data[i] = data[i] + " - Ok"

        context = {
            'messages': data,
            'empty': len(data) == 0,
        }

        return render(request, 'server/approve_doc.html', context)
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


def doctype(request):
    context = {}
    if request.user.is_staff:
        if request.method == "POST":
            selected = []
            for i in request.POST.keys():
                if i == "csrfmiddlewaretoken":
                    continue
                if i == "action":
                    continue

                selected.append(DocumentType.objects.get(id=i))

            for i in selected:
                if request.POST["action"] == 'delete':
                    try:
                        i.delete()
                    except ProtectedError:
                        print("nope")
                elif request.POST["action"] == 'hide':
                    i.enabled = not i.enabled
                    i.save()

        parent_group = request.user.groups.values_list('name', flat=True)[
            0]
        group = Group.objects.get(name=parent_group)
        public_types = DocumentType.objects.filter(
            Q(group_private=False) | Q(group=group))
        out = []
        for doc in public_types:
            custom_keys = Keys.objects.filter(container=doc)
            ref_docs = Document.objects.filter(document_type=doc)
            out.append([doc, custom_keys, len(ref_docs)])

        context = {'docs': out}
        return render(request, 'server/doc_type.html', context)
    else:
        return render(request, 'client/index.html', context)


def docedit(request):
    context = {}
    if request.user.is_staff:
        parent_group = request.user.groups.values_list('name', flat=True)[
            0]
        group = Group.objects.get(name=parent_group)
        enabled = False
        group_private = False
        personal_data = False
        medical_data = False
        custom_data = False
        name = ""

        enabled_check = ""
        private_check = 'checked="checked"'
        personal_check = 'checked="checked"'
        medical_check = ""
        custom_check = ""
        custom_message_check = ""
        context = {
            "enabled_check": enabled_check,
            "private_check": private_check,
            "personal_check": personal_check,
            "medical_check": medical_check,
            "custom_check": custom_check,
            "custom_message_check": custom_message_check,
        }
        if request.method == "POST":
            enabled = "enabled" in request.POST.keys()
            group_private = "group_private" in request.POST.keys()
            personal_data = "personal_data" in request.POST.keys()
            medical_data = "medical_data" in request.POST.keys()
            custom_data = "custom_data" in request.POST.keys()
            custom_message = "custom_message" in request.POST.keys()
            custom_message_text = request.POST["custom_message_text"]
            name = request.POST["name"]
            custom = request.POST["custom"]
            custom += " "
            custom = custom.split("\n")
            doctype = DocumentType(
                custom_message=custom_message, custom_message_text=custom_message_text, name=request.POST["name"], enabled=enabled, group_private=group_private, group=group, personal_data=personal_data, medical_data=medical_data, custom_data=custom_data)
            doctype.save()
            for i in custom:
                key = Keys(key=i[:-1], container=doctype)
                key.save()
            return HttpResponseRedirect('doctype')

        return render(request, 'server/doc_edit.html', context)
    else:
        return render(request, 'client/index.html', context)


def doclist(request):
    context = {}
    if request.user.is_staff:
        if request.method == "POST":
            selected = []
            for i in request.POST.keys():
                if i == "csrfmiddlewaretoken":
                    continue
                if i == "action":
                    continue

                selected.append(Document.objects.get(id=i))

            for i in selected:
                if request.POST["action"] == 'delete':
                    try:
                        i.delete()
                    except ProtectedError:
                        print("nope")
                elif request.POST["action"] == 'approve':
                    i.status = 'ok'
                    i.save()
                elif request.POST["action"] == 'archive':
                    i.status = 'archive'
                    i.save()

        parent_group = request.user.groups.values_list('name', flat=True)[
            0]
        group = Group.objects.get(name=parent_group)
        documents = Document.objects.filter(group=group)
        out = []
        for i in documents:
            custom_keys = KeyVal.objects.filter(container=i)
            out.append([i, custom_keys])
        context = {"docs": out}
        return render(request, 'server/doc_list.html', context)
    else:
        return render(request, 'client/index.html', context)
