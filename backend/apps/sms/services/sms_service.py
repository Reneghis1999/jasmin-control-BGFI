import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class SMSServiceError(Exception):
    """Exception personnalisée pour l'échec d'envoi de SMS."""
    pass

class SMSService:
    """Service gérant l'émission de SMS via l'interface HTTP GET de Jasmin Gateway."""

    def __init__(self):
        self.host = getattr(settings, 'JASMIN_HOST', '192.168.1.69')
        self.port = getattr(settings, 'JASMIN_HTTP_PORT', 1401)
        self.timeout = getattr(settings, 'JASMIN_TIMEOUT', 30)
        self.endpoint = f"http://{self.host}:{self.port}/send"

    def send_sms(self, username: str, password: str, recipient: str, message: str) -> str:
        """
        Envoie une requête GET vers Jasmin avec les paramètres :
        username, password, to, text.
        """
        payload = {
            'username': username,
            'password': password,
            'to': recipient,
            'text': message,
        }

        try:
            response = requests.get(self.endpoint, params=payload, timeout=self.timeout)
            
            if response.status_code == 200 and "ACK" in response.text:
                msg_id = response.text.strip()
                logger.info(f"SMS envoyé à {recipient} par {username} - Reponse: {msg_id}")
                return msg_id
            else:
                logger.error(f"Échec Jasmin ({response.status_code}): {response.text}")
                raise SMSServiceError(f"Réponse Jasmin ({response.status_code}): {response.text}")

        except requests.RequestException as e:
            logger.error(f"Erreur réseau vers {self.endpoint}: {e}")
            raise SMSServiceError(f"Erreur de connexion au serveur Jasmin: {e}")