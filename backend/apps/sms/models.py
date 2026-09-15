from django.db import models


class SMSLog(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'En attente'),
        ('SENT', 'Transmis à Jasmin'),
        ('DELIVRD', 'Livré au destinataire'),
        ('UNDELIV', 'Non livré'),
        ('REJECTD', 'Rejeté'),
        ('EXPIRED', 'Expiré'),
        ('FAILED', 'Échec'),
    ]

    msg_id = models.CharField(max_length=64, unique=True, verbose_name="ID Message Jasmin")
    recipient = models.CharField(max_length=20, verbose_name="Destinataire")
    message = models.TextField(verbose_name="Contenu")
    sender_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="Expéditeur")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="Statut")
    stat_code = models.CharField(max_length=30, blank=True, null=True, verbose_name="Code Jasmin DLR")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Historique SMS"
        verbose_name_plural = "Historiques SMS"

    def __str__(self):
        return f"[{self.status}] -> {self.recipient} (ID: {self.msg_id})"