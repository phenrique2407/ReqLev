#!/usr/bin/env python3
"""
ReqLev – Database Seed Script
══════════════════════════════════════════════════════════════════════════════

Creates sample data for demonstration and evaluation purposes.
Safe to run against an empty database or re-run (existing records are detected
and skipped so the script is idempotent).

Pre-configured users
─────────────────────
  alice@reqlev.dev  / password123   (owns 2 projects)
  bob@reqlev.dev    / password123   (has edit access to Alice's first project)
  carol@reqlev.dev  / password123   (has view access to Alice's first project)
  dave@reqlev.dev   / password123   (owns 1 project, no shared access)

Usage
─────
  # From the project root:
  python seed.py

  # With a custom MySQL URL:
  DATABASE_URL="mysql+pymysql://user:pass@host/dbname" python seed.py

  # Verify insertion:
  python seed.py --verify
"""

import os
import sys
import argparse
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ── Allow running from any working directory ──────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

# ── Inline minimal settings (avoid importing app fully before DB is ready) ───
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "mysql+pymysql://root:@localhost:3306/reqlev",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)


def _make_tables():
    """Ensure all tables exist before seeding."""
    from backend.app.database import Base
    from backend.app import models  # noqa: F401 – registers all ORM models
    Base.metadata.create_all(bind=engine)
    print("✔  Tables verified/created.")


