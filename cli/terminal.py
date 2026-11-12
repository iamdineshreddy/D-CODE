import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
import asyncio

console = Console()


def _db():
    from app.db import SessionLocal, init_db
    init_db()
    return SessionLocal()


SLASH_COMMANDS = {
    "/help": "Show commands",
    "/models": "List models",
    "/providers": "List providers",
    "/sessions": "List sessions",
    "/new": "New session",
    "/resume": "Resume session (by id)",
    "/clear": "Clear screen",
    "/usage": "Usage summary",
    "/context": "Context info",
    "/tasks": "List tasks",
    "/status": "Status",
    "/plan": "Plan a task (usage: /plan <objective>)",
    "/execute": "Execute task (usage: /execute <task_id>)",
    "/pause": "Pause task",
    "/cancel": "Cancel task",
    "/dashboard": "Open dashboard",
    "/settings": "Settings",
    "/exit": "Exit",
}


def _handle_slash(cmd: str, session_id: str | None):
    parts = cmd.strip().split(None, 1)
    name = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    if name == "/help":
        for k, v in SLASH_COMMANDS.items():
            console.print(f"  [cyan]{k}[/cyan] - {v}")
        return session_id
    if name == "/clear":
        console.clear()
        return session_id
    if name == "/models":
        db = _db()
        from app.models import ModelRecord
        rows = db.query(ModelRecord).all()
        db.close()
        for m in rows[:40]:
            console.print(f"{m.model_id} ({m.provider_name})")
        return session_id
    if name == "/providers":
        db = _db()
        from app.models import Provider
        for p in db.query(Provider).all():
            console.print(f"{p.name}: {p.health}")
        db.close()
        return session_id
    if name == "/sessions":
        db = _db()
        from app.models import Session as S
        for s in db.query(S).all():
            console.print(f"{s.id[:8]} {s.title or '-'} {s.status}")
        db.close()
        return session_id
    if name == "/new":
        db = _db()
        from app.models import Session as S
        s = S(title="New session")
        db.add(s)
        db.commit()
        db.refresh(s)
        db.close()
        console.print(f"[green]Created session {s.id}[/green]")
        return s.id
    if name == "/resume":
        return arg.strip() if arg else session_id
    if name == "/usage":
        db = _db()
        from app.services import usage_manager
        console.print(usage_manager.usage_summary(db))
        db.close()
        return session_id
    if name == "/tasks":
        db = _db()
        from app.models import Task
        for t in db.query(Task).all():
            console.print(f"{t.id[:8]} {t.title} {t.status}")
        db.close()
        return session_id
    if name == "/status":
        console.print(f"Session: {session_id}")
        return session_id
    if name == "/plan":
        if not arg:
            console.print("Usage: /plan <objective>")
            return session_id
        db = _db()
        import asyncio
        from app.services import prompt_optimizer
        opt = asyncio.run(prompt_optimizer.optimize_prompt(arg, "balanced"))
        db.close()
        console.print(Panel(opt["optimized"], title="Plan"))
        return session_id
    if name == "/execute":
        if not arg:
            console.print("Usage: /execute <task_id>")
            return session_id
        db = _db()
        import asyncio
        from app.services import task_executor
        res = asyncio.run(task_executor.run_task(db, arg))
        db.close()
        console.print(res)
        return session_id
    if name == "/dashboard":
        import subprocess, sys, time, webbrowser
        from pathlib import Path
        proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], cwd=str(Path(__file__).resolve().parent.parent / "backend"))
        time.sleep(5)
        webbrowser.open("http://127.0.0.1:8000")
        return session_id
    if name == "/exit":
        raise SystemExit
    if name == "/settings":
        console.print("Use dashboard Settings.")
        return session_id
    console.print(f"Unknown command {name}")
    return session_id


def run_interactive(resume_sid: str = None):
    console.print(Panel("D-ORCHESTRATOR Interactive Terminal", style="cyan"))
    session_id = resume_sid or os.environ.get("DORCH_SESSION")
    # create session if none
    if not session_id:
        db = _db()
        from app.models import Session as S
        s = S(title="Interactive session")
        db.add(s)
        db.commit()
        db.refresh(s)
        db.close()
        session_id = s.id
    console.print(f"Session: {session_id}")
    console.print("Type /help for commands. Type a prompt to chat. Ctrl+C to exit.")

    while True:
        try:
            user_input = Prompt.ask("[bold green]you[/bold green]")
        except (KeyboardInterrupt, EOFError):
            console.print("\nBye.")
            break
        if not user_input.strip():
            continue
        if user_input.strip().startswith("/"):
            try:
                session_id = _handle_slash(user_input.strip(), session_id)
            except SystemExit:
                break
            continue
        # chat: route model and call opencode
        db = _db()
        from app.services import model_router
        rr = model_router.route(db, user_input, execution=False)
        model = rr.get("selected_model")
        provider = rr.get("provider")
        # save user message
        from app.models import Message, Session as S
        s = db.query(S).filter(S.id == session_id).first()
        if s:
            if not s.title or s.title == "Interactive session":
                s.title = user_input[:50]
            m = Message(session_id=session_id, role="user", content=user_input, model_id=model, provider_name=provider)
            db.add(m)
            db.commit()
        console.print(f"[dim]Using {provider}/{model}[/dim]")
        # execute via opencode if available else chat
        if provider == "opencode":
            from app.providers.opencode import OpenCodeAdapter
            adapter = OpenCodeAdapter()
            import asyncio
            res = asyncio.run(adapter.run_task(model, user_input, timeout=120.0))
            reply = res.get("text", "") or res.get("stderr", "")
        else:
            from app.services import provider_registry
            adapter = provider_registry.get_adapter(provider)
            if adapter is None:
                reply = "No adapter"
            else:
                r = asyncio.run(adapter.chat(model, [{"role": "user", "content": user_input}]))
                reply = r.get("content", "")
        console.print(Panel(reply, title="assistant"))
        # save assistant message
        m = Message(session_id=session_id, role="assistant", content=reply, model_id=model, provider_name=provider)
        db.add(m)
        if s:
            s.message_count = (s.message_count or 0) + 2
        db.commit()
        db.close()
