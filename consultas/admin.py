from django.contrib import admin

from .models import Clinica, Consulta, Disponibilidade, Paciente, Profissional, Vinculo


@admin.register(Clinica)
class ClinicaAdmin(admin.ModelAdmin):
    list_display = ("nome", "endereco", "criada_em")


@admin.register(Vinculo)
class VinculoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "clinica", "papel")
    list_filter = ("clinica", "papel")


@admin.register(Profissional)
class ProfissionalAdmin(admin.ModelAdmin):
    list_display = ("usuario", "clinica", "especialidade")
    list_filter = ("clinica",)


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ("usuario", "clinica", "telefone")
    list_filter = ("clinica",)


@admin.register(Disponibilidade)
class DisponibilidadeAdmin(admin.ModelAdmin):
    list_display = ("profissional", "data", "hora_inicio", "hora_fim")
    list_filter = ("profissional__clinica", "profissional")


@admin.register(Consulta)
class ConsultaAdmin(admin.ModelAdmin):
    list_display = ("paciente", "profissional", "data", "hora_inicio", "hora_fim", "status")
    list_filter = ("status", "profissional__clinica", "profissional")