def _seed(session):
    from backend.app import models
    from backend.app.auth import hash_password

    # ── Users ────────────────────────────────────────────────────────────────
    def get_or_create_user(username, email, password):
        u = session.query(models.User).filter_by(email=email).first()
        if u:
            print(f"   ↳ User '{username}' already exists, skipping.")
            return u
        u = models.User(
            username      = username,
            email         = email,
            password_hash = hash_password(password),
        )
        session.add(u)
        session.flush()
        print(f"   ✔  Created user '{username}' <{email}>")
        return u

    print("\n── Users ──────────────────────────────────────────────────────────")
    alice = get_or_create_user("alice",  "alice@reqlev.dev", "password123")
    bob   = get_or_create_user("bob",    "bob@reqlev.dev",   "password123")
    carol = get_or_create_user("carol",  "carol@reqlev.dev", "password123")
    dave  = get_or_create_user("dave",   "dave@reqlev.dev",  "password123")

    # ── Projects ─────────────────────────────────────────────────────────────
    def get_or_create_project(owner, name, description):
        p = session.query(models.Project).filter_by(
            owner_id=owner.id, name=name).first()
        if p:
            print(f"   ↳ Project '{name}' already exists, skipping.")
            return p
        p = models.Project(
            name        = name,
            description = description,
            owner_id    = owner.id,
        )
        session.add(p)
        session.flush()
        print(f"   ✔  Created project '{name}' (owner: {owner.username})")
        return p

    print("\n── Projects ───────────────────────────────────────────────────────")
    proj_ecom = get_or_create_project(
        alice,
        "Sistema de E-Commerce",
        "Plataforma de vendas online com carrinho de compras, pagamento integrado "
        "e painel de administração de produtos.",
    )
    proj_rh = get_or_create_project(
        alice,
        "Sistema de RH",
        "Módulo de gestão de funcionários, folha de pagamento e controle de ponto.",
    )
    proj_fintech = get_or_create_project(
        dave,
        "App de Finanças Pessoais",
        "Aplicativo mobile para controle de receitas, despesas, metas e "
        "investimentos pessoais.",
    )

    # ── Permissions ───────────────────────────────────────────────────────────
    def get_or_create_permission(project, user, permission):
        existing = session.query(models.ProjectPermission).filter_by(
            project_id=project.id, user_id=user.id).first()
        if existing:
            print(f"   ↳ Permission for '{user.username}' on '{project.name}' exists, skipping.")
            return existing
        perm = models.ProjectPermission(
            project_id = project.id,
            user_id    = user.id,
            permission = models.PermissionLevel(permission),
        )
        session.add(perm)
        session.flush()
        print(f"   ✔  {user.username} → '{project.name}' [{permission}]")
        return perm

    print("\n── Permissions ────────────────────────────────────────────────────")
    get_or_create_permission(proj_ecom, bob,   "edit")
    get_or_create_permission(proj_ecom, carol, "view")
    get_or_create_permission(proj_rh,   bob,   "view")

    # ── Requirements ──────────────────────────────────────────────────────────
    def get_or_create_req(project, name, description, req_type, status, creator):
        existing = session.query(models.Requirement).filter_by(
            project_id=project.id, name=name).first()
        if existing:
            print(f"   ↳ Requirement '{name}' exists, skipping.")
            return existing
        req = models.Requirement(
            project_id  = project.id,
            name        = name,
            description = description,
            type        = models.RequirementType(req_type),
            status      = models.RequirementStatus(status),
            created_by  = creator.id,
        )
        session.add(req)
        session.flush()
        print(f"   ✔  [{req_type}] {name} ({status})")
        return req

    print(f"\n── Requirements – {proj_ecom.name} ──────────────────────────────")
    reqs_ecom = [
        get_or_create_req(proj_ecom, "Cadastro de Usuário",
            "O sistema deve permitir cadastro com e-mail, senha e confirmação. "
            "Verificação de e-mail obrigatória.",
            "RF", "done", alice),
        get_or_create_req(proj_ecom, "Login e Autenticação",
            "Autenticação via JWT com refresh token. Suporte a 2FA opcional.",
            "RF", "done", alice),
        get_or_create_req(proj_ecom, "Catálogo de Produtos",
            "Listagem paginada com filtros por categoria, faixa de preço e "
            "disponibilidade em estoque.",
            "RF", "done", bob),
        get_or_create_req(proj_ecom, "Carrinho de Compras",
            "Persistência do carrinho entre sessões. Cálculo automático de "
            "frete por CEP.",
            "RF", "in_progress", bob),
        get_or_create_req(proj_ecom, "Pagamento Online",
            "Integração com gateway de pagamento (Pix, cartão de crédito/débito). "
            "Retentativa automática em caso de falha.",
            "RF", "in_progress", alice),
        get_or_create_req(proj_ecom, "Painel Administrativo",
            "Dashboard com KPIs de vendas, gerenciamento de pedidos e controle "
            "de estoque.",
            "RF", "todo", alice),
        get_or_create_req(proj_ecom, "Performance – Tempo de Carregamento",
            "Páginas de listagem devem carregar em menos de 2 segundos com "
            "1.000 usuários concorrentes.",
            "RNF", "todo", alice),
        get_or_create_req(proj_ecom, "Segurança – LGPD",
            "Todos os dados pessoais devem ser armazenados criptografados. "
            "Política de privacidade e consentimento obrigatórios.",
            "RNF", "in_progress", bob),
        get_or_create_req(proj_ecom, "Disponibilidade",
            "SLA de 99,9% de uptime. Monitoramento ativo com alertas automáticos.",
            "RNF", "todo", alice),
    ]

    print(f"\n── Requirements – {proj_rh.name} ──────────────────────────────")
    reqs_rh = [
        get_or_create_req(proj_rh, "Cadastro de Funcionários",
            "Formulário completo com dados pessoais, cargo, departamento e "
            "data de admissão.",
            "RF", "done", alice),
        get_or_create_req(proj_rh, "Controle de Ponto",
            "Registro de entrada/saída com suporte a horas extras e banco de horas.",
            "RF", "in_progress", alice),
        get_or_create_req(proj_rh, "Folha de Pagamento",
            "Cálculo automático de salário, INSS, IRRF e benefícios. Geração "
            "de holerites em PDF.",
            "RF", "todo", alice),
        get_or_create_req(proj_rh, "Relatórios Gerenciais",
            "Exportação de relatórios em Excel e PDF com dados de headcount, "
            "turnover e absenteísmo.",
            "RF", "todo", alice),
        get_or_create_req(proj_rh, "Segurança de Dados",
            "Controle de acesso por perfil (admin, gerente, funcionário). "
            "Logs de auditoria para todas as operações.",
            "RNF", "in_progress", alice),
    ]

    print(f"\n── Requirements – {proj_fintech.name} ────────────────────────")
    reqs_fintech = [
        get_or_create_req(proj_fintech, "Registro de Transações",
            "Lançamento manual de receitas e despesas com categorização automática "
            "via IA.",
            "RF", "in_progress", dave),
        get_or_create_req(proj_fintech, "Dashboard Financeiro",
            "Visão consolidada de saldo, evolução patrimonial e projeção de "
            "gastos futuros.",
            "RF", "todo", dave),
        get_or_create_req(proj_fintech, "Metas de Economia",
            "Definição de metas mensais com acompanhamento visual e notificações "
            "push quando próximo do limite.",
            "RF", "todo", dave),
        get_or_create_req(proj_fintech, "Sincronização Bancária",
            "Integração com Open Finance para importação automática de extratos.",
            "RF", "todo", dave),
        get_or_create_req(proj_fintech, "Criptografia de Dados Financeiros",
            "Todas as transações devem ser armazenadas com AES-256. "
            "Comunicação exclusivamente via HTTPS.",
            "RNF", "in_progress", dave),
        get_or_create_req(proj_fintech, "Modo Offline",
            "O app deve funcionar sem internet, sincronizando quando reconectado.",
            "RNF", "todo", dave),
    ]

    # ── Activity Logs ─────────────────────────────────────────────────────────
    def log_activity(project, user, action, obj_type, obj_id, obj_name, details=None):
        existing = session.query(models.ActivityLog).filter_by(
            project_id=project.id, action=action,
            object_id=obj_id, user_id=user.id).first()
        if existing:
            return existing
        entry = models.ActivityLog(
            project_id  = project.id,
            user_id     = user.id,
            action      = action,
            object_type = models.ObjectType(obj_type),
            object_id   = obj_id,
            object_name = obj_name,
            details     = details,
        )
        session.add(entry)
        return entry

    print("\n── Activity Logs ──────────────────────────────────────────────────")

    # E-Commerce project logs
    log_activity(proj_ecom, alice, "Criou o projeto",    "project",     proj_ecom.id, proj_ecom.name)
    log_activity(proj_ecom, alice, "Criou requisito",    "requirement", reqs_ecom[0].id, reqs_ecom[0].name, "Tipo: RF, Status: todo")
    log_activity(proj_ecom, alice, "Criou requisito",    "requirement", reqs_ecom[1].id, reqs_ecom[1].name, "Tipo: RF, Status: todo")
    log_activity(proj_ecom, alice, "Editou requisito",   "requirement", reqs_ecom[0].id, reqs_ecom[0].name, "status: A fazer → Concluído")
    log_activity(proj_ecom, alice, "Editou requisito",   "requirement", reqs_ecom[1].id, reqs_ecom[1].name, "status: A fazer → Concluído")
    log_activity(proj_ecom, alice, f"Compartilhou com {bob.username} (Editar)", "project", proj_ecom.id, proj_ecom.name)
    log_activity(proj_ecom, alice, f"Compartilhou com {carol.username} (Apenas Ver)", "project", proj_ecom.id, proj_ecom.name)
    log_activity(proj_ecom, bob,   "Criou requisito",    "requirement", reqs_ecom[2].id, reqs_ecom[2].name, "Tipo: RF, Status: done")
    log_activity(proj_ecom, bob,   "Criou requisito",    "requirement", reqs_ecom[3].id, reqs_ecom[3].name, "Tipo: RF, Status: in_progress")
    log_activity(proj_ecom, alice, "Criou requisito",    "requirement", reqs_ecom[4].id, reqs_ecom[4].name, "Tipo: RF, Status: in_progress")
    log_activity(proj_ecom, alice, "Criou requisito",    "requirement", reqs_ecom[5].id, reqs_ecom[5].name, "Tipo: RF, Status: todo")
    log_activity(proj_ecom, alice, "Criou requisito",    "requirement", reqs_ecom[6].id, reqs_ecom[6].name, "Tipo: RNF, Status: todo")
    log_activity(proj_ecom, bob,   "Criou requisito",    "requirement", reqs_ecom[7].id, reqs_ecom[7].name, "Tipo: RNF, Status: in_progress")
    log_activity(proj_ecom, alice, "Criou requisito",    "requirement", reqs_ecom[8].id, reqs_ecom[8].name, "Tipo: RNF, Status: todo")
    log_activity(proj_ecom, bob,   "Editou requisito",   "requirement", reqs_ecom[7].id, reqs_ecom[7].name, "descrição atualizada")

    # RH project logs
    log_activity(proj_rh, alice, "Criou o projeto",  "project",     proj_rh.id, proj_rh.name)
    log_activity(proj_rh, alice, f"Compartilhou com {bob.username} (Apenas Ver)", "project", proj_rh.id, proj_rh.name)
    for req in reqs_rh:
        log_activity(proj_rh, alice, "Criou requisito", "requirement", req.id, req.name)
    log_activity(proj_rh, alice, "Editou requisito", "requirement", reqs_rh[0].id, reqs_rh[0].name, "status: A fazer → Concluído")

    # Fintech project logs
    log_activity(proj_fintech, dave, "Criou o projeto", "project", proj_fintech.id, proj_fintech.name)
    for req in reqs_fintech:
        log_activity(proj_fintech, dave, "Criou requisito", "requirement", req.id, req.name)

    print("   ✔  Activity logs inserted.")

    session.commit()
    print("\n✅  Seed completed successfully!")


