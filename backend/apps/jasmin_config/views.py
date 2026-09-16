import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import GroupForm, SMPPConnectorForm, UserForm
from .services.health import get_services_health
from .services.jasmin_cli import JasminCLIClient, JasminCLIError

logger = logging.getLogger(__name__)


def _cli_status():
    """État de la passerelle, sans ouvrir de session telnet si le port est fermé."""
    if not get_services_health()['jcli']['up']:
        return {'connected': False, 'smpp_connectors': [], 'users': [], 'stats': {}}
    return JasminCLIClient().get_system_status()


# --- CONNECTEURS SMPP ---

@login_required
def connectors_list(request):
    """Liste et création des connecteurs SMPP."""
    if request.method == 'POST':
        form = SMPPConnectorForm(request.POST)
        if form.is_valid():
            try:
                JasminCLIClient().create_smpp_connector(form.cleaned_data)
                messages.success(request, f"Connecteur « {form.cleaned_data['cid']} » créé avec succès.")
                return redirect('jasmin_config:connectors_list')
            except JasminCLIError as e:
                messages.error(request, f"Échec de création du connecteur : {e}")
    else:
        form = SMPPConnectorForm()

    status = _cli_status()
    return render(request, 'jasmin_config/connectors_list.html', {
        'connectors': status.get('smpp_connectors', []),
        'jasmin_connected': status.get('connected', False),
        'form': form,
    })


@login_required
@require_POST
def connector_action(request, cid: str, action: str):
    """Contrôle d'un connecteur SMPP (start, stop, delete)."""
    try:
        res = JasminCLIClient().control_smpp_connector(cid, action)
        messages.success(request, f"Action « {action} » exécutée sur #{cid} : {res}")
    except (JasminCLIError, ValueError) as e:
        messages.error(request, f"Erreur lors de l'action « {action} » sur #{cid} : {e}")

    return redirect('jasmin_config:connectors_list')


# --- GROUPES ---

@login_required
def groups_list(request):
    """Liste et création des groupes d'utilisateurs."""
    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            try:
                JasminCLIClient().create_group(form.cleaned_data['gid'])
                messages.success(request, f"Groupe « {form.cleaned_data['gid']} » créé avec succès.")
                return redirect('jasmin_config:groups_list')
            except JasminCLIError as e:
                messages.error(request, f"Échec de création du groupe : {e}")
    else:
        form = GroupForm()

    status = _cli_status()
    groups = []
    if status.get('connected'):
        try:
            groups = JasminCLIClient().get_groups_list()
        except JasminCLIError as e:
            messages.error(request, f"Impossible de lister les groupes : {e}")

    return render(request, 'jasmin_config/groups_list.html', {
        'groups': groups,
        'jasmin_connected': status.get('connected', False),
        'form': form,
    })


@login_required
@require_POST
def group_action(request, gid: str, action: str):
    """Actions sur un groupe (suppression)."""
    if action != 'delete':
        messages.error(request, f"Action « {action} » non reconnue pour un groupe.")
        return redirect('jasmin_config:groups_list')

    try:
        res = JasminCLIClient().delete_group(gid)
        messages.success(request, f"Groupe #{gid} supprimé : {res}")
    except JasminCLIError as e:
        messages.error(request, f"Erreur lors de la suppression du groupe #{gid} : {e}")

    return redirect('jasmin_config:groups_list')


# --- UTILISATEURS ---

@login_required
def users_list(request):
    """Liste et création des utilisateurs Jasmin."""
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            try:
                JasminCLIClient().create_user(form.cleaned_data)
                messages.success(request, f"Utilisateur « {form.cleaned_data['uid']} » créé avec succès.")
                return redirect('jasmin_config:users_list')
            except JasminCLIError as e:
                messages.error(request, f"Échec de création de l'utilisateur : {e}")
    else:
        form = UserForm()

    status = _cli_status()
    return render(request, 'jasmin_config/users_list.html', {
        'users': status.get('users', []),
        'jasmin_connected': status.get('connected', False),
        'total_users': status.get('stats', {}).get('total_users', 0),
        'form': form,
    })


@login_required
@require_POST
def user_action(request, uid: str, action: str):
    """Actions sur un utilisateur (suppression)."""
    if action != 'delete':
        messages.error(request, f"Action « {action} » non reconnue pour un utilisateur.")
        return redirect('jasmin_config:users_list')

    try:
        res = JasminCLIClient().delete_user(uid)
        messages.success(request, f"Utilisateur #{uid} supprimé : {res}")
    except JasminCLIError as e:
        messages.error(request, f"Erreur lors de la suppression de l'utilisateur #{uid} : {e}")

    return redirect('jasmin_config:users_list')
