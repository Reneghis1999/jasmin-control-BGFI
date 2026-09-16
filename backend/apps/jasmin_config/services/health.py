"""Sondes d'état des services de la passerelle Jasmin.

Les vérifications sont de simples ouvertures de socket TCP : pas d'authentification,
pas de commande envoyée. C'est volontairement léger, le dashboard étant rafraîchi
à chaque chargement de page.
"""
import logging
import socket
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Durée de mise en cache du résultat des sondes (secondes).
HEALTH_CACHE_TTL = 15

# Délai d'attente par sonde. Volontairement court : un port injoignable ne doit
# pas retarder l'affichage de la page.
PROBE_TIMEOUT = 1.5

CACHE_KEY = 'jasmin:services_health'


def probe_port(host: str, port: int, timeout: float = PROBE_TIMEOUT) -> bool:
    """Retourne True si le port TCP accepte une connexion."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError as e:
        logger.debug(f"Sonde {host}:{port} injoignable : {e}")
        return False


def get_services_health(use_cache: bool = True) -> dict:
    """État des trois services dont dépend la passerelle.

    Les sondes sont lancées en parallèle : le temps total est celui de la plus
    lente, pas leur somme.
    """
    if use_cache:
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return cached

    host = getattr(settings, 'JASMIN_HOST', '127.0.0.1')
    services = [
        ('jcli', "Jasmin CLI (jcli)", int(getattr(settings, 'JASMIN_JCLI_PORT', 8990))),
        ('http', "Rest API (HTTP)", int(getattr(settings, 'JASMIN_HTTP_PORT', 1401))),
        ('amqp', "RabbitMQ Broker", int(getattr(settings, 'JASMIN_AMQP_PORT', 5672))),
    ]

    with ThreadPoolExecutor(max_workers=len(services)) as pool:
        results = list(pool.map(lambda s: probe_port(host, s[2]), services))

    health = {
        key: {'label': label, 'port': port, 'up': up}
        for (key, label, port), up in zip(services, results)
    }

    if use_cache:
        cache.set(CACHE_KEY, health, HEALTH_CACHE_TTL)
    return health
