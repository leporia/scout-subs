from random import randint

from django.shortcuts import render

from .models import UserCode

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
