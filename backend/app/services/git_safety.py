import subprocess, os
from typing import Dict, Any, List

def _run(args, cwd):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=60)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return -1, "", str(e)

def is_git_repo(path: str) -> bool:
    rc, out, _ = _run(["git", "rev-parse", "--is-inside-work-tree"], path)
    return rc == 0

def status(path: str) -> str:
    rc, out, err = _run(["git", "status", "--porcelain"], path)
    return out

def create_checkpoint_commit(path: str, label: str) -> Dict[str, Any]:
    if not is_git_repo(path):
        return {"ok": False, "reason": "not a git repo"}
    rc, out, err = _run(["git", "add", "-A"], path)
    rc2, out2, err2 = _run(["git", "commit", "-m", f"checkpoint: {label}", "--allow-empty"], path)
    if rc2 == 0:
        rc3, sha, _ = _run(["git", "rev-parse", "HEAD"], path)
        return {"ok": True, "sha": sha}
    return {"ok": False, "reason": err2 or err}

def changed_files(path: str) -> List[str]:
    rc, out, _ = _run(["git", "status", "--porcelain"], path)
    if rc != 0:
        return []
    files = []
    for line in out.splitlines():
        if not line.strip():
            continue
        # format: XY filename
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            files.append(parts[1].strip())
    return files

def rollback(path: str, sha: str) -> bool:
    rc, _, _ = _run(["git", "reset", "--hard", sha], path)
    return rc == 0
