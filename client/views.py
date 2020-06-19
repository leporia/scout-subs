from random import randint
from django.contrib.auth.models import Group, Permission, User
from client.models import UserCode, Keys, DocumentType, Document, PersonalData
from django.db.models import Q

from django.shortcuts import render

# Create your views here.


def index(request):
    context = {}
    if (request.user.is_authenticated):
        users = UserCode.objects.filter(user=request.user)
        code = None
        if (len(users) == 0):
            while (True):
                code = randint(100000, 999999)
                if len(UserCode.objects.filter(code=code)) == 0:
                    break
            userCode = UserCode(user=request.user, code=code)
            userCode.save()

        documents = Document.objects.filter(user=request.user)
        out = []
        for i in documents:
            out.append(i)
        context = {
            "docs": out,
            "empty": len(out) == 0,
        }
    return render(request, 'client/index.html', context)


def approve(request):
    context = {}
    if not (request.user.is_staff or request.user.has_perm('approved')):
        usercode = UserCode.objects.filter(user=request.user)[0]
        okay = False
        if request.user.first_name != "" and request.user.last_name != "" and request.user.email != "" and len(request.user.groups.values_list('name', flat=True)) != 0:
            okay = True
        context = {'code': 'U' + str(usercode.code), 'okay': okay}
        return render(request, 'client/approve.html', context)
    else:
        return render(request, 'client/index.html', context)


def create(request):
    context = {}
    if request.user.is_authenticated:
        parent_group = request.user.groups.values_list('name', flat=True)[
            0]
        group = Group.objects.get(name=parent_group)
        public_types = DocumentType.objects.filter(
            Q(group_private=False) | Q(group=group))
        out = []
        for doc in public_types:
            out.append(doc)

        context = {'docs': out}
        if request.method == "POST":
            usercode = UserCode.objects.filter(user=request.user)[0]
            code = 0
            status = 0
            document_type = DocumentType.objects.get(
                id=request.POST["doctype"])
            personal_data = PersonalData(parent_name=usercode.parent_name, via=usercode.via, cap=usercode.cap, country=usercode.country,
                                         nationality=usercode.nationality, born_date=usercode.born_date, home_phone=usercode.home_phone, phone=usercode.phone)
            personal_data.save()

            while (True):
                code = randint(100000, 999999)
                if len(Document.objects.filter(code=code)) == 0:
                    break

            document = Document(
                user=request.user, group=group, code=code, status=status, document_type=document_type, personal_data=personal_data)
            document.save()

        return render(request, 'client/doc_create.html', context)
    else:
        return render(request, 'client/index.html', context)
