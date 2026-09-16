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
