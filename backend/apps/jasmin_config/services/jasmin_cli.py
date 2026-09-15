import logging
import re
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
        raw = self.execute_command("group -l")
        groups = []
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("#") and not line.startswith("#Gid"):
                parts = re.split(r'\s{2,}', line)
                if parts:
                    gid = parts[0].replace('#', '').strip()
                    groups.append({'gid': gid})
        return groups

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

    def _parse_smppcc_list(self, raw_output: str) -> list:
        connectors = []
        for line in raw_output.splitlines():
            line = line.strip()
            if line.startswith("#") and not line.startswith("#Cid"):
                parts = re.split(r'\s{2,}', line)
                if len(parts) >= 3:
                    cid = parts[0].replace('#', '').strip()
                    service = parts[1].strip() if len(parts) > 1 else 'N/A'
                    status = parts[2].strip() if len(parts) > 2 else 'UNKNOWN'
                    session = parts[3].strip() if len(parts) > 3 else 'N/A'
                    connectors.append({
                        'cid': cid,
                        'service': service,
                        'status': status,
                        'session': session
                    })
        return connectors

    def _parse_user_list(self, raw_output: str) -> list:
        users = []
        for line in raw_output.splitlines():
            line = line.strip()
            if line.startswith("#") and not line.startswith("#Uid"):
                parts = re.split(r'\s{2,}', line)
                if len(parts) >= 2:
                    uid = parts[0].replace('#', '').strip()
                    gid = parts[1].strip() if len(parts) > 1 else 'N/A'
                    balance = parts[2].strip() if len(parts) > 2 else 'N/A'
                    users.append({
                        'uid': uid,
                        'gid': gid,
                        'balance': balance
                    })
        return users