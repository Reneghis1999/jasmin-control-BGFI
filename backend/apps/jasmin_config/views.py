from django.shortcuts import render, redirect
from django.contrib import messages

def connectors_list(request):
    return render(request, 'jasmin_config/connectors_list.html')

def connector_action(request, cid, action):
    # Logique d'action sur le connecteur (start, stop, delete)
    messages.success(request, f"Action '{action}' effectuée sur le connecteur {cid}.")
    return redirect('jasmin_config:connectors_list')

def groups_list(request):
    return render(request, 'jasmin_config/groups_list.html')

def group_action(request, gid, action):
    # Logique d'action sur le groupe (ex: delete)
    messages.success(request, f"Action '{action}' effectuée sur le groupe {gid}.")
    return redirect('jasmin_config:groups_list')

def users_list(request):
    return render(request, 'jasmin_config/users_list.html')

def user_action(request, uid, action):
    # Logique d'action sur l'utilisateur (ex: delete)
    messages.success(request, f"Action '{action}' effectuée sur l'utilisateur {uid}.")
    return redirect('jasmin_config:users_list')