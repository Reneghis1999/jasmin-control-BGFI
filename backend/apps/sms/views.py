import logging
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.urls import reverse  # ✅ Importation de reverse

from .models import SMSLog
from .forms import SendSMSForm
from .services.sms_service import SMSService, SMSServiceError
from .services.stats import FAILED_STATUSES, get_daily_series, get_dashboard_stats
from apps.jasmin_config.services.jasmin_cli import JasminCLIClient
from apps.jasmin_config.services.health import get_services_health

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """Tableau de bord principal affichant l'état du système Jasmin."""
    health = get_services_health()

    # La CLI ouvre une session telnet authentifiée par commande. Inutile de payer
    # ce coût si la sonde vient de constater que le port est fermé.
    if health['jcli']['up']:
        jasmin_status = JasminCLIClient().get_system_status()
    else:
        jasmin_status = {'connected': False, 'smpp_connectors': [], 'users': [], 'stats': {}}

    context = {
        'jasmin_connected': jasmin_status.get('connected', False),
        'smpp_connectors': jasmin_status.get('smpp_connectors', []),
        'users_list': jasmin_status.get('users', []),
        'stats': jasmin_status.get('stats', {}),
        'services': health,
        'kpi': get_dashboard_stats(),
        'recent_logs': SMSLog.objects.all()[:5],
        'daily': get_daily_series(14),
    }
    return render(request, 'sms/dashboard.html', context)


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
@require_POST
def dlr_callback(request):
    """Webhook DLR appelé par Jasmin.

    Jasmin notifie deux niveaux d'accusé : l'acquittement du SMSC (`level` 1,
    `message_status` de la forme `ESME_ROK`) puis l'accusé de remise final
    (`level` 2, `DELIVRD`, `UNDELIV`…). Seul le second change réellement le sort
    du message ; écraser le statut avec un acquittement SMSC ferait régresser un
    message déjà marqué comme livré.
    """
    msg_id = request.POST.get('id')
    raw_status = request.POST.get('message_status')

    if not msg_id or not raw_status:
        logger.warning(f"DLR incomplet reçu : {dict(request.POST)}")
        return HttpResponse("Paramètres DLR manquants", status=400)

    try:
        sms_log = SMSLog.objects.get(msg_id=msg_id)
    except SMSLog.DoesNotExist:
        logger.warning(f"DLR reçu pour un message inconnu : {msg_id}")
        return HttpResponse("Message non trouvé", status=404)

    status = raw_status.strip().upper()
    known_statuses = dict(SMSLog.STATUS_CHOICES)

    sms_log.stat_code = status
    if status in known_statuses:
        sms_log.status = status
    elif status.startswith('ESME_'):
        # Acquittement de soumission : le message est parti, la remise reste à confirmer.
        if sms_log.status == 'PENDING':
            sms_log.status = 'SENT'
    else:
        # Statut inattendu : on le conserve dans stat_code pour diagnostic sans
        # corrompre le champ `status`, contraint par STATUS_CHOICES.
        logger.warning(f"DLR {msg_id} : statut non reconnu '{status}', conservé en stat_code.")

    sms_log.save(update_fields=['status', 'stat_code', 'updated_at'])
    logger.info(f"DLR {msg_id} : {raw_status} -> statut {sms_log.status}")
    return HttpResponse("ACK/Jasmin", status=200)


@login_required
def sms_list(request):
    """Historique des envois, filtrable et paginé."""
    logs = SMSLog.objects.all()

    # Les compteurs portent sur la totalité de l'historique, pas sur la page
    # affichée : ils doivent rester stables quand on navigue ou qu'on filtre.
    totals = SMSLog.objects.aggregate(
        total_sent=Count('id'),
        total_delivered=Count('id', filter=Q(status='DELIVRD')),
        total_failed=Count('id', filter=Q(status__in=FAILED_STATUSES)),
    )

    status = request.GET.get('status', '').strip()
    query = request.GET.get('q', '').strip()

    if status in dict(SMSLog.STATUS_CHOICES):
        logs = logs.filter(status=status)
    if query:
        logs = logs.filter(
            Q(recipient__icontains=query)
            | Q(message__icontains=query)
            | Q(msg_id__icontains=query)
            | Q(sender_id__icontains=query)
        )

    paginator = Paginator(logs, 25)
    page = paginator.get_page(request.GET.get('page'))

    # Conserve les filtres actifs dans les liens de pagination.
    params = request.GET.copy()
    params.pop('page', None)

    context = {
        'logs': page.object_list,
        'page_obj': page,
        'paginator': paginator,
        'filter_status': status,
        'filter_query': query,
        'status_choices': SMSLog.STATUS_CHOICES,
        'querystring': params.urlencode(),
        'result_count': paginator.count,
        'is_filtered': bool(status or query),
        **totals,
    }
    return render(request, 'sms/sms_list.html', context)