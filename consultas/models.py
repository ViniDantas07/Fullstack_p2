from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction


def nome_usuario(usuario):
    return usuario.get_full_name() or usuario.username


class Clinica(models.Model):
    nome = models.CharField(max_length=150)
    endereco = models.CharField(max_length=200, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    @transaction.atomic
    def adicionar_membro(self, usuario, papel, especialidade="", telefone=""):
        """
        Vincula um usuário à clínica com um papel. Se o papel for profissional
        ou paciente, cria também o perfil correspondente (usado por
        disponibilidades e consultas).
        """
        vinculo, criado = Vinculo.objects.get_or_create(
            usuario=usuario, clinica=self, defaults={"papel": papel}
        )
        if not criado:
            raise ValidationError("Este usuário já faz parte da clínica.")
        if papel == Vinculo.PROFISSIONAL:
            Profissional.objects.create(usuario=usuario, clinica=self, especialidade=especialidade)
        elif papel == Vinculo.PACIENTE:
            Paciente.objects.create(usuario=usuario, clinica=self, telefone=telefone)
        return vinculo


class Vinculo(models.Model):
    """Papel de um usuário dentro de uma clínica (pode ser diferente em cada clínica)."""

    ADMIN = "admin"
    RECEPCAO = "recepcao"
    PROFISSIONAL = "profissional"
    PACIENTE = "paciente"
    PAPEL_CHOICES = [
        (ADMIN, "Administrador"),
        (RECEPCAO, "Recepção"),
        (PROFISSIONAL, "Profissional"),
        (PACIENTE, "Paciente"),
    ]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vinculos")
    clinica = models.ForeignKey(Clinica, on_delete=models.CASCADE, related_name="vinculos")
    papel = models.CharField(max_length=20, choices=PAPEL_CHOICES)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("usuario", "clinica")
        ordering = ["clinica__nome", "papel"]

    def __str__(self):
        return f"{nome_usuario(self.usuario)} — {self.get_papel_display()} em {self.clinica}"


class Profissional(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfis_profissional")
    clinica = models.ForeignKey(Clinica, on_delete=models.CASCADE, related_name="profissionais")
    especialidade = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ("usuario", "clinica")
        verbose_name_plural = "profissionais"

    def __str__(self):
        nome = nome_usuario(self.usuario)
        return f"{nome} ({self.especialidade})" if self.especialidade else nome


class Paciente(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfis_paciente")
    clinica = models.ForeignKey(Clinica, on_delete=models.CASCADE, related_name="pacientes")
    telefone = models.CharField(max_length=30, blank=True)

    class Meta:
        unique_together = ("usuario", "clinica")

    def __str__(self):
        return nome_usuario(self.usuario)


class Disponibilidade(models.Model):
    """Bloco de horário em que o profissional aceita marcações."""

    profissional = models.ForeignKey(Profissional, on_delete=models.CASCADE, related_name="disponibilidades")
    data = models.DateField()
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()

    class Meta:
        ordering = ["data", "hora_inicio"]
        verbose_name_plural = "disponibilidades"

    def __str__(self):
        return f"{self.data} {self.hora_inicio}–{self.hora_fim}"

    def clean(self):
        if self.hora_inicio and self.hora_fim and self.hora_inicio >= self.hora_fim:
            raise ValidationError("O horário de início deve ser antes do horário de término.")


class Consulta(models.Model):
    STATUS_AGENDADA = "agendada"
    STATUS_CANCELADA = "cancelada"
    STATUS_REALIZADA = "realizada"
    STATUS_CHOICES = [
        (STATUS_AGENDADA, "Agendada"),
        (STATUS_CANCELADA, "Cancelada"),
        (STATUS_REALIZADA, "Realizada"),
    ]

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="consultas")
    profissional = models.ForeignKey(Profissional, on_delete=models.CASCADE, related_name="consultas")
    data = models.DateField()
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()
    observacoes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AGENDADA)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["data", "hora_inicio"]

    def __str__(self):
        return f"{self.paciente} com {self.profissional} em {self.data} {self.hora_inicio}"

    @property
    def clinica(self):
        return self.profissional.clinica

    def clean(self):
        """
        Regra do P1 (mantida): o horário precisa estar dentro de uma
        disponibilidade do profissional e não pode conflitar com outra consulta.
        Regra nova do P2: paciente e profissional precisam ser da mesma clínica.
        """
        if self.profissional_id and self.paciente_id:
            if self.paciente.clinica_id != self.profissional.clinica_id:
                raise ValidationError("Paciente e profissional precisam ser da mesma clínica.")

        if not (self.data and self.hora_inicio and self.hora_fim and self.profissional_id):
            return

        if self.hora_inicio >= self.hora_fim:
            raise ValidationError("O horário de início deve ser antes do horário de término.")

        dentro_da_disponibilidade = self.profissional.disponibilidades.filter(
            data=self.data,
            hora_inicio__lte=self.hora_inicio,
            hora_fim__gte=self.hora_fim,
        ).exists()
        if not dentro_da_disponibilidade:
            raise ValidationError(
                "O profissional não tem disponibilidade cadastrada para esse dia/horário."
            )

        conflitos = (
            Consulta.objects.filter(
                profissional=self.profissional,
                data=self.data,
                status=self.STATUS_AGENDADA,
            )
            .exclude(pk=self.pk)
            .filter(hora_inicio__lt=self.hora_fim, hora_fim__gt=self.hora_inicio)
        )
        if conflitos.exists():
            raise ValidationError(
                "Já existe uma consulta marcada para este profissional nesse horário."
            )

    def cancelar(self):
        self.status = self.STATUS_CANCELADA
        self.save()

    def marcar_realizada(self):
        self.status = self.STATUS_REALIZADA
        self.save()
