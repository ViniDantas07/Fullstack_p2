from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .dashboard import metricas_clinica
from .forms import (
    CadastroForm,
    ClinicaForm,
    ConsultaForm,
    ConsultaStaffForm,
    DisponibilidadeForm,
    MembroForm,
)
from .models import Clinica, Consulta, Disponibilidade, Paciente, Profissional, Vinculo
from .permissoes import (
    PAPEIS_GESTAO,
    SESSION_KEY,
    papel_requerido,
    pode_gerir_consulta,
    pode_realizar_consulta,
)


# ---------------------------------------------------------------- conta / clínica

def cadastro(request):
    if request.method == "POST":
        form = CadastroForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Conta criada! Agora escolha ou crie uma clínica.")
            return redirect("selecionar_clinica")
    else:
        form = CadastroForm()
    return render(request, "consultas/cadastro.html", {"form": form})


@login_required
def selecionar_clinica(request):
    vinculos = Vinculo.objects.filter(usuario=request.user).select_related("clinica")
    outras = Clinica.objects.exclude(id__in=[v.clinica_id for v in vinculos])
    return render(
        request,
        "consultas/selecionar_clinica.html",
        {"vinculos": vinculos, "outras_clinicas": outras},
    )


@login_required
@require_POST
def entrar_clinica(request, clinica_pk):
    vinculo = get_object_or_404(Vinculo, usuario=request.user, clinica_id=clinica_pk)
    request.session[SESSION_KEY] = vinculo.clinica_id
    return redirect("home")


@login_required
def clinica_create(request):
    if request.method == "POST":
        form = ClinicaForm(request.POST)
        if form.is_valid():
            clinica = form.save()
            clinica.adicionar_membro(request.user, Vinculo.ADMIN)
            request.session[SESSION_KEY] = clinica.pk
            messages.success(request, "Clínica criada! Você é o administrador dela.")
            return redirect("home")
    else:
        form = ClinicaForm()
    return render(request, "consultas/clinica_form.html", {"form": form})


@login_required
@require_POST
def clinica_ingressar(request, clinica_pk):
    """Entrar em uma clínica existente como paciente."""
    clinica = get_object_or_404(Clinica, pk=clinica_pk)
    try:
        clinica.adicionar_membro(request.user, Vinculo.PACIENTE)
    except ValidationError as erro:
        messages.error(request, erro.message)
        return redirect("selecionar_clinica")
    request.session[SESSION_KEY] = clinica.pk
    messages.success(request, f"Você agora é paciente da {clinica}.")
    return redirect("home")


# ---------------------------------------------------------------- home por papel

def _perfil_profissional(request):
    return get_object_or_404(Profissional, usuario=request.user, clinica=request.clinica)


def _perfil_paciente(request):
    return get_object_or_404(Paciente, usuario=request.user, clinica=request.clinica)


@papel_requerido()
def home(request):
    if request.papel in PAPEIS_GESTAO:
        return redirect("dashboard")

    if request.papel == Vinculo.PROFISSIONAL:
        perfil = _perfil_profissional(request)
        return render(
            request,
            "consultas/home_profissional.html",
            {
                "perfil": perfil,
                "disponibilidades": perfil.disponibilidades.all(),
                "consultas": perfil.consultas.exclude(status=Consulta.STATUS_CANCELADA).select_related("paciente__usuario"),
            },
        )

    perfil = _perfil_paciente(request)
    return render(
        request,
        "consultas/home_paciente.html",
        {
            "perfil": perfil,
            "consultas": perfil.consultas.exclude(status=Consulta.STATUS_CANCELADA).select_related("profissional__usuario"),
        },
    )


# ---------------------------------------------------------------- gestão (admin / recepção)

@papel_requerido(*PAPEIS_GESTAO)
def dashboard(request):
    hoje = timezone.localdate()
    proximas = (
        Consulta.objects.filter(
            profissional__clinica=request.clinica,
            status=Consulta.STATUS_AGENDADA,
            data__gte=hoje,
        )
        .select_related("paciente__usuario", "profissional__usuario")
        .order_by("data", "hora_inicio")[:8]
    )
    return render(
        request,
        "consultas/dashboard.html",
        {"m": metricas_clinica(request.clinica), "proximas": proximas},
    )


@papel_requerido(*PAPEIS_GESTAO)
def consulta_list(request):
    consultas = Consulta.objects.filter(profissional__clinica=request.clinica).select_related(
        "paciente__usuario", "profissional__usuario"
    )
    status = request.GET.get("status", "")
    if status in dict(Consulta.STATUS_CHOICES):
        consultas = consultas.filter(status=status)
    profissional = request.GET.get("profissional", "")
    if profissional.isdigit():
        consultas = consultas.filter(profissional_id=profissional)

    return render(
        request,
        "consultas/consulta_list.html",
        {
            "consultas": consultas,
            "profissionais": Profissional.objects.filter(clinica=request.clinica).select_related("usuario"),
            "status_choices": Consulta.STATUS_CHOICES,
            "filtro_status": status,
            "filtro_profissional": profissional,
        },
    )


