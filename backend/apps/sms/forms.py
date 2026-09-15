from django import forms


class SendSMSForm(forms.Form):
    username = forms.CharField(
        label="Nom d'utilisateur Jasmin",
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-input'})
    )
    recipient = forms.CharField(
        label="Destinataire (E.164)",
        max_length=20,
        widget=forms.TextInput(attrs={'placeholder': '+22890000000', 'class': 'form-input'})
    )
    message = forms.CharField(
        label="Message",
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-textarea'})
    )


class SMPPConnectorForm(forms.Form):
    cid = forms.CharField(
        label="Identifiant du connecteur (CID)",
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': 'ex: smpp_togocel', 'class': 'form-input'})
    )
    host = forms.CharField(
        label="Hôte / IP SMSC",
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': '192.168.1.100', 'class': 'form-input'})
    )
    port = forms.IntegerField(
        label="Port SMPP",
        initial=2775,
        widget=forms.NumberInput(attrs={'class': 'form-input'})
    )
    username = forms.CharField(
        label="System ID / Username",
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-input'})
    )
    system_type = forms.CharField(
        label="System Type (Optionnel)",
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'ex: SMS', 'class': 'form-input'})
    )


class GroupForm(forms.Form):
    gid = forms.CharField(
        label="Identifiant du Groupe (GID)",
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': 'ex: clients_vip', 'class': 'form-input'})
    )


class UserForm(forms.Form):
    uid = forms.CharField(
        label="Identifiant (UID)",
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': 'ex: user_01', 'class': 'form-input'})
    )
    gid = forms.CharField(
        label="Groupe (GID)",
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': 'ex: clients_vip', 'class': 'form-input'})
    )
    username = forms.CharField(
        label="Nom d'utilisateur SMS",
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-input'})
    )