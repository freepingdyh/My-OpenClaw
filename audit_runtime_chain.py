#!/usr/bin/env python3
"""Audit the active Xiaoxia runtime wrapper chain without importing application code.

Phase 0/1 safety tool for runtime flattening. Read-only: parses Python AST only.
It deliberately does not execute installers, import lobster_discord, or change runtime behavior.
"""
from __future__ import annotations
import ast, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = "xiaoxia_runtime_v11207.py"
OUT = ROOT / "runtime_active_manifest.json"

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def runtime_import(tree: ast.AST):
    found=[]
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.startswith("xiaoxia_runtime_"):
                    found.append(a.name + ".py")
    return found

def xiaoxia_imports(tree: ast.AST):
    out=[]
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("xiaoxia"):
            out.append({"module":n.module,"names":[a.name for a in n.names]})
    return out

def calls_and_assignments(tree: ast.AST):
    rows=[]
    for n in getattr(tree,"body",[]):
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call):
            rows.append({"kind":"call","source":ast.unparse(n.value)})
        elif isinstance(n,(ast.Assign,ast.AnnAssign,ast.AugAssign)):
            rows.append({"kind":"assignment","source":ast.unparse(n)})
    return rows

def main():
    cur=ENTRY; seen=set(); chain=[]
    while True:
        if cur in seen:
            raise RuntimeError(f"runtime cycle detected at {cur}")
        seen.add(cur)
        path=ROOT/cur
        if not path.exists():
            raise FileNotFoundError(path)
        src=path.read_text(encoding="utf-8")
        tree=ast.parse(src, filename=cur)
        nxt=runtime_import(tree)
        chain.append({
            "file":cur,
            "sha256":sha256(path),
            "runtime_imports":nxt,
            "xiaoxia_imports":xiaoxia_imports(tree),
            "top_level_effects":calls_and_assignments(tree),
        })
        if not nxt: break
        if len(nxt)!=1:
            raise RuntimeError(f"{cur}: expected exactly one previous runtime, got {nxt}")
        cur=nxt[0]

    all_runtime=sorted(p.name for p in ROOT.glob("xiaoxia_runtime_*.py"))
    active={x["file"] for x in chain}
    manifest={
        "entry":ENTRY,
        "active_count":len(chain),
        "repository_runtime_count":len(all_runtime),
        "inactive_runtime_files":[x for x in all_runtime if x not in active],
        "active_chain":chain,
    }
    OUT.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"active={len(chain)} repo={len(all_runtime)} inactive={len(manifest['inactive_runtime_files'])}")
    print("inactive:", ", ".join(manifest["inactive_runtime_files"]) or "(none)")
    print("wrote", OUT.name)

if __name__=="__main__":
    main()