@papel_requerido(Vinculo.ADMIN)
def equipe(request):
    if request.method == "POST":
        form = MembroForm(request.POST)
        if form.is_valid():
            try:
                request.clinica.adicionar_membro(
                    form.cleaned_data["usuario"],
                    form.cleaned_data["papel"],
                    especialidade=form.cleaned_data["especialidade"],
                    telefone=form.cleaned_data["telefone"],
                )
            except ValidationError as erro:
                form.add_error(None, erro.message)
            else:
                messages.success(request, "Membro adicionado à clínica.")
                return redirect("equipe")
    else:
        form = MembroForm()

    vinculos = (
        Vinculo.objects.filter(clinica=request.clinica)
        .select_related("usuario")
        .order_by("papel", "usuario__username")
    )
    return render(request, "consultas/equipe.html", {"vinculos": vinculos, "form": form})


@papel_requerido(Vinculo.ADMIN)
@require_POST
def membro_remover(request, pk):
    vinculo = get_object_or_404(Vinculo, pk=pk, clinica=request.clinica)

    if vinculo.papel == Vinculo.ADMIN:
        total_admins = Vinculo.objects.filter(clinica=request.clinica, papel=Vinculo.ADMIN).count()
        if total_admins <= 1:
            messages.error(request, "A clínica precisa ter pelo menos um administrador.")
            return redirect("equipe")

    perfil = None
    if vinculo.papel == Vinculo.PROFISSIONAL:
        perfil = Profissional.objects.filter(usuario=vinculo.usuario, clinica=request.clinica).first()
    elif vinculo.papel == Vinculo.PACIENTE:
        perfil = Paciente.objects.filter(usuario=vinculo.usuario, clinica=request.clinica).first()
    if perfil is not None:
        if perfil.consultas.exists():
            messages.error(request, "Não é possível remover: essa pessoa possui consultas registradas.")
            return redirect("equipe")
        perfil.delete()

    vinculo.delete()
    messages.success(request, "Membro removido da clínica.")
    if vinculo.usuario_id == request.user.id:
        request.session.pop(SESSION_KEY, None)
        return redirect("selecionar_clinica")
    return redirect("equipe")


# ---------------------------------------------------------------- disponibilidade (profissional)

@papel_requerido(Vinculo.PROFISSIONAL)
def disponibilidade_create(request):
    perfil = _perfil_profissional(request)
    if request.method == "POST":
        form = DisponibilidadeForm(request.POST, instance=Disponibilidade(profissional=perfil))
        if form.is_valid():
            form.save()
            messages.success(request, "Disponibilidade cadastrada!")
            return redirect("home")
    else:
        form = DisponibilidadeForm()
    return render(request, "consultas/disponibilidade_form.html", {"form": form})


@papel_requerido(Vinculo.PROFISSIONAL)
@require_POST
def disponibilidade_delete(request, pk):
    perfil = _perfil_profissional(request)
    disponibilidade = get_object_or_404(Disponibilidade, pk=pk, profissional=perfil)
    disponibilidade.delete()
    messages.success(request, "Disponibilidade removida.")
    return redirect("home")


# ---------------------------------------------------------------- consultas

@papel_requerido(Vinculo.PACIENTE, *PAPEIS_GESTAO)
def profissional_list(request):
    profissionais = Profissional.objects.filter(clinica=request.clinica).select_related("usuario")
    return render(request, "consultas/profissional_list.html", {"profissionais": profissionais})


@papel_requerido(Vinculo.PACIENTE, *PAPEIS_GESTAO)
def consulta_create(request, profissional_pk):
    profissional = get_object_or_404(Profissional, pk=profissional_pk, clinica=request.clinica)

    if request.papel == Vinculo.PACIENTE:
        instancia = Consulta(paciente=_perfil_paciente(request), profissional=profissional)
        form_class, extras = ConsultaForm, {}
    else:
        instancia = Consulta(profissional=profissional)
        form_class, extras = ConsultaStaffForm, {"clinica": request.clinica}

    if request.method == "POST":
        form = form_class(request.POST, instance=instancia, **extras)
        if form.is_valid():
            form.save()
            messages.success(request, "Consulta agendada com sucesso!")
            return redirect("home" if request.papel == Vinculo.PACIENTE else "consulta_list")
    else:
        form = form_class(instance=instancia, **extras)

    return render(
        request,
        "consultas/consulta_form.html",
        {"form": form, "profissional": profissional},
    )


def _voltar(request):
    return redirect("consulta_list" if request.papel in PAPEIS_GESTAO else "home")


@papel_requerido()
@require_POST
def consulta_cancelar(request, pk):
    consulta = get_object_or_404(
        Consulta.objects.select_related("paciente", "profissional"),
        pk=pk,
        profissional__clinica=request.clinica,
    )
    if not pode_gerir_consulta(request.papel, request.user, consulta):
        messages.error(request, "Você não pode cancelar esta consulta.")
    elif consulta.status != Consulta.STATUS_AGENDADA:
        messages.error(request, "Só é possível cancelar consultas agendadas.")
    else:
        consulta.cancelar()
        messages.info(request, "Consulta cancelada.")
    return _voltar(request)


@papel_requerido()
@require_POST
def consulta_realizar(request, pk):
    consulta = get_object_or_404(
        Consulta.objects.select_related("paciente", "profissional"),
        pk=pk,
        profissional__clinica=request.clinica,
    )
    if not pode_realizar_consulta(request.papel, request.user, consulta):
        messages.error(request, "Você não pode marcar esta consulta como realizada.")
    elif consulta.status != Consulta.STATUS_AGENDADA:
        messages.error(request, "Só consultas agendadas podem ser marcadas como realizadas.")
    else:
        consulta.marcar_realizada()
        messages.success(request, "Consulta marcada como realizada.")
    return _voltar(request)
