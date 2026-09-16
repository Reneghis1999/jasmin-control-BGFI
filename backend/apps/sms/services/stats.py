"""Agrégats du journal d'envoi alimentant les indicateurs du tableau de bord."""
from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.sms.models import SMSLog

# Statuts considérés comme un échec définitif de remise.
FAILED_STATUSES = ['UNDELIV', 'REJECTD', 'EXPIRED', 'FAILED']

# Statuts en attente d'un accusé de réception : ils ne comptent ni en succès
# ni en échec tant que le DLR n'est pas revenu.
PENDING_STATUSES = ['PENDING', 'SENT']


def _month_bounds(reference=None):
    """Retourne (début du mois courant, début du mois précédent)."""
    now = reference or timezone.localtime()
    start_current = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_previous = (start_current - timedelta(days=1)).replace(day=1)
    return start_current, start_previous


def get_daily_series(days: int = 14) -> list:
    """Volume quotidien des `days` derniers jours, du plus ancien au plus récent.

    Les jours sans envoi sont renvoyés à zéro : les omettre tasserait l'axe du
    graphe et laisserait croire à une activité continue.
    """
    today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    start = today - timedelta(days=days - 1)

    rows = (
        SMSLog.objects.filter(created_at__gte=start)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(
            total=Count('id'),
            delivered=Count('id', filter=Q(status='DELIVRD')),
            failed=Count('id', filter=Q(status__in=FAILED_STATUSES)),
        )
    )
    by_day = {r['day']: r for r in rows}

    series = []
    for offset in range(days):
        day = (start + timedelta(days=offset)).date()
        row = by_day.get(day, {})
        series.append({
            'date': day,
            'total': row.get('total', 0),
            'delivered': row.get('delivered', 0),
            'failed': row.get('failed', 0),
        })

    peak = max((d['total'] for d in series), default=0)
    for d in series:
        # Hauteur en pourcentage, calculée côté serveur pour garder le gabarit simple.
        d['height'] = round(d['total'] / peak * 100) if peak else 0
    return series


def get_dashboard_stats() -> dict:
    """Indicateurs affichés en haut du tableau de bord.

    Le taux de délivrance est calculé sur les seuls messages ayant reçu un DLR
    définitif ; inclure les messages encore en attente ferait mécaniquement
    chuter le taux sans que rien n'aille mal.
    """
    start_current, start_previous = _month_bounds()

    month = SMSLog.objects.filter(created_at__gte=start_current).aggregate(
        total=Count('id'),
        delivered=Count('id', filter=Q(status='DELIVRD')),
        failed=Count('id', filter=Q(status__in=FAILED_STATUSES)),
        pending=Count('id', filter=Q(status__in=PENDING_STATUSES)),
    )
    previous_total = SMSLog.objects.filter(
        created_at__gte=start_previous, created_at__lt=start_current
    ).count()

    # Base du taux de délivrance : messages dont le sort est connu.
    resolved = month['delivered'] + month['failed']
    delivery_rate = round(month['delivered'] / resolved * 100, 1) if resolved else None
    failure_rate = round(month['failed'] / resolved * 100, 2) if resolved else None

    if previous_total:
        month_delta = round((month['total'] - previous_total) / previous_total * 100, 1)
    else:
        # Pas d'historique le mois précédent : afficher une évolution serait trompeur.
        month_delta = None

    return {
        'sent_month': month['total'],
        'delivered_month': month['delivered'],
        'failed_month': month['failed'],
        'pending_month': month['pending'],
        'previous_month': previous_total,
        'month_delta': month_delta,
        'delivery_rate': delivery_rate,
        'failure_rate': failure_rate,
        'resolved_month': resolved,
        'total_all_time': SMSLog.objects.count(),
    }
