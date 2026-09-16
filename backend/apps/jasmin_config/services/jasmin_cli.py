import logging
import socket
import time
from django.conf import settings

logger = logging.getLogger(__name__)


class JasminCLIError(Exception):
    """Exception personnalisée pour la communication CLI Jasmin."""
    pass


class JasminCLIClient:
    """Client Socket pour interroger et piloter la CLI de Jasmin Gateway (jcli - Port 8990)."""

    PROMPT_MAIN = b"jcli : "
    PROMPT_SUB = b"> "

    def __init__(self, host=None, port=None, username=None, password=None, timeout=None):
        self.host = host or getattr(settings, 'JASMIN_HOST', '192.168.1.70')
        self.port = int(port or getattr(settings, 'JASMIN_JCLI_PORT', 8990))
        self.username = username or getattr(settings, 'JASMIN_USERNAME', 'jcliadmin')
        self.password = password or getattr(settings, 'JASMIN_PASSWORD', 'jclipwd')
        self.timeout = int(timeout or getattr(settings, 'JASMIN_TIMEOUT', 30))

    def _read_until(self, sock, expected, buffer_size=4096) -> str:
        if isinstance(expected, bytes):
            expected = (expected,)

        output = b""
        start_time = time.time()
        while True:
            if time.time() - start_time > self.timeout:
                break
            try:
                chunk = sock.recv(buffer_size)
                if not chunk:
                    break
                output += chunk
                if any(exp in output for exp in expected):
                    break
            except socket.timeout:
                break

        return output.decode('utf-8', errors='ignore')

    def execute_command(self, command: str) -> str:
        sock = None
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)

            self._read_until(sock, b"Username: ")
            sock.sendall(f"{self.username}\n".encode('utf-8'))

            self._read_until(sock, b"Password: ")
            sock.sendall(f"{self.password}\n".encode('utf-8'))

            auth_res = self._read_until(sock, self.PROMPT_MAIN)
            if "Authentication failed" in auth_res or "Incorrect" in auth_res:
                raise JasminCLIError("Échec d'authentification sur Jasmin CLI (port 8990).")

            sock.sendall(f"{command}\n".encode('utf-8'))
            raw_response = self._read_until(sock, self.PROMPT_MAIN)

            sock.sendall(b"quit\n")

            lines = raw_response.splitlines()
            if len(lines) > 1:
                return "\n".join(lines[1:-1]).strip()
            return raw_response.strip()

        except (socket.error, socket.timeout) as e:
            logger.error(f"Erreur de connexion Jasmin jcli ({self.host}:{self.port}) : {e}")
            raise JasminCLIError(f"Erreur de connexion au port 8990 : {e}")
        finally:
            if sock:
                sock.close()

    # --- CONNECTEURS SMPP ---

    def create_smpp_connector(self, data: dict) -> bool:
        sock = None
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)

            self._read_until(sock, b"Username: ")
            sock.sendall(f"{self.username}\n".encode('utf-8'))

            self._read_until(sock, b"Password: ")
            sock.sendall(f"{self.password}\n".encode('utf-8'))

            auth_res = self._read_until(sock, self.PROMPT_MAIN)
            if "Authentication failed" in auth_res or "Incorrect" in auth_res:
                raise JasminCLIError("Échec d'authentification sur Jasmin CLI.")

            sock.sendall(b"smppcc -a\n")
            self._read_until(sock, (self.PROMPT_SUB, self.PROMPT_MAIN))

            sub_commands = [
                f"cid {data['cid']}",
                f"host {data['host']}",
                f"port {data['port']}",
                f"username {data['username']}",
                f"password {data['password']}",
            ]

            if data.get('system_type'):
                sub_commands.append(f"system_type {data['system_type']}")

            for cmd in sub_commands:
                sock.sendall(f"{cmd}\n".encode('utf-8'))
                res = self._read_until(sock, (self.PROMPT_SUB, self.PROMPT_MAIN))
                if "Error" in res or "Unknown" in res:
                    sock.sendall(b"cancel\n")
                    self._read_until(sock, self.PROMPT_MAIN)
                    sock.sendall(b"quit\n")
                    raise JasminCLIError(f"Erreur de configuration SMPP : {res.strip()}")

            sock.sendall(b"ok\n")
            res_ok = self._read_until(sock, self.PROMPT_MAIN)
            if "Error" in res_ok:
                raise JasminCLIError(f"Échec de la validation 'ok' : {res_ok.strip()}")

            sock.sendall(b"quit\n")
            return True

        except (socket.error, socket.timeout) as e:
            logger.error(f"Erreur création connecteur SMPP : {e}")
            raise JasminCLIError(f"Échec de communication jcli : {e}")
        finally:
            if sock:
                sock.close()

    def control_smpp_connector(self, cid: str, action: str) -> str:
        if action == 'start':
            cmd = f"smppcc -m {cid} -start"
        elif action == 'stop':
            cmd = f"smppcc -m {cid} -stop"
        elif action == 'delete':
            cmd = f"smppcc -r {cid}"
        else:
            raise ValueError(f"Action '{action}' non reconnue.")

        return self.execute_command(cmd)

    # --- GROUPES ---

    def create_group(self, gid: str) -> bool:
        sock = None
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            self._read_until(sock, b"Username: ")
            sock.sendall(f"{self.username}\n".encode('utf-8'))
            self._read_until(sock, b"Password: ")
            sock.sendall(f"{self.password}\n".encode('utf-8'))
            self._read_until(sock, self.PROMPT_MAIN)

            sock.sendall(b"group -a\n")
            self._read_until(sock, (self.PROMPT_SUB, self.PROMPT_MAIN))

            sock.sendall(f"gid {gid}\n".encode('utf-8'))
            self._read_until(sock, (self.PROMPT_SUB, self.PROMPT_MAIN))

            sock.sendall(b"ok\n")
            res_ok = self._read_until(sock, self.PROMPT_MAIN)
            if "Error" in res_ok:
                raise JasminCLIError(f"Erreur création groupe : {res_ok.strip()}")

            sock.sendall(b"quit\n")
            return True
        except (socket.error, socket.timeout) as e:
            raise JasminCLIError(f"Erreur de communication jcli : {e}")
        finally:
            if sock:
                sock.close()

    def delete_group(self, gid: str) -> str:
        return self.execute_command(f"group -r {gid}")

    def get_groups_list(self) -> list:
        # Colonne unique de `group -l` : Group id.
        return self._parse_table(self.execute_command("group -l"), ['gid'])

    # --- UTILISATEURS ---

    def create_user(self, data: dict) -> bool:
        sock = None
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            self._read_until(sock, b"Username: ")
            sock.sendall(f"{self.username}\n".encode('utf-8'))
            self._read_until(sock, b"Password: ")
            sock.sendall(f"{self.password}\n".encode('utf-8'))
            self._read_until(sock, self.PROMPT_MAIN)

            sock.sendall(b"user -a\n")
            self._read_until(sock, (self.PROMPT_SUB, self.PROMPT_MAIN))

            sub_commands = [
                f"uid {data['uid']}",
                f"gid {data['gid']}",
                f"username {data['username']}",
                f"password {data['password']}",
            ]

            for cmd in sub_commands:
                sock.sendall(f"{cmd}\n".encode('utf-8'))
                res = self._read_until(sock, (self.PROMPT_SUB, self.PROMPT_MAIN))
                if "Error" in res:
                    sock.sendall(b"cancel\n")
                    self._read_until(sock, self.PROMPT_MAIN)
                    sock.sendall(b"quit\n")
                    raise JasminCLIError(f"Erreur configuration utilisateur : {res.strip()}")

            sock.sendall(b"ok\n")
            res_ok = self._read_until(sock, self.PROMPT_MAIN)
            if "Error" in res_ok:
                raise JasminCLIError(f"Échec validation utilisateur : {res_ok.strip()}")

            sock.sendall(b"quit\n")
            return True
        except (socket.error, socket.timeout) as e:
            raise JasminCLIError(f"Erreur de communication jcli : {e}")
        finally:
            if sock:
                sock.close()

    def delete_user(self, uid: str) -> str:
        return self.execute_command(f"user -r {uid}")

    # --- STATUT GLOBAL & PARSERS ---

    def get_system_status(self) -> dict:
        result = {
            'connected': False,
            'smpp_connectors': [],
            'users': [],
            'stats': {
                'total_connectors': 0,
                'bound_connectors': 0,
                'total_users': 0,
            }
        }

        try:
            smpp_raw = self.execute_command("smppcc -l")
            result['smpp_connectors'] = self._parse_smppcc_list(smpp_raw)

            user_raw = self.execute_command("user -l")
            result['users'] = self._parse_user_list(user_raw)

            result['connected'] = True
            result['stats']['total_connectors'] = len(result['smpp_connectors'])
            result['stats']['bound_connectors'] = sum(
                1 for c in result['smpp_connectors']
                if 'BOUND' in c.get('session', '').upper() or 'BOUND' in c.get('status', '').upper()
            )
            result['stats']['total_users'] = len(result['users'])

        except Exception as e:
            logger.warning(f"Jasmin CLI 8990 injoignable : {e}")
            result['connected'] = False

        return result

    @staticmethod
    def _parse_table(raw_output: str, champs: list) -> list:
        """Découpe une table jcli en dictionnaires.

        jcli aligne ses colonnes sur une largeur fixe et préfixe chaque ligne
        d'un `#`, en-tête compris (`#Connector id  Service  Session  …`). Deux
        pièges en découlent :

        * l'en-tête doit être ignoré, sinon il devient une fausse entrée — et son
          libellé varie (`#Connector id`, `#User id`), donc on ne peut pas le
          reconnaître par son texte : c'est simplement la première ligne ;
        * les colonnes ne sont pas séparées par au moins deux espaces. Une valeur
          qui remplit sa colonne n'en laisse qu'un (`started BOUND_TRX`), ce qui
          fusionnerait deux champs. Les valeurs jcli ne contenant jamais
          d'espace, on découpe sur n'importe quelle suite d'espaces.
        """
        lignes = [l.strip() for l in raw_output.splitlines() if l.strip().startswith('#')]
        entrees = []
        for ligne in lignes[1:]:  # la première ligne est l'en-tête
            valeurs = ligne.lstrip('#').split()
            if not valeurs:
                continue
            entree = {nom: (valeurs[i] if i < len(valeurs) else 'N/A') for i, nom in enumerate(champs)}
            entrees.append(entree)
        return entrees

    def _parse_smppcc_list(self, raw_output: str) -> list:
        # Colonnes de `smppcc -l` : Connector id, Service, Session, Starts, Stops.
        connectors = self._parse_table(raw_output, ['cid', 'service', 'session', 'starts', 'stops'])
        for c in connectors:
            # jcli écrit ces valeurs en minuscules (`started`, `bound_trx`) : les
            # gabarits ne peuvent pas comparer la casse, on tranche ici.
            c['is_started'] = c['service'].lower() == 'started'
            c['is_bound'] = 'bound' in c['session'].lower()
            # `status` reste exposé pour compatibilité avec les gabarits existants.
            c['status'] = c['service']
        return connectors

    def _parse_user_list(self, raw_output: str) -> list:
        # Colonnes de `user -l` : User id, Group id, Username, Balance, MT SMS, Throughput.
        return self._parse_table(
            raw_output, ['uid', 'gid', 'username', 'balance', 'mt_sms', 'throughput']
        )