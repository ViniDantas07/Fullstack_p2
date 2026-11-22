# Agenda de Consultas — P2

| Requisito do P2 | Onde está |
|---|---|
| **Múltiplas clínicas** | `Clinica`; `Profissional` e `Paciente` pertencem a uma clínica; a clínica ativa fica na sessão |
| **Papéis de usuário** | `Vinculo` (usuário + clínica + papel): administrador, recepção, profissional, paciente |
| **Dashboard** | `/dashboard/` (tela) e `consultas/dashboard.py` (métricas) |
| **API REST (DRF)** | `/api/...` (`api_serializers.py`, `api_views.py`, `api_urls.py`) |

## Multi-clínica

Um mesmo usuário pode participar de várias clínicas, **com papéis diferentes em cada
uma**. Depois do login, a pessoa escolhe a clínica (`/clinicas/`); tudo que ela vê e
faz depois fica isolado nessa clínica. Pode também criar uma clínica nova (vira
administrador dela) ou entrar em outra como paciente.

## Papéis e permissões

| Ação | Admin | Recepção | Profissional | Paciente |
|---|:-:|:-:|:-:|:-:|
| Ver dashboard | ✅ | ✅ | – | – |
| Ver agenda completa da clínica | ✅ | ✅ | – | – |
| Gerenciar equipe (adicionar/remover membros) | ✅ | – | – | – |
| Cadastrar a própria disponibilidade | – | – | ✅ | – |
| Marcar consulta | para qualquer paciente | para qualquer paciente | – | só para si |
| Cancelar consulta | qualquer | qualquer | as suas | as suas |
| Marcar como realizada | qualquer | – | as suas | – |

O controle está no decorator `papel_requerido(...)` (`consultas/permissoes.py`) nas
views web, e no `ClinicaMixin` (`api_views.py`) na API.

## Regras de negócio

`Consulta.clean()` (mantida do P1, mais uma regra nova):

1. o horário precisa estar dentro de um bloco de `Disponibilidade` do profissional;
2. não pode conflitar com outra consulta agendada do mesmo profissional;
3. **(P2)** paciente e profissional precisam ser da mesma clínica.

A mesma validação é usada pelos formulários web e pela API.

## Como rodar

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py makemigrations
python manage.py migrate
python manage.py popular_demo      # opcional: cria dados de demonstração
python manage.py runserver
```

> Se você já rodou o P1 nesta pasta, apague o `db.sqlite3` antes: o esquema mudou
> (clínicas e papéis).

`popular_demo` cria 2 clínicas e um usuário de cada papel (senha de todos:
`demo12345`): `admin_demo`, `recepcao_demo`, `dr_silva`, `dra_costa`,
`joao_paciente`, `maria_paciente`. Veja a saída do comando para o papel de cada um.

## API REST

Autenticação por token (ou pela sessão do navegador, o que permite usar a API
navegável do DRF em `/api/clinicas/`).

```bash
# 1) obter token
curl -X POST http://127.0.0.1:8000/api/token/ \
     -d "username=joao_paciente&password=demo12345"
# {"token": "abc123..."}

# 2) minhas clínicas e meu papel em cada uma
curl -H "Authorization: Token abc123..." http://127.0.0.1:8000/api/clinicas/
```

| Método e rota | Descrição | Quem pode |
|---|---|---|
| `POST /api/token/` | obtém o token | qualquer um com conta |
| `GET /api/clinicas/` | clínicas do usuário + papel | autenticado |
| `GET /api/clinicas/{id}/profissionais/` | profissionais da clínica | membros |
| `GET /api/clinicas/{id}/disponibilidades/?profissional=` | disponibilidades | membros |
| `POST/PUT/PATCH/DELETE /api/clinicas/{id}/disponibilidades/` | gerenciar disponibilidade | profissional (as suas), admin |
| `GET /api/clinicas/{id}/consultas/?status=&data=&profissional=` | lista consultas | cada papel vê só o que lhe cabe |
| `POST /api/clinicas/{id}/consultas/` | agenda consulta | paciente, recepção, admin |
| `POST /api/clinicas/{id}/consultas/{n}/cancelar/` | cancela | conforme a tabela de papéis |
| `POST /api/clinicas/{id}/consultas/{n}/realizar/` | marca como realizada | profissional (as suas), admin |
| `GET /api/clinicas/{id}/dashboard/` | métricas da clínica | admin, recepção |

Exemplo de agendamento (como paciente):

```bash
curl -X POST http://127.0.0.1:8000/api/clinicas/1/consultas/ \
     -H "Authorization: Token abc123..." -H "Content-Type: application/json" \
     -d '{"profissional": 1, "data": "2026-11-25", "hora_inicio": "10:00", "hora_fim": "10:30"}'
```

