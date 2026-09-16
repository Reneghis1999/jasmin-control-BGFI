"""Contexte injecté dans toutes les pages.

Le bandeau supérieur affiche l'état de la passerelle : il doit donc être
disponible partout, pas seulement sur le tableau de bord.
"""
from django.conf import settings

from .services.health import get_services_health


def jasmin_health(request):
    """Expose l'état des services Jasmin et l'hôte configuré.

    S'appuie sur le cache court de `get_services_health`, ce qui évite de
    sonder les ports à chaque rendu de page.
    """
    health = get_services_health()
    return {
        'services': health,
        'jasmin_cli_up': health['jcli']['up'],
        'jasmin_host': getattr(settings, 'JASMIN_HOST', ''),
    }
