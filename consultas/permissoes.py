from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import Vinculo

SESSION_KEY = "clinica_id"

# Papéis que gerenciam a clínica inteira
PAPEIS_GESTAO = (Vinculo.ADMIN, Vinculo.RECEPCAO)


def vinculo_ativo(request):
    """Vínculo (usuário + clínica + papel) da clínica selecionada na sessão."""
    if hasattr(request, "_vinculo_cache"):
        return request._vinculo_cache
    vinculo = None
    if request.user.is_authenticated:
        clinica_id = request.session.get(SESSION_KEY)
        if clinica_id:
            vinculo = (
                Vinculo.objects.select_related("clinica")
                .filter(usuario=request.user, clinica_id=clinica_id)
                .first()
            )
    request._vinculo_cache = vinculo
    return vinculo


def papel_requerido(*papeis):
    """
    Exige login, uma clínica ativa e (se informado) um dos papéis listados.
    Injeta request.vinculo, request.clinica e request.papel na view.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            vinculo = vinculo_ativo(request)
            if vinculo is None:
                return redirect("selecionar_clinica")
            if papeis and vinculo.papel not in papeis:
                messages.error(request, "Seu papel nesta clínica não permite acessar essa página.")
                return redirect("home")
            request.vinculo = vinculo
            request.clinica = vinculo.clinica
            request.papel = vinculo.papel
            return view(request, *args, **kwargs)

        return login_required(wrapper)

    return decorator


def pode_gerir_consulta(papel, usuario, consulta):
    """Quem pode cancelar uma consulta (usado na web e na API)."""
    if papel in PAPEIS_GESTAO:
        return True
    if papel == Vinculo.PROFISSIONAL:
        return consulta.profissional.usuario_id == usuario.id
    if papel == Vinculo.PACIENTE:
        return consulta.paciente.usuario_id == usuario.id
    return False


def pode_realizar_consulta(papel, usuario, consulta):
    """Quem pode marcar uma consulta como realizada."""
    if papel == Vinculo.ADMIN:
        return True
    if papel == Vinculo.PROFISSIONAL:
        return consulta.profissional.usuario_id == usuario.id
    return False
