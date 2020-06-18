from random import randint

from django.shortcuts import render

from .models import UserCode

# Create your views here.


def index(request):
    context = {}
    return render(request, 'client/index.html', context)


def approve(request):
    context = {}
    if not (request.user.is_staff or request.user.has_perm('approved')):
        users = UserCode.objects.filter(user=request.user)
        code = None
        if (len(users) == 0):
            while (True):
                code = randint(100000, 999999)
                if len(UserCode.objects.filter(code=code)) == 0:
                    break
            userCode = UserCode(user=request.user, code=code)
            userCode.save()
        else:
            code = UserCode.objects.filter(user=request.user)[0].code
        context = {'code': 'U' + str(code), }
        return render(request, 'client/approve.html', context)
    else:
        return render(request, 'client/index.html', context)
