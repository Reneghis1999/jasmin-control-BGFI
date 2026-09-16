import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Réponses de l'API HTTP de Jasmin :
#   succès -> HTTP 200, corps `Success "07033084-5cfd-4812-90a4-e4d24ffb6e3d"`
#   échec  -> HTTP 4xx, corps `Error "No route found"`
SUCCESS_RE = re.compile(r'Success\s+"([^"]+)"', re.IGNORECASE)
ERROR_RE = re.compile(r'Error\s+"([^"]+)"', re.IGNORECASE)


class SMSServiceError(Exception):
    """Exception personnalisée pour l'échec d'envoi de SMS."""
    pass


class SMSService:
    """Service gérant l'émission de SMS via l'interface HTTP de Jasmin Gateway."""

    # Nombre total de tentatives sur erreur réseau (la première incluse).
    MAX_ATTEMPTS = 3

    def __init__(self):
        self.host = getattr(settings, 'JASMIN_HOST', '127.0.0.1')
        self.port = getattr(settings, 'JASMIN_HTTP_PORT', 1401)
        self.timeout = getattr(settings, 'JASMIN_TIMEOUT', 30)
        self.endpoint = f"http://{self.host}:{self.port}/send"

    @staticmethod
    def parse_response(body: str) -> str:
        """Extrait l'identifiant de message d'une réponse Jasmin.

        Jasmin encadre l'identifiant de guillemets : le renvoyer brut ferait
        échouer plus tard la correspondance avec le `id` reçu dans le DLR.
        """
        match = SUCCESS_RE.search(body)
        if match:
            return match.group(1)

        error = ERROR_RE.search(body)
        raise SMSServiceError(error.group(1) if error else f"Réponse inattendue : {body.strip()[:200]}")

    def send_sms(
        self,
        username: str,
        password: str,
        recipient: str,
        message: str,
        dlr_url: str | None = None,
        dlr_level: int = 3,
        dlr_method: str = 'POST',
        sender_id: str | None = None,
    ) -> str:
        """Transmet un SMS à Jasmin et retourne l'identifiant de message.

        `dlr_level` 3 demande les accusés de réception intermédiaires *et*
        finaux, ce qui permet de suivre le message jusqu'à la remise.
        """
        payload = {
            'username': username,
            'password': password,
            'to': recipient,
            'content': message,
        }

        if dlr_url:
            payload.update({
                'dlr': 'yes',
                'dlr-url': dlr_url,
                'dlr-level': dlr_level,
                'dlr-method': dlr_method,
            })

        if sender_id:
            payload['from'] = sender_id

        last_error = None
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                response = requests.post(self.endpoint, data=payload, timeout=self.timeout)
            except requests.RequestException as e:
                # Erreur réseau : l'envoi n'a probablement pas atteint Jasmin, on réessaie.
                last_error = e
                logger.warning(
                    f"Tentative {attempt}/{self.MAX_ATTEMPTS} vers {self.endpoint} échouée : {e}"
                )
                continue

            body = response.text or ''
            if response.status_code == 200:
                msg_id = self.parse_response(body)
                logger.info(f"SMS accepté par Jasmin pour {recipient} (id={msg_id})")
                return msg_id

            # Jasmin a répondu : le message a été refusé, pas la peine de réessayer.
            error = ERROR_RE.search(body)
            detail = error.group(1) if error else body.strip()[:200]
            logger.error(f"Refus Jasmin ({response.status_code}) : {detail}")
            raise SMSServiceError(f"Jasmin a refusé l'envoi ({response.status_code}) : {detail}")

        raise SMSServiceError(
            f"Serveur Jasmin injoignable sur {self.host}:{self.port} "
            f"après {self.MAX_ATTEMPTS} tentatives ({last_error})."
        )
