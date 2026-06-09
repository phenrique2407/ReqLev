# ReqLev — Gerenciamento de Projetos & Requisitos

**ReqLev** é uma aplicação web full-stack para gerenciamento de projetos e
requisitos com colaboração em tempo real, controle de permissões granular,
log de atividades completo e exportação de relatórios em PDF.

```
Stack: FastAPI · SQLAlchemy · MySQL · Vanilla JS · CSS puro · SSE
```

---

## Sumário

1. [Visão Geral da Arquitetura](#1-visão-geral-da-arquitetura)
2. [Estrutura de Diretórios](#2-estrutura-de-diretórios)
3. [Pré-requisitos](#3-pré-requisitos)
4. [Configuração do Ambiente](#4-configuração-do-ambiente)
5. [Instalação de Dependências](#5-instalação-de-dependências)
6. [Configuração do Banco de Dados](#6-configuração-do-banco-de-dados)
7. [Rodando a Aplicação](#7-rodando-a-aplicação)
8. [Script de Seed](#8-script-de-seed)
9. [Documentação da API](#9-documentação-da-api)
10. [Modelo de Banco de Dados](#10-modelo-de-banco-de-dados)
11. [Colaboração em Tempo Real (SSE)](#11-colaboração-em-tempo-real-sse)
12. [Exportação PDF](#12-exportação-pdf)
13. [Testes Automatizados](#13-testes-automatizados)
14. [Guia de Usuário](#14-guia-de-usuário)

---

## 1. Visão Geral da Arquitetura

```
┌──────────────────────────────────────────────────────────┐
│  Browser (Vanilla JS SPA)                                 │
│  ┌──────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐  │
│  │  Login/  │  │Dashboard │  │ Project │  │   SSE    │  │
│  │ Register │  │ (lista)  │  │ Detail  │  │  Client  │  │
│  └────┬─────┘  └────┬─────┘  └────┬────┘  └────┬─────┘  │
│       │             │             │              │        │
│  HTTP REST (fetch)               │         EventSource   │
└───────┼─────────────┼─────────────┼──────────────┼───────┘
        │             │ JSON        │              │ SSE stream
┌───────▼─────────────▼─────────────▼──────────────▼───────┐
│  FastAPI Backend                                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐   │
│  │  /auth   │ │/projects │ │  /reqs   │ │  /sse/...  │   │
│  └──────────┘ └──────────┘ └──────────┘ └─────┬──────┘   │
│       │                         │             │           │
│  SQLAlchemy ORM            activity_log   SSEManager      │
│       │                         │        (asyncio.Queue)  │
└───────┼─────────────────────────┼───────────────────────┘
        │                         │
┌───────▼─────────────────────────▼───────┐
│           MySQL (ou SQLite nos testes)   │
│  users · projects · project_permissions │
│  requirements · activity_logs           │
└─────────────────────────────────────────┘
```

### Fluxo de autenticação

```
POST /api/auth/register  →  201 { access_token }
POST /api/auth/login     →  200 { access_token }

Todas as rotas protegidas:  Authorization: Bearer <token>
Rota SSE (EventSource):     ?token=<token>   (query param)
```

---

## 2. Estrutura de Diretórios

```
reqlev/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── activity_service.py   # helper para gravar logs
│   │   ├── auth.py               # JWT: hash, create, decode, deps
│   │   ├── config.py             # pydantic-settings
│   │   ├── database.py           # engine, SessionLocal, create_tables
│   │   ├── main.py               # FastAPI app, CORS, static files
│   │   ├── models.py             # SQLAlchemy ORM
│   │   ├── pdf_service.py        # ReportLab PDF generation
│   │   ├── schemas.py            # Pydantic request/response models
│   │   ├── sse_manager.py        # SSE connection manager (asyncio.Queue)
│   │   └── routers/
│   │       ├── auth.py           # /api/auth/*
│   │       ├── users.py          # /api/users/search
│   │       ├── projects.py       # /api/projects/*  (CRUD + share + PDF)
│   │       ├── requirements.py   # /api/projects/{id}/requirements/*
│   │       ├── activities.py     # /api/projects/{id}/activities
│   │       └── sse.py            # /api/sse/projects/{id}
│   ├── tests/
│   │   ├── conftest.py           # fixtures, helpers, SQLite override
│   │   ├── test_auth.py          # 17 tests
│   │   ├── test_projects.py      # 30 tests  (CRUD + permissions + activity)
│   │   ├── test_requirements.py  # 22 tests
│   │   └── test_pdf.py           # 8 tests
│   └── requirements.txt
├── frontend/
│   ├── index.html                # SPA entry point
│   ├── css/
│   │   └── styles.css            # dark-orange design system
│   └── js/
│       ├── api.js                # fetch wrapper
│       ├── auth.js               # JWT state (localStorage)
│       ├── router.js             # hash-based SPA router
│       ├── sse.js                # EventSource wrapper
│       ├── ui.js                 # toasts, modal, loader, helpers
│       └── views/
│           ├── login.js
│           ├── register.js
│           ├── dashboard.js      # list + create projects
│           └── project.js        # full project view + real-time
├── seed.py                       # demo data script
├── pytest.ini
├── .env.example
└── README.md
```

---

## 3. Pré-requisitos

| Ferramenta | Versão mínima |
|------------|--------------|
| Python     | 3.10+        |
| MySQL      | 8.0+         |
| pip        | 23+          |

> **Nota:** Para rodar os testes não é necessário MySQL —
> eles usam SQLite in-memory automaticamente.

---

## 4. Configuração do Ambiente

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/reqlev.git
cd reqlev

# 2. Crie e ative o virtualenv
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

# 3. Copie o arquivo de ambiente
cp .env.example .env
```

Edite `.env` com as configurações do seu MySQL:

```env
DATABASE_URL=mysql+pymysql://root:suasenha@localhost:3306/reqlev
SECRET_KEY=troque-por-uma-string-longa-e-aleatoria
ACCESS_TOKEN_EXPIRE_MINUTES=43200   # 30 dias
```

Gere um SECRET_KEY seguro:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 5. Instalação de Dependências

```bash
cd backend
pip install -r requirements.txt
```

`requirements.txt` inclui:
```
fastapi==0.110.0          # framework web
uvicorn[standard]==0.27.1 # servidor ASGI
sqlalchemy==2.0.27        # ORM
pymysql==1.1.0            # driver MySQL
python-jose[cryptography] # JWT
passlib[bcrypt]==1.7.4    # hash de senhas
bcrypt==4.0.1             # compatível com passlib
pydantic[email]==2.6.1    # validação
pydantic-settings==2.2.1  # configuração
reportlab==4.1.0          # geração de PDF
pytest==8.0.2             # testes
pytest-asyncio==0.23.5    # testes async
httpx==0.27.0             # cliente HTTP para testes
aiofiles==23.2.1          # arquivos async
```

---

## 6. Configuração do Banco de Dados

### Criar o banco no MySQL

```sql
-- Conecte ao MySQL
mysql -u root -p

-- Crie o banco
CREATE DATABASE reqlev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- (Opcional) crie um usuário dedicado
CREATE USER 'reqlev_user'@'localhost' IDENTIFIED BY 'senha_segura';
GRANT ALL PRIVILEGES ON reqlev.* TO 'reqlev_user'@'localhost';
FLUSH PRIVILEGES;
```

### Criação automática de tabelas

As tabelas são criadas automaticamente no primeiro `startup` do servidor.
Não é necessário rodar migrations manualmente.

```bash
# Iniciar o servidor cria as tabelas:
uvicorn backend.app.main:app --reload
# ✅  ReqLev API started – http://localhost:8000
```

---

## 7. Rodando a Aplicação

### Backend (a partir da raiz do projeto)

```bash
# Modo desenvolvimento com hot-reload
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

O FastAPI serve o frontend automaticamente em `http://localhost:8000`.

Para desenvolvimento frontend isolado, você pode usar qualquer servidor
de arquivos estáticos apontando para `frontend/`:

```bash
# Python simples:
cd frontend
python -m http.server 3000
# Acesse http://localhost:3000
```

> Neste caso, ajuste a constante `API_BASE` em `frontend/js/api.js`:
> ```js
> const API_BASE = 'http://localhost:8000';
> ```

### Acessando

| URL | Descrição |
|-----|-----------|
| `http://localhost:8000`       | Aplicação web (frontend) |
| `http://localhost:8000/api/docs`  | Swagger UI (API interativa) |
| `http://localhost:8000/api/redoc` | Redoc (documentação alternativa) |

---

## 8. Script de Seed

O script `seed.py` popula o banco com dados de exemplo para avaliação.

### Executar

```bash
# A partir da raiz do projeto:
python seed.py

# Com URL customizada:
DATABASE_URL="mysql+pymysql://user:pass@host/dbname" python seed.py

# Apenas verificar dados existentes (sem inserir):
python seed.py --verify
```

### Usuários criados

| Username | Email               | Senha       | Papel |
|----------|---------------------|-------------|-------|
| alice    | alice@reqlev.dev    | password123 | Proprietária de 2 projetos |
| bob      | bob@reqlev.dev      | password123 | Editor no projeto E-Commerce; Visualizador em RH |
| carol    | carol@reqlev.dev    | password123 | Visualizador no projeto E-Commerce |
| dave     | dave@reqlev.dev     | password123 | Proprietário de 1 projeto próprio |

### Projetos criados

| Projeto | Proprietário | Requisitos | Colaboradores |
|---------|-------------|-----------|---------------|
| Sistema de E-Commerce | alice | 9 | bob (edit), carol (view) |
| Sistema de RH | alice | 5 | bob (view) |
| App de Finanças Pessoais | dave | 6 | — |

### Verificar inserção

```bash
python seed.py --verify
```

Saída esperada:
```
── Verification ────────────────────────────────
   Users        : 4
   Projects     : 3
   Permissions  : 3
   Requirements : 20
   Activity logs: 27
```

Também pode verificar diretamente no MySQL:
```sql
USE reqlev;
SELECT username, email FROM users;
SELECT name, (SELECT COUNT(*) FROM requirements r WHERE r.project_id = p.id) AS reqs
FROM projects p;
```

### Re-executar o seed

O script é idempotente: execuções repetidas pulam registros já existentes.
Para começar do zero:

```sql
-- Limpar tudo
DROP DATABASE reqlev;
CREATE DATABASE reqlev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

---

## 9. Documentação da API

### Autenticação

| Método | Endpoint | Descrição | Auth |
|--------|----------|-----------|------|
| POST | `/api/auth/register` | Registrar novo usuário | ❌ |
| POST | `/api/auth/login` | Login (retorna JWT) | ❌ |
| GET  | `/api/auth/me` | Usuário autenticado | ✅ |

**POST /api/auth/register**
```json
// Request
{ "username": "alice", "email": "alice@test.com", "password": "secret123" }
// Response 201
{ "access_token": "eyJ...", "token_type": "bearer" }
```

**POST /api/auth/login**
```json
// Request
{ "email": "alice@test.com", "password": "secret123" }
// Response 200
{ "access_token": "eyJ...", "token_type": "bearer" }
```

---

### Usuários

| Método | Endpoint | Descrição | Auth |
|--------|----------|-----------|------|
| GET | `/api/users/search?q=termo` | Buscar usuários por email/username | ✅ |

---

### Projetos

| Método | Endpoint | Descrição | Permissão |
|--------|----------|-----------|-----------|
| GET    | `/api/projects` | Listar projetos do usuário | auth |
| POST   | `/api/projects` | Criar projeto | auth |
| GET    | `/api/projects/{id}` | Ver projeto | owner/edit/view |
| PUT    | `/api/projects/{id}` | Editar projeto | owner/edit |
| DELETE | `/api/projects/{id}` | Deletar projeto | owner |
| GET    | `/api/projects/{id}/permissions` | Listar permissões | owner/edit/view |
| POST   | `/api/projects/{id}/permissions` | Compartilhar | owner |
| PUT    | `/api/projects/{id}/permissions/{uid}` | Alterar permissão | owner |
| DELETE | `/api/projects/{id}/permissions/{uid}` | Revogar acesso | owner |
| GET    | `/api/projects/{id}/export/pdf` | Exportar PDF | owner/edit/view |

**POST /api/projects**
```json
// Request
{ "name": "Meu Projeto", "description": "Opcional" }
// Response 201
{ "id": 1, "name": "Meu Projeto", "user_permission": "owner", ... }
```

**POST /api/projects/{id}/permissions**
```json
// Request
{ "user_id": 42, "permission": "view" }   // "view" ou "edit"
// Response 201
{ "id": 1, "project_id": 1, "user_id": 42, "permission": "view", ... }
```

---

### Requisitos

| Método | Endpoint | Descrição | Permissão |
|--------|----------|-----------|-----------|
| GET    | `/api/projects/{id}/requirements` | Listar (filtro: `?status=todo`) | owner/edit/view |
| POST   | `/api/projects/{id}/requirements` | Criar | owner/edit |
| GET    | `/api/projects/{id}/requirements/{rid}` | Ver requisito | owner/edit/view |
| PUT    | `/api/projects/{id}/requirements/{rid}` | Editar | owner/edit |
| DELETE | `/api/projects/{id}/requirements/{rid}` | Deletar | owner/edit |

**POST /api/projects/{id}/requirements**
```json
// Request
{
  "name": "Autenticação de usuário",
  "description": "Login via JWT",
  "type": "RF",            // "RF" ou "RNF"
  "status": "todo"         // "todo" | "in_progress" | "done"
}
// Response 201
{ "id": 5, "type": "RF", "status": "todo", ... }
```

**GET /api/projects/{id}/requirements?status=done**
```json
// Response 200 – apenas requisitos com status "done"
[{ "id": 1, "name": "Login", "status": "done", ... }]
```

---

### Atividades

| Método | Endpoint | Descrição | Permissão |
|--------|----------|-----------|-----------|
| GET | `/api/projects/{id}/activities?limit=100&offset=0` | Log de atividades | owner/edit/view |

---

### SSE – Tempo Real

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET  | `/api/sse/projects/{id}?token=JWT` | Stream SSE do projeto |
| POST | `/api/sse/projects/{id}/editing/start?requirement_id=N&token=JWT` | Sinalizar início de edição |
| POST | `/api/sse/projects/{id}/editing/stop?requirement_id=N&token=JWT` | Sinalizar fim de edição |

---

### Erros padrão

| Status | Significado |
|--------|-------------|
| 400 | Requisição inválida (ex: compartilhar consigo mesmo) |
| 401 | Token ausente ou inválido |
| 403 | Sem permissão para a operação |
| 404 | Recurso não encontrado |
| 409 | Conflito (ex: email já registrado) |
| 422 | Erro de validação (campo obrigatório, formato inválido) |

```json
// Formato de erro
{ "detail": "mensagem de erro descritiva" }
```

---

## 10. Modelo de Banco de Dados

```
┌─────────────┐       ┌──────────────────────┐       ┌──────────────────┐
│   users     │       │   project_permissions│       │    projects      │
├─────────────┤       ├──────────────────────┤       ├──────────────────┤
│ id (PK)     │──┐    │ id (PK)              │    ┌──│ id (PK)          │
│ username    │  │    │ project_id (FK)──────┼────┘  │ name             │
│ email       │  └────│ user_id    (FK)      │       │ description      │
│ password_hash│       │ permission           │       │ owner_id (FK)────┼──┐
│ created_at  │       │   view | edit        │       │ created_at       │  │
└─────────────┘       │ created_at           │       │ updated_at       │  │
       │               └──────────────────────┘       └──────────────────┘  │
       │                                                       │             │
       │               ┌──────────────────┐                   │             │
       │               │  requirements    │                   │             │
       │               ├──────────────────┤                   │             │
       │               │ id (PK)          │                   │             │
       │               │ project_id (FK)──┼───────────────────┘             │
       │               │ name             │                                  │
       │               │ description      │                                  │
       └───────────────│ created_by (FK)  │                                  │
                       │ type: RF | RNF   │                                  │
                       │ status:          │                                  │
                       │  todo|in_progress│                                  │
                       │  |done           │                                  │
                       │ created_at       │                                  │
                       │ updated_at       │                                  │
                       └──────────────────┘                                  │
                                                                             │
               ┌──────────────────────┐                                      │
               │   activity_logs      │                                      │
               ├──────────────────────┤                                      │
               │ id (PK)              │                                      │
               │ project_id (FK)──────┼──────────────────────────────────────┘
               │ user_id    (FK)      │
               │ action               │
               │ object_type          │
               │  project|requirement │
               │ object_id            │
               │ object_name          │
               │ details              │
               │ created_at           │
               └──────────────────────┘
```

### Regras de permissão

| Ação | owner | edit | view |
|------|:-----:|:----:|:----:|
| Ver projeto | ✅ | ✅ | ✅ |
| Editar projeto | ✅ | ✅ | ❌ |
| Deletar projeto | ✅ | ❌ | ❌ |
| Compartilhar projeto | ✅ | ❌ | ❌ |
| Criar requisito | ✅ | ✅ | ❌ |
| Editar requisito | ✅ | ✅ | ❌ |
| Deletar requisito | ✅ | ✅ | ❌ |
| Ver log de atividades | ✅ | ✅ | ✅ |
| Exportar PDF | ✅ | ✅ | ✅ |

> **Last-Write-Wins:** Edições simultâneas são suportadas sem lock.
> A última gravação sobrescreve silenciosamente as anteriores.

---

## 11. Colaboração em Tempo Real (SSE)

### Tecnologia escolhida: Server-Sent Events (SSE)

Preferimos SSE em vez de WebSockets por três razões:

1. **Unidirecional por natureza** – o servidor envia eventos para clientes;
   clientes enviam mudanças via HTTP normal. SSE é perfeito para isso.
2. **Infraestrutura simples** – SSE usa HTTP/1.1 puro, sem upgrade de
   protocolo, compatível com qualquer proxy reverso sem configuração extra.
3. **Reconexão automática** – o browser reconecta automaticamente se a
   conexão cair, sem código adicional no cliente.

### Fluxo completo

```
Browser A (editor)              Server                Browser B (viewer)
       │                           │                          │
       │── POST /requirements ────►│                          │
       │                           │── db.commit() ──────────►│
       │                           │── sse_manager            │
       │                           │   .broadcast(project_id, │
       │                           │   "requirement_created", │
       │                           │   {req_data})           ►│ SSE event
       │                           │                          │
       │                           │                    JS dispatchEvent
       │                           │                    → DOM update (no refresh)
```

### Implementação no servidor

`sse_manager.py` mantém um dicionário:
```python
# project_id → [asyncio.Queue, asyncio.Queue, ...]
_queues: Dict[int, List[asyncio.Queue]]
```

Quando uma mudança ocorre, qualquer router chama:
```python
await sse_manager.broadcast(project_id, "requirement_created", data)
```

Isso coloca o evento em **cada Queue** do projeto. O gerador SSE
consome a Queue e faz `yield` para o cliente:
```python
async def stream(project_id, queue):
    yield "event: connected\ndata: {...}\n\n"
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=30)
            yield event               # SSE frame
        except asyncio.TimeoutError:
            yield ": heartbeat\n\n"   # keep-alive
```

### Eventos emitidos

| Evento | Quando |
|--------|--------|
| `connected` | Handshake inicial |
| `requirement_created` | Requisito criado |
| `requirement_updated` | Requisito editado |
| `requirement_deleted` | Requisito deletado |
| `project_updated` | Metadados do projeto alterados |
| `project_deleted` | Projeto deletado |
| `permission_added` | Novo colaborador adicionado |
| `permission_removed` | Acesso revogado |
| `editing_start` | Usuário abriu form de edição |
| `editing_stop` | Usuário fechou form de edição |

### Indicador de edição ativa

Quando um usuário abre o formulário de edição inline de um requisito,
o frontend dispara:

```
POST /api/sse/projects/{id}/editing/start?requirement_id={rid}&token={jwt}
```

O servidor faz broadcast de `editing_start` para todos os viewers.
O card do requisito recebe uma borda âmbar e o texto
_"username está editando…"_.

Quando o usuário salva ou cancela:
```
POST /api/sse/projects/{id}/editing/stop?requirement_id={rid}&token={jwt}
```

### Implementação no cliente

```js
// Abrir conexão SSE ao entrar na tela de projeto
sseClient.connect(projectId);   // cria EventSource com ?token=JWT

// Ouvir eventos como CustomEvents no document
document.addEventListener('rl:requirement_created', e => {
    projectView._onReqCreated(e.detail);   // atualiza DOM diretamente
});
```

### Suporte a editores simultâneos ilimitados

Não há lock de requisitos. Qualquer número de usuários pode editar
o mesmo requisito ao mesmo tempo. O último `PUT /requirements/{id}`
a chegar ao servidor vence (**last-write-wins**). A mudança é
propagada para todos via SSE imediatamente.

---

## 12. Exportação PDF

### Como usar

```
GET /api/projects/{id}/export/pdf
Authorization: Bearer <token>
```

O servidor gera e retorna o PDF como stream direto (sem preview):
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="ReqLev_Nome_Projeto.pdf"
```

### Estrutura do PDF

```
┌─────────────────────────────────────┐
│  CAPA (fundo escuro, barra laranja) │
│  ─────────────────────────────────  │
│  ReqLev                             │
│  Nome do Projeto                    │
│  Descrição                          │
│                                     │
│  Data de Criação: 01/01/2025        │
│  Proprietário: alice                │
│  Contribuidores:                    │
│    • bob <bob@reqlev.dev> — Editor  │
│  Total de Requisitos: 9             │
├─────────────────────────────────────┤
│  REQUISITOS                         │
│  ─────────────────────────────────  │
│  ┌─────────────────────────────┐    │
│  │ Nome do Requisito           │    │
│  │ [RF] [Em andamento]         │    │
│  │ Descrição detalhada…        │    │
│  └─────────────────────────────┘    │
│  … (um card por requisito)          │
├─────────────────────────────────────┤
│  HISTÓRICO DE ATIVIDADES            │
│  ─────────────────────────────────  │
│  Tabela: Data/Hora | Usuário | Ação │
└─────────────────────────────────────┘
```

### Via curl

```bash
curl -H "Authorization: Bearer SEU_TOKEN" \
     "http://localhost:8000/api/projects/1/export/pdf" \
     --output relatorio.pdf
```

### Via JavaScript (frontend)

```js
const blob = await api.download(`/api/projects/${id}/export/pdf`);
const url  = URL.createObjectURL(blob);
const a    = document.createElement('a');
a.href     = url;
a.download = 'relatorio.pdf';
a.click();
```

---

## 13. Testes Automatizados

### Executar todos os testes

```bash
# A partir da raiz do projeto (sem MySQL – usa SQLite in-memory):
python -m pytest

# Com saída verbosa:
python -m pytest -v

# Apenas um arquivo:
python -m pytest backend/tests/test_auth.py -v

# Com cobertura (instale pytest-cov):
pip install pytest-cov
python -m pytest --cov=backend/app --cov-report=term-missing
```

### Resultado esperado

```
backend/tests/test_auth.py         17 passed
backend/tests/test_projects.py     30 passed
backend/tests/test_requirements.py 22 passed
backend/tests/test_pdf.py           8 passed
─────────────────────────────────────────────
77 passed
```

### Estrutura dos testes

```
backend/tests/
├── conftest.py              # fixtures: db, client, factories
├── test_auth.py             # 17 testes
│   ├── TestRegister         # sucesso, email dup, username dup, senha fraca…
│   ├── TestLogin            # sucesso, senha errada, email desconhecido…
│   ├── TestMe               # token válido, ausente, inválido
│   └── funções unitárias    # hash_password, token roundtrip
├── test_projects.py         # 30 testes
│   ├── TestProjectCRUD      # create, list, get, update, delete
│   ├── TestPermissions      # share, view-only, edit, revoke, owner-only…
│   ├── TestUserSearch       # por username, por email, exclui self
│   └── TestActivityLog      # log gerado em cada ação, acesso por view
├── test_requirements.py     # 22 testes
│   ├── create               # owner, edit-user, view-user (403)
│   ├── filter               # ?status=done, inválido
│   ├── edit                 # tipo, status, nome; edit-user edita qualquer req
│   ├── delete               # edit-user deleta qualquer req; view-user (403)
│   └── activity log         # entrada criada em create/update/delete
└── test_pdf.py              # 8 testes
    ├── export_owner/view/edit   # todos recebem PDF válido (%PDF magic)
    ├── non_member_denied        # 403
    ├── empty_project            # sem requisitos → PDF válido
    ├── filename_header          # Content-Disposition correto
    └── pdf_service_unit         # unit test sem HTTP, instâncias mock
```

### Estratégia de teste

* **Banco de dados**: SQLite in-memory com `StaticPool` — todos os testes
  são isolados e não requerem MySQL.
* **Isolamento**: cada teste recebe um banco limpo via fixture `db`
  (`create_all` antes, `drop_all` depois).
* **Cliente HTTP**: `TestClient` do Starlette com override de `get_db`.
* **Sem mocks de negócio**: os testes exercem o caminho real
  (router → service → ORM → SQLite).
* **PDF**: teste de unidade instancia objetos ORM diretamente,
  sem necessidade de banco.

### Configuração (pytest.ini)

```ini
[pytest]
testpaths = backend/tests
asyncio_mode = auto
addopts = -v --tb=short
```

---

## 14. Guia de Usuário

### Primeiros passos

1. Acesse `http://localhost:8000`
2. Clique em **"Criar conta"** e preencha username, email e senha
3. Após o registro, você é redirecionado ao dashboard

### Criar um projeto

1. No dashboard, clique em **"+ Novo Projeto"**
2. Informe nome e descrição (opcional)
3. O projeto aparece no dashboard com o badge **"Proprietário"**

### Adicionar requisitos

1. Clique no projeto para abrir a tela de detalhes
2. Clique em **"+ Adicionar"**
3. Preencha nome, descrição, tipo (**RF** ou **RNF**) e andamento
4. O requisito aparece em tempo real para todos os usuários com acesso

### Filtrar requisitos

Use os botões de filtro no topo da lista:
`Todos` · `A fazer` · `Em andamento` · `Concluídos`

### Editar um requisito

1. Clique no ícone ✏️ no card do requisito
2. O formulário inline se abre; outros usuários veem
   _"username está editando…"_ no card
3. Altere qualquer campo (incluindo **tipo RF/RNF**)
4. Clique **Salvar** — a mudança aparece para todos instantaneamente

### Compartilhar um projeto

1. Na tela do projeto, clique em **"+ Compartilhar"** (somente proprietário)
2. Digite email ou username no campo de busca
3. Selecione o usuário da lista
4. Escolha a permissão: **Apenas Ver** ou **Editar**
5. Clique **Compartilhar**

### Exportar PDF

Clique no botão **"⬇ PDF"** na barra superior do projeto.
O download inicia imediatamente.

### Visualizar histórico

O painel **"Atividades Recentes"** na direita da tela de projeto
lista as últimas 20 ações. Usuários com permissão **"Apenas Ver"**
têm acesso completo ao histórico.

---

## Licença

MIT — use, modifique e distribua livremente.
