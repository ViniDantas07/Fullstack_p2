from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Clinica, Consulta, Disponibilidade, Paciente, Vinculo


class CadastroForm(UserCreationForm):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email"]


class ClinicaForm(forms.ModelForm):
    class Meta:
        model = Clinica
        fields = ["nome", "endereco"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "endereco": forms.TextInput(attrs={"class": "form-control"}),
        }


class MembroForm(forms.Form):
    """Admin adiciona uma pessoa (que já tem conta) à equipe da clínica."""

    username = forms.CharField(
        label="Usuário", widget=forms.TextInput(attrs={"class": "form-control"})
    )
    papel = forms.ChoiceField(
        choices=Vinculo.PAPEL_CHOICES, widget=forms.Select(attrs={"class": "form-select"})
    )
    especialidade = forms.CharField(
        required=False, label="Especialidade (profissional)",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    telefone = forms.CharField(
        required=False, label="Telefone (paciente)",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    def clean(self):
        cleaned = super().clean()
        username = cleaned.get("username")
        if username:
            try:
                cleaned["usuario"] = User.objects.get(username=username)
            except User.DoesNotExist:
                self.add_error("username", "Usuário não encontrado. A pessoa precisa criar uma conta antes.")
        return cleaned


class DisponibilidadeForm(forms.ModelForm):
    class Meta:
        model = Disponibilidade
        fields = ["data", "hora_inicio", "hora_fim"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "hora_fim": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
        }


class ConsultaForm(forms.ModelForm):
    """Formulário do paciente (o paciente é o próprio usuário logado)."""

    class Meta:
        model = Consulta
        fields = ["data", "hora_inicio", "hora_fim", "observacoes"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "hora_fim": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class ConsultaStaffForm(ConsultaForm):
    """Formulário da recepção/admin: escolhe o paciente da clínica."""

    class Meta(ConsultaForm.Meta):
        fields = ["paciente", "data", "hora_inicio", "hora_fim", "observacoes"]
        widgets = {
            **ConsultaForm.Meta.widgets,
            "paciente": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, clinica=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["paciente"].queryset = Paciente.objects.filter(clinica=clinica).select_related("usuario")