def _verify(session):
    from backend.app import models

    print("\n── Verification ───────────────────────────────────────────────────")
    users = session.query(models.User).all()
    print(f"   Users        : {len(users)}")
    for u in users:
        print(f"                  • {u.username} <{u.email}>")

    projects = session.query(models.Project).all()
    print(f"   Projects     : {len(projects)}")
    for p in projects:
        count = session.query(models.Requirement).filter_by(project_id=p.id).count()
        print(f"                  • {p.name} ({count} requisitos, owner: {p.owner.username})")

    perms = session.query(models.ProjectPermission).all()
    print(f"   Permissions  : {len(perms)}")
    for pm in perms:
        print(f"                  • {pm.user.username} → {pm.project.name} [{pm.permission.value}]")

    req_count = session.query(models.Requirement).count()
    print(f"   Requirements : {req_count}")

    log_count = session.query(models.ActivityLog).count()
    print(f"   Activity logs: {log_count}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="ReqLev – Database seed / verification script",
    )
    parser.add_argument("--verify", action="store_true",
                        help="Only verify existing data without inserting")
    parser.add_argument("--url",    type=str, default=None,
                        help="Override DATABASE_URL")
    args = parser.parse_args()

    if args.url:
        global DATABASE_URL, engine, Session
        DATABASE_URL = args.url
        engine       = create_engine(DATABASE_URL, pool_pre_ping=True)
        Session      = sessionmaker(bind=engine)

    print("═" * 66)
    print("  ReqLev – Seed Script")
    print(f"  Database: {DATABASE_URL.split('@')[-1]}")
    print("═" * 66)

    try:
        _make_tables()
    except Exception as e:
        print(f"\n❌  Could not connect to database: {e}")
        print("    Make sure MySQL is running and DATABASE_URL is correct.")
        sys.exit(1)

    session = Session()
    try:
        if not args.verify:
            _seed(session)
        _verify(session)
    except Exception as e:
        session.rollback()
        print(f"\n❌  Seed failed: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
