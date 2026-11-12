import sys, os, webbrowser, subprocess, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

app = typer.Typer(help="D-ORCHESTRATOR: multi-provider AI engineering command center")
console = Console()

VERSION = "1.0.0"


def _db():
    from app.db import SessionLocal, init_db
    init_db()
    return SessionLocal()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context, version: bool = typer.Option(False, "--version", help="Show version")):
    if version:
        console.print(f"D-ORCHESTRATOR {VERSION}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        # launch interactive terminal
        from cli.terminal import run_interactive
        run_interactive()


@app.command()
def init():
    """Initialize database and seed providers."""
    db = _db()
    from app.services import provider_registry, usage_manager
    provider_registry.seed_providers(db)
    usage_manager.get_budget(db)
    # refresh models
    import asyncio
    asyncio.run(provider_registry.refresh_all(db))
    db.close()
    console.print("[green]Initialized D-ORCHESTRATOR.[/green]")


@app.command()
def doctor():
    """Check environment and integrations."""
    console.print(Panel("D-ORCHESTRATOR Doctor", style="cyan"))
    # python
    console.print(f"Python: {sys.version.split()[0]}")
    # ollama
    import httpx
    try:
        r = httpx.get("http://127.0.0.1:11434/api/tags", timeout=5)
        console.print(f"Ollama: [green]reachable[/green] ({len(r.json().get('models', []))} models)")
    except Exception as e:
        console.print(f"Ollama: [red]unreachable[/red] ({e})")
    # opencode
    import shutil
    oc = shutil.which("opencode")
    console.print(f"OpenCode: {'[green]found[/green] ' + oc if oc else '[red]not found[/red]'}")
    # db
    db = _db()
    from app.models import Provider, ModelRecord
    console.print(f"Providers: {db.query(Provider).count()}, Models: {db.query(ModelRecord).count()}")
    db.close()


# ---------- Sessions ----------
sessions_app = typer.Typer(help="Session management")
app.add_typer(sessions_app, name="sessions")


@sessions_app.command("list")
def sessions_list():
    db = _db()
    from app.models import Session as S
    rows = db.query(S).order_by(S.last_active.desc()).all()
    t = Table("ID", "Title", "Model", "Msgs", "Status", "Last Active")
    for s in rows:
        t.add_row(s.id[:8], s.title or "-", s.model_id or "-", str(s.message_count), s.status, str(s.last_active))
    console.print(t)
    db.close()


@sessions_app.command("new")
def sessions_new(title: str = typer.Option(None, "--title", "-t"), project_dir: str = typer.Option(None, "--dir", "-d")):
    db = _db()
    from app.models import Session as S
    s = S(title=title, project_dir=project_dir)
    db.add(s)
    db.commit()
    db.refresh(s)
    console.print(f"[green]Created session[/green] {s.id}")
    db.close()


@sessions_app.command("show")
def sessions_show(sid: str):
    db = _db()
    from app.models import Session as S, Message
    s = db.query(S).filter(S.id == sid).first() or db.query(S).filter(S.id.startswith(sid)).first()
    if not s:
        console.print("[red]Session not found[/red]"); raise typer.Exit(1)
    msgs = db.query(Message).filter(Message.session_id == s.id).all()
    console.print(Panel(f"Session {s.id}\nTitle: {s.title}\nModel: {s.model_id}\nMessages: {len(msgs)}", style="cyan"))
    for m in msgs[-20:]:
        console.print(f"[bold]{m.role}[/bold]: {m.content[:300]}")
    db.close()


@sessions_app.command("resume")
def sessions_resume(sid: str):
    console.print(f"Resume session {sid} (use interactive mode).")
    # set env var for interactive
    os.environ["DORCH_SESSION"] = sid
    from cli.terminal import run_interactive
    run_interactive(resume_sid=sid)


@sessions_app.command("delete")
def sessions_delete(sid: str, yes: bool = typer.Option(False, "--yes", "-y")):
    db = _db()
    from app.models import Session as S, Message
    s = db.query(S).filter(S.id == sid).first() or db.query(S).filter(S.id.startswith(sid)).first()
    if not s:
        console.print("[red]Not found[/red]"); raise typer.Exit(1)
    if not yes and not Confirm.ask(f"Delete session {s.id}?"):
        raise typer.Exit()
    db.query(Message).filter(Message.session_id == s.id).delete()
    db.delete(s)
    db.commit()
    console.print("[green]Deleted[/green]")
    db.close()


@sessions_app.command("export")
def sessions_export(sid: str, out: str = typer.Option("session_export.json", "--out", "-o")):
    import json
    db = _db()
    from app.models import Session as S, Message
    s = db.query(S).filter(S.id == sid).first() or db.query(S).filter(S.id.startswith(sid)).first()
    if not s:
        console.print("[red]Not found[/red]"); raise typer.Exit(1)
    msgs = db.query(Message).filter(Message.session_id == s.id).all()
    data = {"session": {c.name: getattr(s, c.name) for c in s.__table__.columns}, "messages": [{c.name: getattr(m, c.name) for c in m.__table__.columns} for m in msgs]}
    Path(out).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    console.print(f"[green]Exported to {out}[/green]")
    db.close()


# alias
@app.command("sessions")
def sessions_alias():
    sessions_list()


# ---------- Models ----------
models_app = typer.Typer(help="Model management")
app.add_typer(models_app, name="models")


@models_app.command("list")
def models_list(provider: str = typer.Option(None, "--provider", "-p")):
    db = _db()
    from app.models import ModelRecord
    q = db.query(ModelRecord)
    if provider:
        q = q.filter(ModelRecord.provider_name == provider)
    rows = q.all()
    t = Table("Model", "Provider", "Category", "Ctx", "Local", "CostIn", "Health", "Avail")
    for m in rows:
        t.add_row(m.model_id, m.provider_name, m.category, str(m.context_window), "Y" if m.is_local else "N", str(m.estimated_cost_input), m.health, "Y" if m.available else "N")
    console.print(t)
    db.close()


@models_app.command("local")
def models_local():
    models_list(provider=None)
    db = _db()
    from app.models import ModelRecord
    rows = db.query(ModelRecord).filter(ModelRecord.is_local == True).all()
    db.close()
    t = Table("Model", "Provider", "Category", "Ctx")
    for m in rows:
        t.add_row(m.model_id, m.provider_name, m.category, str(m.context_window))
    console.print(t)


@models_app.command("cloud")
def models_cloud():
    db = _db()
    from app.models import ModelRecord
    rows = db.query(ModelRecord).filter(ModelRecord.is_local == False).all()
    db.close()
    t = Table("Model", "Provider", "Category", "Ctx")
    for m in rows:
        t.add_row(m.model_id, m.provider_name, m.category, str(m.context_window))
    console.print(t)


@models_app.command("search")
def models_search(query: str):
    db = _db()
    from app.models import ModelRecord
    rows = db.query(ModelRecord).filter(ModelRecord.model_id.contains(query)).all()
    db.close()
    for m in rows:
        console.print(m.model_id, m.provider_name)


@models_app.command("use")
def models_use(model: str):
    # store default in env/config file
    cfg = Path.home() / ".dorchestrator"
    cfg.mkdir(exist_ok=True)
    (cfg / "default_model.txt").write_text(model)
    console.print(f"[green]Default model set to {model}[/green]")


@models_app.command("info")
def models_info(model: str):
    db = _db()
    from app.models import ModelRecord
    m = db.query(ModelRecord).filter(ModelRecord.model_id == model).first()
    if not m:
        console.print("[red]Not found[/red]"); raise typer.Exit(1)
    console.print(Panel(f"{m.model_id}\nProvider: {m.provider_name}\nCategory: {m.category}\nContext: {m.context_window}\nTools: {m.supports_tools}\nVision: {m.supports_vision}\nCost in/out: {m.estimated_cost_input}/{m.estimated_cost_output}\nHealth: {m.health}\nAvailable: {m.available}", style="cyan"))
    db.close()


@app.command("models")
def models_alias():
    models_list()


# ---------- Providers ----------
providers_app = typer.Typer(help="Provider management")
app.add_typer(providers_app, name="providers")


@providers_app.command("list")
def providers_list():
    db = _db()
    from app.models import Provider
    rows = db.query(Provider).all()
    t = Table("Name", "Kind", "Health", "Auth", "Enabled")
    for p in rows:
        t.add_row(p.name, p.kind, p.health, p.auth_type, str(p.enabled))
    console.print(t)
    db.close()


@providers_app.command("connect")
def providers_connect(provider: str, api_key: str = typer.Option(None, "--api-key")):
    # store env hint
    console.print(f"To connect {provider}, set the appropriate environment variable and run `dorchestrator providers test {provider}`.")
    if api_key:
        console.print("[yellow]API key passed via CLI is not stored for security; use environment variables.[/yellow]")


@providers_app.command("disconnect")
def providers_disconnect(provider: str):
    console.print(f"Disconnect {provider} by unsetting its environment variable and disabling in dashboard.")


@providers_app.command("test")
def providers_test(provider: str):
    import asyncio
    db = _db()
    from app.services import provider_registry
    res = asyncio.run(provider_registry.refresh_provider(db, provider))
    db.close()
    console.print(res)


@app.command("providers")
def providers_alias():
    providers_list()


# ---------- Usage ----------
usage_app = typer.Typer(help="Usage analytics")
app.add_typer(usage_app, name="usage")


@usage_app.command("today")
def usage_today():
    db = _db()
    from app.services import usage_manager
    bs = usage_manager.budget_status(db)
    console.print(bs)
    db.close()


@usage_app.command("monthly")
def usage_monthly():
    usage_today()


@usage_app.command("providers")
def usage_providers():
    db = _db()
    from app.services import usage_manager
    s = usage_manager.usage_summary(db)
    for p in s["by_provider"]:
        console.print(p)
    db.close()


@usage_app.command("export")
def usage_export(out: str = typer.Option("usage_export.json", "--out", "-o")):
    import json
    db = _db()
    from app.services import usage_manager
    s = usage_manager.usage_summary(db)
    db.close()
    Path(out).write_text(json.dumps(s, indent=2, default=str))
    console.print(f"[green]Exported to {out}[/green]")


@app.command("usage")
def usage_alias():
    db = _db()
    from app.services import usage_manager
    s = usage_manager.usage_summary(db)
    console.print(s)
    db.close()


# ---------- Tasks ----------
tasks_app = typer.Typer(help="Task management")
app.add_typer(tasks_app, name="tasks")


@tasks_app.command("list")
def tasks_list():
    db = _db()
    from app.models import Task
    rows = db.query(Task).order_by(Task.created_at.desc()).all()
    t = Table("ID", "Title", "Status", "Model")
    for r in rows:
        t.add_row(r.id[:8], r.title, r.status, r.current_model or "-")
    console.print(t)
    db.close()


@tasks_app.command("show")
def tasks_show(tid: str):
    db = _db()
    from app.models import Task
    t = db.query(Task).filter(Task.id == tid).first() or db.query(Task).filter(Task.id.startswith(tid)).first()
    if not t:
        console.print("[red]Not found[/red]"); raise typer.Exit(1)
    console.print(Panel(f"{t.title}\nStatus: {t.status}\nModel: {t.current_model}\nError: {t.error}\nResult: {(t.result_summary or '')[:500]}", style="cyan"))
    db.close()


@tasks_app.command("resume")
def tasks_resume(tid: str):
    import asyncio
    db = _db()
    from app.services import task_executor
    res = asyncio.run(task_executor.run_task(db, tid))
    db.close()
    console.print(res)


@tasks_app.command("cancel")
def tasks_cancel(tid: str):
    db = _db()
    from app.models import Task
    t = db.query(Task).filter(Task.id == tid).first() or db.query(Task).filter(Task.id.startswith(tid)).first()
    if t:
        t.status = "cancelled"
        db.commit()
    db.close()
    console.print("[green]Cancelled[/green]")


@app.command("tasks")
def tasks_alias():
    tasks_list()


# ---------- Other ----------
@app.command()
def dashboard():
    """Start backend and open dashboard."""
    console.print("Starting backend on http://127.0.0.1:8000 ...")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], cwd=str(Path(__file__).resolve().parent.parent / "backend"))
    time.sleep(6)
    webbrowser.open("http://127.0.0.1:8000")
    console.print("Dashboard opened. Press Ctrl+C to stop.")
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()


@app.command()
def config():
    console.print("Config stored in ~/.dorchestrator and backend/data")


@app.command()
def logs():
    console.print("Logs are in backend console output.")


@app.command()
def memory():
    db = _db()
    from app.models import ProjectMemory
    rows = db.query(ProjectMemory).all()
    for r in rows:
        console.print(r.project_name, r.project_dir)
    db.close()


@app.command()
def reset():
    if Confirm.ask("Reset database?"):
        p = Path(__file__).resolve().parent.parent / "backend" / "data" / "d_orchestrator.db"
        if p.exists():
            p.unlink()
        console.print("[green]Database reset.[/green]")


@app.command()
def update():
    console.print("Run git pull / pip install -e . to update.")


if __name__ == "__main__":
    app()
