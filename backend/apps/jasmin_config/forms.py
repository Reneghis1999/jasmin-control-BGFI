"""Formulaires d'administration de la passerelle Jasmin.

Les valeurs saisies ici sont transmises à la CLI jcli, qui interprète le saut de
ligne comme un séparateur de commandes : `CLICommandField` refuse donc tout
caractère de contrôle, faute de quoi un champ pourrait injecter des commandes
arbitraires dans la session telnet.
"""
import re

from django import forms

INVALID_CHARS_RE = re.compile(r'[\r\n\x00-\x1f\x7f]')


class CLICommandField(forms.CharField):
    """Champ texte dont la valeur est sûre à concaténer dans une commande jcli."""

    def validate(self, value):
        super().validate(value)
        if value and INVALID_CHARS_RE.search(value):
            raise forms.ValidationError("Ce champ ne peut pas contenir de saut de ligne ou de caractère de contrôle.")


class SMPPConnectorForm(forms.Form):
    cid = CLICommandField(
        label="Identifiant du connecteur (CID)",
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': 'ex: smpp_togocel', 'class': 'form-input'})
    )
    host = CLICommandField(
        label="Hôte / IP SMSC",
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': '192.168.1.100', 'class': 'form-input'})
    )
    port = forms.IntegerField(
        label="Port SMPP",
        initial=2775,
        min_value=1,
        max_value=65535,
        widget=forms.NumberInput(attrs={'class': 'form-input'})
    )
    username = CLICommandField(
        label="System ID / Username",
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )
    password = CLICommandField(
        label="Mot de passe",
        max_length=50,
        widget=forms.PasswordInput(attrs={'class': 'form-input'})
    )
    system_type = CLICommandField(
        label="System Type (Optionnel)",
        required=False,
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': 'ex: SMS', 'class': 'form-input'})
    )


class GroupForm(forms.Form):
    gid = CLICommandField(
        label="Identifiant du Groupe (GID)",
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': 'ex: clients_vip', 'class': 'form-input'})
    )


class UserForm(forms.Form):
    uid = CLICommandField(
        label="Identifiant (UID)",
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': 'ex: user_01', 'class': 'form-input'})
    )
    gid = CLICommandField(
        label="Groupe (GID)",
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': 'ex: clients_vip', 'class': 'form-input'})
    )
    username = CLICommandField(
        label="Nom d'utilisateur SMS",
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )
    password = CLICommandField(
        label="Mot de passe",
        max_length=50,
        widget=forms.PasswordInput(attrs={'class': 'form-input'})
    )
