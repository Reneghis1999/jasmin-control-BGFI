import logging
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse  # ✅ Importation de reverse

from .models import SMSLog
from .forms import SendSMSForm, SMPPConnectorForm, GroupForm, UserForm
from .services.sms_service import SMSService, SMSServiceError
from apps.jasmin_config.services.jasmin_cli import JasminCLIClient, JasminCLIError

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """Tableau de bord principal affichant l'état du système Jasmin."""
    cli_client = JasminCLIClient()
    jasmin_status = cli_client.get_system_status()

    context = {
        'jasmin_connected': jasmin_status.get('connected', False),
        'smpp_connectors': jasmin_status.get('smpp_connectors', []),
        'users_list': jasmin_status.get('users', []),
        'stats': jasmin_status.get('stats', {}),
    }
    return render(request, 'sms/dashboard.html', context)


# --- GESTION DES CONNECTEURS SMPP ---

@login_required
def connectors_list(request):
    """Liste et création des connecteurs SMPP."""
    cli = JasminCLIClient()

    if request.method == 'POST':
        form = SMPPConnectorForm(request.POST)
        if form.is_valid():
            try:
                cli.create_smpp_connector(form.cleaned_data)
                messages.success(request, f"Connecteur '{form.cleaned_data['cid']}' créé avec succès.")
                return redirect('sms:connectors_list')
            except JasminCLIError as e:
                messages.error(request, f"Échec de création du connecteur : {e}")
    else:
        form = SMPPConnectorForm()

    status = cli.get_system_status()
    context = {
        'connectors': status.get('smpp_connectors', []),
        'jasmin_connected': status.get('connected', False),
        'form': form,
    }
    return render(request, 'jasmin_config/connectors_list.html', context)


@login_required
def connector_action(request, cid: str, action: str):
    """Contrôle d'un connecteur SMPP (start, stop, delete)."""
    cli = JasminCLIClient()
    try:
        res = cli.control_smpp_connector(cid, action)
        messages.success(request, f"Action '{action}' exécutée sur #{cid} : {res}")
    except (JasminCLIError, ValueError) as e:
        messages.error(request, f"Erreur lors de l'action '{action}' sur #{cid} : {e}")

    return redirect('sms:connectors_list')


# --- GESTION DES GROUPES ---

@login_required
def groups_list(request):
    """Liste et création des groupes d'utilisateurs."""
    cli = JasminCLIClient()

    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            try:
                cli.create_group(form.cleaned_data['gid'])
                messages.success(request, f"Groupe '{form.cleaned_data['gid']}' créé avec succès.")
                return redirect('sms:groups_list')
            except JasminCLIError as e:
                messages.error(request, f"Échec de création du groupe : {e}")
    else:
        form = GroupForm()

    status = cli.get_system_status()
    groups = cli.get_groups_list()

    context = {
        'groups': groups,
        'jasmin_connected': status.get('connected', False),
        'form': form,
    }
    return render(request, 'jasmin_config/groups_list.html', context)


@login_required
def group_action(request, gid: str, action: str):
    """Actions sur un groupe (ex: suppression)."""
    cli = JasminCLIClient()
    if action == 'delete':
        try:
            res = cli.delete_group(gid)
            messages.success(request, f"Groupe #{gid} supprimé : {res}")
        except JasminCLIError as e:
            messages.error(request, f"Erreur lors de la suppression du groupe #{gid} : {e}")

    return redirect('sms:groups_list')


# --- GESTION DES UTILISATEURS ---

@login_required
def users_list(request):
    """Liste et création des utilisateurs Jasmin."""
    cli = JasminCLIClient()

    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            try:
                cli.create_user(form.cleaned_data)
                messages.success(request, f"Utilisateur '{form.cleaned_data['uid']}' créé avec succès.")
                return redirect('sms:users_list')
            except JasminCLIError as e:
                messages.error(request, f"Échec de création de l'utilisateur : {e}")
    else:
        form = UserForm()

    status = cli.get_system_status()
    context = {
        'users': status.get('users', []),
        'jasmin_connected': status.get('connected', False),
        'total_users': status.get('stats', {}).get('total_users', 0),
        'form': form,
    }
    return render(request, 'jasmin_config/users_list.html', context)


@login_required
def user_action(request, uid: str, action: str):
    """Actions sur un utilisateur (ex: suppression)."""
    cli = JasminCLIClient()
    if action == 'delete':
        try:
            res = cli.delete_user(uid)
            messages.success(request, f"Utilisateur #{uid} supprimé : {res}")
        except JasminCLIError as e:
            messages.error(request, f"Erreur lors de la suppression de l'utilisateur #{uid} : {e}")

    return redirect('sms:users_list')


# --- ENVOI, CALLBACK DLR ET HISTORIQUE ---

@login_required
def send_sms(request):
    """Envoi de SMS via Jasmin et enregistrement initial du log."""
    if request.method == 'POST':
        form = SendSMSForm(request.POST)
        if form.is_valid():
            sms_service = SMSService()
            
            # ✅ URL dynamique de Callback générée via reverse()
            dlr_url = request.build_absolute_uri(reverse('sms:dlr_callback'))
            
            try:
                msg_id = sms_service.send_sms(
                    username=form.cleaned_data['username'],
                    password=form.cleaned_data['password'],
                    recipient=form.cleaned_data['recipient'],
                    message=form.cleaned_data['message'],
                    dlr_url=dlr_url
                )

                SMSLog.objects.create(
                    msg_id=msg_id,
                    recipient=form.cleaned_data['recipient'],
                    message=form.cleaned_data['message'],
                    sender_id=form.cleaned_data.get('username'),
                    status='SENT'
                )

                messages.success(request, f"SMS transmis à Jasmin (ACK: {msg_id})")
                return redirect('sms:sms_list')

            except SMSServiceError as e:
                messages.error(request, f"Erreur lors de l'envoi : {e}")
    else:
        form = SendSMSForm()

    return render(request, 'sms/send_sms.html', {'form': form})


@csrf_exempt
def dlr_callback(request):
    """Webhook DLR appelé par Jasmin."""
    msg_id = request.GET.get('id') or request.POST.get('id')
    message_status = request.GET.get('message_status') or request.POST.get('message_status')

    if msg_id and message_status:
        try:
            sms_log = SMSLog.objects.get(msg_id=msg_id)
            sms_log.status = message_status.upper()
            sms_log.stat_code = message_status
            sms_log.save()
            logger.info(f"DLR reçu pour {msg_id}: nouveau statut -> {message_status}")
            return HttpResponse("ACK/Jasmin", status=200)
        except SMSLog.DoesNotExist:
            logger.warning(f"DLR reçu pour un message inconnu : {msg_id}")
            return HttpResponse("Message non trouvé", status=404)

    return HttpResponse("Paramètres DLR manquants", status=400)


@login_required
def sms_list(request):
    """Affichage du tableau de bord d'historique et des statistiques DLR."""
    logs = SMSLog.objects.all()

    total_sent = logs.count()
    total_delivered = logs.filter(status='DELIVRD').count()
    total_failed = logs.filter(status__in=['UNDELIV', 'REJECTD', 'FAILED']).count()

    context = {
        'logs': logs,
        'total_sent': total_sent,
        'total_delivered': total_delivered,
        'total_failed': total_failed,
    }
    return render(request, 'sms/sms_list.html', context)