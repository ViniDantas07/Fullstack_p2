from datetime import datetime, time, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from consultas.models import Clinica, Consulta, Disponibilidade, Paciente, Profissional, Vinculo

SENHA = "demo12345"


def usuario(username, nome, sobrenome):
    user, criado = User.objects.get_or_create(
        username=username, defaults={"first_name": nome, "last_name": sobrenome}
    )
    if criado:
        user.set_password(SENHA)
        user.save()
    return user


def membro(clinica, user, papel, **extra):
    if not Vinculo.objects.filter(usuario=user, clinica=clinica).exists():
        clinica.adicionar_membro(user, papel, **extra)


class Command(BaseCommand):
    help = "Cria dados de demonstração: 2 clínicas, um usuário de cada papel, disponibilidades e consultas."

    def handle(self, *args, **options):
        hoje = timezone.localdate()

        vida, _ = Clinica.objects.get_or_create(nome="Clínica Vida", defaults={"endereco": "Rua das Flores, 100"})
        bem, _ = Clinica.objects.get_or_create(nome="Clínica Bem Estar", defaults={"endereco": "Av. Central, 500"})

        admin = usuario("admin_demo", "Ana", "Administradora")
        recep = usuario("recepcao_demo", "Rita", "Recepção")
        dr_silva = usuario("dr_silva", "Carlos", "Silva")
        dr_costa = usuario("dra_costa", "Marina", "Costa")
        joao = usuario("joao_paciente", "João", "Pereira")
        maria = usuario("maria_paciente", "Maria", "Souza")

        membro(vida, admin, Vinculo.ADMIN)
        membro(vida, recep, Vinculo.RECEPCAO)
        membro(vida, dr_silva, Vinculo.PROFISSIONAL, especialidade="Clínico geral")
        membro(vida, joao, Vinculo.PACIENTE, telefone="(24) 99999-0001")
        membro(vida, maria, Vinculo.PACIENTE, telefone="(24) 99999-0002")

        # o mesmo usuário com papéis diferentes em clínicas diferentes
        membro(bem, admin, Vinculo.PACIENTE)
        membro(bem, dr_costa, Vinculo.PROFISSIONAL, especialidade="Dermatologia")
        membro(bem, dr_silva, Vinculo.PROFISSIONAL, especialidade="Cardiologia")
        membro(bem, joao, Vinculo.ADMIN)

        silva_vida = Profissional.objects.get(usuario=dr_silva, clinica=vida)
        costa_bem = Profissional.objects.get(usuario=dr_costa, clinica=bem)
        for prof in (silva_vida, costa_bem):
            for dias in range(-2, 6):
                Disponibilidade.objects.get_or_create(
                    profissional=prof,
                    data=hoje + timedelta(days=dias),
                    hora_inicio=time(8, 0),
                    hora_fim=time(12, 0),
                )

        pac_joao = Paciente.objects.get(usuario=joao, clinica=vida)
        pac_maria = Paciente.objects.get(usuario=maria, clinica=vida)
        exemplos = [
            (pac_joao, 0, time(8, 0), Consulta.STATUS_AGENDADA),
            (pac_maria, 0, time(9, 0), Consulta.STATUS_AGENDADA),
            (pac_joao, 2, time(10, 0), Consulta.STATUS_AGENDADA),
            (pac_maria, -1, time(8, 0), Consulta.STATUS_REALIZADA),
            (pac_joao, -2, time(9, 0), Consulta.STATUS_REALIZADA),
            (pac_maria, 3, time(8, 30), Consulta.STATUS_CANCELADA),
        ]
        for paciente, dias, inicio, status in exemplos:
            fim = (datetime.combine(hoje, inicio) + timedelta(minutes=30)).time()
            Consulta.objects.get_or_create(
                paciente=paciente,
                profissional=silva_vida,
                data=hoje + timedelta(days=dias),
                hora_inicio=inicio,
                defaults={"hora_fim": fim, "status": status},
            )

        self.stdout.write(self.style.SUCCESS("Dados de demonstração criados. Senha de todos: " + SENHA))
        self.stdout.write("  admin_demo      -> administrador da Clínica Vida (e paciente na Bem Estar)")
        self.stdout.write("  recepcao_demo   -> recepção da Clínica Vida")
        self.stdout.write("  dr_silva        -> profissional nas duas clínicas")
        self.stdout.write("  dra_costa       -> profissional da Clínica Bem Estar")
        self.stdout.write("  joao_paciente   -> paciente na Vida, administrador na Bem Estar")
        self.stdout.write("  maria_paciente  -> paciente na Vida")
