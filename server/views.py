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
        users_out = []
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
            users_out.append([user.username, user.first_name,
                        user.last_name, code, status])

        parent_group = request.user.groups.values_list('name', flat=True)[
            0]
        group = Group.objects.get(name=parent_group)
        public_types = DocumentType.objects.filter(
            Q(group_private=False) | Q(group=group) & Q(enabled=True))
        docs = []
        for doc in public_types:
            ref_docs = Document.objects.filter(document_type=doc)
            docs.append([doc, len(ref_docs)])

        context = {
            'docs': docs,
            'users': users_out,
            }
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
                        data[i] = data[i] + " - Già approvato"
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
        error = False
        error_text = ""

        public = True
        selfsign = True
        hidden = False
        personal = True
        medic = True
        custom = True
        message = True
        public_check = 'checked="checked"'
        selfsign_check = 'checked="checked"'
        hidden_check = 'checked="checked"'
        personal_check = 'checked="checked"'
        medic_check = 'checked="checked"'
        custom_check = 'checked="checked"'
        message_check = 'checked="checked"'
        if request.method == "POST":
            selected = []
            for i in request.POST.keys():
                if i.isdigit():
                    selected.append(DocumentType.objects.get(id=i))

            for i in selected:
                if request.POST["action"] == 'delete':
                    try:
                        i.delete()
                    except ProtectedError:
                        error = True
                        error_text = "Non puoi eliminare un tipo a cui é collegato uno o piú documenti"
                elif request.POST["action"] == 'hide':
                    i.enabled = False
                    i.save()
                elif request.POST["action"] == 'show':
                    i.enabled = True
                    i.save()

            public = "filter_public" in request.POST
            selfsign = "filter_selfsign" in request.POST
            hidden = "filter_hidden" in request.POST
            personal = "filter_personal" in request.POST
            medic = "filter_medic" in request.POST
            custom = "filter_custom" in request.POST
            message = "filter_message" in request.POST

        parent_group = request.user.groups.values_list('name', flat=True)[
            0]
        group = Group.objects.get(name=parent_group)
        public_types = DocumentType.objects.filter(
            Q(group_private=False) | Q(group=group))
        if not public:
            public_types = public_types.filter(group_private=True)
            public_check = ""
        if not selfsign:
            public_types = public_types.filter(auto_sign=False)
            selfsign_check = ""
        if not hidden:
            public_types = public_types.filter(enabled=True)
            hidden_check = ""
        if not personal:
            public_types = public_types.filter(personal_data=False)
            personal_check = ""
        if not medic:
            public_types = public_types.filter(medical_data=False)
            medic_check = ""
        if not custom:
            public_types = public_types.filter(custom_data=False)
            custom_check = ""
        if not message:
            public_types = public_types.filter(custom_message=False)
            message_check = ""

        out = []
        for doc in public_types:
            custom_keys = Keys.objects.filter(container=doc)
            ref_docs = Document.objects.filter(document_type=doc)
            out.append([doc, custom_keys, len(ref_docs)])

        context = {
            'docs': out,
            'public_check': public_check,
            'selfsign_check': selfsign_check,
            'hidden_check': hidden_check,
            'personal_check': personal_check,
            'medic_check': medic_check,
            'custom_check': custom_check,
            'message_check': message_check,
            'error': error,
            'error_text': error_text,
            }
        return render(request, 'server/doc_type.html', context)
    else:
        return render(request, 'client/index.html', context)


def doccreate(request):
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

        enabled_check = 'checked="checked'
        private_check = 'checked="checked"'
        personal_check = 'checked="checked"'
        sign_check = 'checked="checked'
        medical_check = ""
        custom_check = ""
        custom_message_check = ""
        context = {
            "enabled_check": enabled_check,
            "private_check": private_check,
            "sign_check": sign_check,
            "personal_check": personal_check,
            "medical_check": medical_check,
            "custom_check": custom_check,
            "custom_message_check": custom_message_check,
        }
        if request.method == "POST":
            enabled = "enabled" in request.POST.keys()
            auto_sign = "sign" not in request.POST.keys()
            group_private = "group_private" in request.POST.keys()
            personal_data = "personal_data" in request.POST.keys()
            medical_data = "medical_data" in request.POST.keys()
            custom_data = "custom_data" in request.POST.keys()
            custom_message = "custom_message" in request.POST.keys()
            custom_message_text = request.POST["custom_message_text"]
            name = request.POST["name"]
            doctype = DocumentType(
                auto_sign=auto_sign, custom_message=custom_message, custom_message_text=custom_message_text, name=request.POST["name"], enabled=enabled, group_private=group_private, group=group, personal_data=personal_data, medical_data=medical_data, custom_data=custom_data)
            doctype.save()
            if custom_data:
                custom = request.POST["custom"]
                custom.replace("\r", "")
                custom = custom.split("\n")
                for i in custom:
                    key = Keys(key=i, container=doctype)
                    key.save()
            return HttpResponseRedirect('doctype')

        return render(request, 'server/doc_create.html', context)
    else:
        return render(request, 'client/index.html', context)


def doclist(request):
    context = {}
    if request.user.is_staff:
        error = False
        error_text = ""
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
                    i.delete()
                elif request.POST["action"] == 'approve':
                    i.status = 'ok'
                    i.save()
                elif request.POST["action"] == 'archive':
                    if i.status == 'ok':
                        i.status = 'archive'
                        i.save()
                    else:
                        error = True
                        error_text = "Non puoi archiviare un documento non approvato"
                elif request.POST["action"] == 'unarchive':
                    if i.status == 'archive':
                        i.status = 'ok'
                        i.save()
                    else:
                        error = True
                        error_text = "Non puoi dearchiviare un documento non archiviato"

        parent_group = request.user.groups.values_list('name', flat=True)[
            0]
        group = Group.objects.get(name=parent_group)
        documents = Document.objects.filter(group=group)
        out = []
        for i in documents:
            personal = None
            medical = None
            if i.document_type.personal_data:
                personal = i.personal_data.__dict__.values()
            if i.document_type.medical_data:
                medical = i.medical_data.__dict__.values()

            out.append([i, KeyVal.objects.filter(container=i), personal, medical])
        context = {
            "docs": out,
            'error': error,
            'error_text': error_text,
            }
        return render(request, 'server/doc_list.html', context)
    else:
        return render(request, 'client/index.html', context)
