# Specifications & Roadmap — Jasmin Web Platform

Ce document détaille l'architecture, le fonctionnement technique et la feuille de route pour la refonte et la finalisation de la plateforme **Jasmin Web**.

---

## 1. Vue d'Ensemble & Stack Technique

| Composant | Technologie / Protocole | Rôle & Port |
| :--- | :--- | :--- |
| **Backend** | Python 3.13 / Django 6.x | Logique métier, ORM, Webhooks, Authentification |
| **SMS Gateway** | Jasmin SMSGW | Moteur SMS (Port REST: `1401`, Port CLI/Telnet: `8990`) |
| **Base de Données** | SQLite / PostgreSQL | Stockage des logs d'envoi, utilisateurs, statuts DLR |
| **Frontend** | Django Templates / CSS | Formulaires d'envoi, tableaux de bord, gestion Jasmin |

---

## 2. Architecture des Applications Django (`apps/`)

* **`apps.accounts`** : Authentification et gestion des accès (Login, Logout, Rôles d'administration).
* **`apps.jasmin_config`** : Administration de la passerelle Jasmin via CLI/API.
  * *Vues* : `connectors_list`, `groups_list`, `users_list`.
  * *Actions* : Démarrage/arrêt/suppression des connecteurs SMPP, création de groupes/utilisateurs Jasmin.
* **`apps.sms`** : Moteur d'envoi et suivi des messages.
  * *Vues* : `dashboard`, `send_sms`, `sms_list`, `dlr_callback`.
  * *Service* : `SMSService` centralisant les appels HTTP vers le port REST `1401` de Jasmin.

---

## 3. Flux Critique : Envoi SMS & Rapports de Remise (DLR)

1. **Envoi HTTP** : Le backend effectue une requête `GET` ou `POST` vers `http://<JASMIN_HOST>:1401/send` avec les paramètres :
   * `username`, `password`, `to`, `content`
   * `dlr=yes`, `dlr-url=http://<DJANGO_HOST>/sms/dlr/`, `dlr-level=7`, `dlr-method=POST`
2. **Réception du DLR** : Jasmin notifie l'URL de callback (`/sms/dlr/`) à chaque changement de statut du message (DELIVRD, UNDELIV, REJECTD, etc.), déclenchant la mise à jour en base de données.

---

## 4. Feuille de Route & Instructions pour Claude Code

### Backend & Intégration API
- [ ] **Fiabilisation de `SMSService`** :
  - Sécuriser les appels vers l'API 1401 (gestion des timeouts, retries, parsing des réponses `ACK/MessageID`).
  - Corriger la signature de la méthode `send_sms` pour supporter dynamiquement les paramètres DLR (`dlr_url`, `dlr_level`, `dlr_method`).
- [ ] **Traitement du Callback DLR (`/sms/dlr/`)** :
  - Valider le parsing des données POST envoyées par Jasmin.
  - Automatiser la mise à jour des instances du modèle `SMSLog` en fonction du `message_id`.
- [ ] **Sécurisation de la Configuration** :
  - Centraliser toutes les variables d'environnement (`JASMIN_HOST`, `JASMIN_HTTP_PORT`, `JASMIN_JCLI_PORT`, `JASMIN_USERNAME`, `JASMIN_PASSWORD`) dans un fichier `.env` via `python-dotenv`.

### Frontend & Expérience Utilisateur
- [ ] **Refonte UI/UX** :
  - Harmoniser le design des templates avec une interface moderne et responsive (ex. Tailwind CSS).
  - Corriger et vérifier les résolutions de nommage d'URL (`namespace`) dans tous les templates (`jasmin_config:...`, `sms:...`).
- [ ] **Dashboard & Suivi** :
  - Ajouter des indicateurs de performance (taux de livraison, volume de SMS, échecs).
  - Ajouter des filtres et une pagination sur l'historique des SMS envoyés.

### Robustesse & Qualité
- [ ] Implémenter la gestion des exceptions et le retour d'information utilisateur via le framework `messages` de Django.
- [ ] Ajouter une suite de tests unitaires pour la validation des formulaires et le mock des requêtes HTTP vers Jasmin.
