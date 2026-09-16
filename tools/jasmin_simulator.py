"""Simulateur local de passerelle Jasmin, pour développer sans SMSC ni serveur Jasmin.

Reproduit les trois points de contact utilisés par le tableau de bord :

  * port 8990 — la console jcli (telnet), avec ses invites, son mode interactif
    d'ajout et le format de colonnes exact de `smppcc -l`, `user -l`, `group -l` ;
  * port 1401 — l'API HTTP `/send`, qui répond `Success "<uuid>"` puis rappelle
    l'URL de DLR de façon asynchrone, comme le ferait un vrai SMSC ;
  * port 5672 — un simple accepteur, pour que la sonde RabbitMQ voie le port ouvert.

Ce n'est pas Jasmin : aucun SMS ne part. Le but est de valider notre code contre
les formats que Jasmin produit réellement.

    python tools/jasmin_simulator.py

Les formats de sortie sont repris de la documentation jcli : colonnes séparées
par plusieurs espaces, lignes de données préfixées par `#`.
"""
import argparse
import re
import socket
import socketserver
import threading
import time
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = '127.0.0.1'

# --- État en mémoire, partagé entre les deux serveurs ---------------------------

ETAT = {
    'connectors': [
        # cid, service, session, starts, stops
        {'cid': 'smpp_gabtel', 'service': 'started', 'session': 'BOUND_TRX', 'starts': 1, 'stops': 0},
        {'cid': 'smpp_airtel', 'service': 'stopped', 'session': 'NONE', 'starts': 0, 'stops': 1},
    ],
    'users': [
        {'uid': 'bgfi_otp', 'gid': 'otp', 'username': 'otp_sender', 'balance': 'ND'},
        {'uid': 'bgfi_sms', 'gid': 'marketing', 'username': 'sms_sender', 'balance': '1500'},
    ],
    'groups': [{'gid': 'otp'}, {'gid': 'marketing'}],
}
VERROU = threading.Lock()


# --- Console jcli (port 8990) --------------------------------------------------

def table_connectors():
    lignes = ["#Connector id                        Service Session               Starts Stops"]
    for c in ETAT['connectors']:
        lignes.append(
            f"#{c['cid']:<36}{c['service']:<8}{c['session']:<22}{c['starts']:<7}{c['stops']}"
        )
    lignes.append(f"Total connectors: {len(ETAT['connectors'])}")
    return lignes


def table_users():
    lignes = ["#User id          Group id         Username         Balance MT SMS Throughput"]
    for u in ETAT['users']:
        lignes.append(
            f"#{u['uid']:<17}{u['gid']:<17}{u['username']:<17}{u['balance']:<8}{'ND':<7}{'ND/ND'}"
        )
    lignes.append(f"Total Users: {len(ETAT['users'])}")
    return lignes


def table_groups():
    lignes = ["#Group id"]
    for g in ETAT['groups']:
        lignes.append(f"#{g['gid']}")
    lignes.append(f"Total Groups: {len(ETAT['groups'])}")
    return lignes


class JCLIHandler(socketserver.BaseRequestHandler):
    """Reproduit la séquence d'authentification et l'invite `jcli : `."""

    PROMPT = "jcli : "
    SOUS_PROMPT = "> "

    def envoyer(self, texte):
        self.request.sendall(texte.encode('utf-8'))

    def lire_ligne(self):
        tampon = b""
        while not tampon.endswith(b"\n"):
            morceau = self.request.recv(1024)
            if not morceau:
                return None
            tampon += morceau
        return tampon.decode('utf-8', errors='ignore').strip()

    def handle(self):
        self.request.settimeout(30)
        try:
            self.envoyer("Authentication required.\n\nUsername: ")
            if self.lire_ligne() is None:
                return
            self.envoyer("Password: ")
            if self.lire_ligne() is None:
                return
            self.envoyer(f"\nWelcome to Jasmin {uuid.uuid4().hex[:6]} console\nType help or ? to list commands.\n\n{self.PROMPT}")

            while True:
                commande = self.lire_ligne()
                if commande is None or commande == 'quit':
                    return
                self.traiter(commande)
        except (socket.timeout, OSError):
            return

    def traiter(self, commande):
        """Répond à une commande. L'écho puis l'invite encadrent la sortie,
        exactement comme jcli : le client s'appuie dessus pour découper la réponse."""
        if commande in ('smppcc -a', 'user -a', 'group -a'):
            self.mode_interactif(commande)
            return

        with VERROU:
            sortie = self.sortie_pour(commande)
        self.envoyer(commande + "\n" + "\n".join(sortie) + "\n" + self.PROMPT)

    def sortie_pour(self, commande):
        if commande == 'smppcc -l':
            return table_connectors()
        if commande == 'user -l':
            return table_users()
        if commande == 'group -l':
            return table_groups()

        m = re.match(r'smppcc -m (\S+) -(start|stop)$', commande)
        if m:
            cid, action = m.groups()
            for c in ETAT['connectors']:
                if c['cid'] == cid:
                    c['service'] = 'started' if action == 'start' else 'stopped'
                    c['session'] = 'BOUND_TRX' if action == 'start' else 'NONE'
                    c['starts' if action == 'start' else 'stops'] += 1
                    return [f"Successfully {action}ed connector id:{cid}"]
            return [f"Unknown connector: {cid}"]

        for motif, cle, champ in [(r'smppcc -r (\S+)$', 'connectors', 'cid'),
                                  (r'user -r (\S+)$', 'users', 'uid'),
                                  (r'group -r (\S+)$', 'groups', 'gid')]:
            m = re.match(motif, commande)
            if m:
                ident = m.group(1)
                avant = len(ETAT[cle])
                ETAT[cle] = [x for x in ETAT[cle] if x[champ] != ident]
                if len(ETAT[cle]) < avant:
                    return [f"Successfully removed {champ}:{ident}"]
                return [f"Unknown {champ}: {ident}"]

        return [f"Unknown command: {commande}"]

    def mode_interactif(self, commande):
        """Mode d'ajout : chaque clé saisie renvoie une sous-invite, `ok` valide."""
        self.envoyer(commande + "\n" + self.SOUS_PROMPT)
        champs = {}
        while True:
            ligne = self.lire_ligne()
            if ligne is None:
                return
            if ligne == 'cancel':
                self.envoyer("cancel\n" + self.PROMPT)
                return
            if ligne == 'ok':
                with VERROU:
                    message = self.valider(commande, champs)
                self.envoyer("ok\n" + message + "\n" + self.PROMPT)
                return
            cle, _, valeur = ligne.partition(' ')
            champs[cle] = valeur
            self.envoyer(ligne + "\n" + self.SOUS_PROMPT)

    def valider(self, commande, champs):
        if commande == 'smppcc -a':
            if not champs.get('cid'):
                return "Error: cid is mandatory."
            ETAT['connectors'].append({
                'cid': champs['cid'], 'service': 'stopped', 'session': 'NONE',
                'starts': 0, 'stops': 0,
            })
            return f"Successfully added connector [{champs['cid']}]"
        if commande == 'user -a':
            if not champs.get('uid') or not champs.get('gid'):
                return "Error: uid and gid are mandatory."
            ETAT['users'].append({
                'uid': champs['uid'], 'gid': champs['gid'],
                'username': champs.get('username', ''), 'balance': 'ND',
            })
            return f"Successfully added User [{champs['uid']}]"
        if commande == 'group -a':
            if not champs.get('gid'):
                return "Error: gid is mandatory."
            ETAT['groups'].append({'gid': champs['gid']})
            return f"Successfully added Group [{champs['gid']}]"
        return "Error: unknown object."


class JCLIServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


# --- API HTTP /send (port 1401) ------------------------------------------------

ENVOIS = []


class HTTPHandler(BaseHTTPRequestHandler):
    def _params(self):
        if self.command == 'POST':
            corps = self.rfile.read(int(self.headers.get('Content-Length', 0))).decode()
            return dict(urllib.parse.parse_qsl(corps))
        return dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))

    def _repondre(self, code, corps):
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(corps.encode())

    def do_GET(self):
        self.do_POST()

    def do_POST(self):
        if not urllib.parse.urlparse(self.path).path.startswith('/send'):
            self._repondre(404, 'Error "Not found"')
            return

        p = self._params()
        if not p.get('username') or not p.get('password'):
            self._repondre(403, 'Error "Authentication failure"')
            return
        if not p.get('to'):
            self._repondre(400, 'Error "Argument [to] is missing"')
            return

        msg_id = str(uuid.uuid4())
        ENVOIS.append({'id': msg_id, 'to': p.get('to'), 'content': p.get('content')})
        print(f"  [1401] envoi accepté pour {p.get('to')} -> {msg_id}")
        self._repondre(200, f'Success "{msg_id}"')

        if p.get('dlr') == 'yes' and p.get('dlr-url'):
            threading.Thread(
                target=self.livrer_dlr,
                args=(p['dlr-url'], msg_id, p.get('dlr-level', '1'), p.get('dlr-method', 'POST')),
                daemon=True,
            ).start()

    @staticmethod
    def livrer_dlr(url, msg_id, niveau, methode):
        """Rejoue la séquence d'un vrai SMSC : accusé de soumission puis de remise."""
        etapes = []
        if niveau in ('1', '3'):
            etapes.append(('ESME_ROK', '1'))
        if niveau in ('2', '3'):
            etapes.append(('DELIVRD', '2'))

        for statut, lvl in etapes:
            time.sleep(1.0)
            donnees = urllib.parse.urlencode({
                'id': msg_id, 'message_status': statut, 'level': lvl,
                'donedate': time.strftime('%y%m%d%H%M'), 'sub': '001', 'dlvrd': '001',
            }).encode()
            try:
                requete = urllib.request.Request(url, data=donnees, method=methode)
                with urllib.request.urlopen(requete, timeout=5) as r:
                    print(f"  [DLR] {msg_id[:8]}… {statut} -> {url} : HTTP {r.status}")
            except Exception as e:
                print(f"  [DLR] échec vers {url} : {e}")

    def log_message(self, *a):
        pass


# --- Accepteur AMQP factice (port 5672) ----------------------------------------

def accepteur(port):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, port))
    s.listen(5)
    while True:
        try:
            conn, _ = s.accept()
            conn.close()
        except OSError:
            return


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--jcli-port', type=int, default=8990)
    ap.add_argument('--http-port', type=int, default=1401)
    ap.add_argument('--amqp-port', type=int, default=5672)
    args = ap.parse_args()

    jcli = JCLIServer((HOST, args.jcli_port), JCLIHandler)
    threading.Thread(target=jcli.serve_forever, daemon=True).start()
    http = HTTPServer((HOST, args.http_port), HTTPHandler)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    threading.Thread(target=accepteur, args=(args.amqp_port,), daemon=True).start()

    print(f"Simulateur Jasmin en écoute sur {HOST} :")
    print(f"  jcli   {args.jcli_port}")
    print(f"  HTTP   {args.http_port}")
    print(f"  AMQP   {args.amqp_port} (accepteur seul)")
    print("Ctrl+C pour arrêter.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
