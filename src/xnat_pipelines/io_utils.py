from __future__ import annotations
from typing import Any, Dict, Iterable, Optional, List
import pathlib, shutil, json, fnmatch

def ensure_dirs(run_dir: pathlib.Path) -> None:
    (run_dir / "input").mkdir(parents=True, exist_ok=True)
    (run_dir / "output").mkdir(parents=True, exist_ok=True)

def _match_resource(name: str, filters: Dict[str,Any]) -> bool:
    names = set(filters.get("resource_names") or [])
    if names and name not in names:
        return False
    return True

def _match_file(label: str, filters: Dict[str,Any]) -> bool:
    patterns: List[str] = filters.get("patterns") or []
    if not patterns:
        return True
    for pat in patterns:
        if fnmatch.fnmatch(label, pat):
            return True
    return False

def _download_resources(entity, dst_dir: pathlib.Path, filters: Dict[str,Any]) -> None:
    # entity.resources is a mapping of resource label -> resource object
    for res in getattr(entity, "resources", {}).values():
        if not _match_resource(res.label, filters):
            continue
        for fobj in res.files.values():
            if not _match_file(fobj.label, filters):
                continue
            out_path = dst_dir / fobj.label
            out_path.parent.mkdir(parents=True, exist_ok=True)
            fobj.download(str(out_path))

def stage_from_xnat(xn, context: Dict[str,str], run_dir: pathlib.Path, resource_filters: Optional[Dict[str,Any]] = None) -> None:
    level = context.get("level")
    ident = context.get("id")
    (run_dir / "context.json").write_text(json.dumps(context, indent=2))
    if xn is None:
        return
    filters = resource_filters or {}
    try:
        if level == "project":
            proj = xn.projects[ident]
            _download_resources(proj, run_dir / "input", filters)
        elif level == "subject":
            subj = xn.subjects[ident]
            _download_resources(subj, run_dir / "input", filters)
        elif level == "experiment":
            exp = xn.experiments[ident]
            _download_resources(exp, run_dir / "input", filters)
        elif level == "scan":
            # 'scan' id may be ambiguous without session; expect full ID path or use a resolver externally.
            scan = xn.scans[ident]
            _download_resources(scan, run_dir / "input", filters)
        elif level == "resource":
            # Direct resource label under an experiment (common case). Expect pattern EXPID:RESNAME
            if ":" in ident:
                exp_id, res_name = ident.split(":", 1)
                exp = xn.experiments[exp_id]
                res = exp.resources[res_name]
                for fobj in res.files.values():
                    if _match_file(fobj.label, filters):
                        fobj.download(str((run_dir / "input" / fobj.label)))
        else:
            (run_dir / "input_staging_warning.txt").write_text(f"Unknown level: {level}")
    except Exception as e:
        (run_dir / "input_staging_error.txt").write_text(str(e))

def _ensure_resource(entity, name: str):
    # Create if missing, else return existing
    if name in entity.resources:
        return entity.resources[name]
    return entity.create_resource(name)

def upload_outputs_to_xnat(xn, context: Dict[str,str], run_dir: pathlib.Path, resource_name: str = "xnat_pipelines_out") -> Optional[str]:
    if xn is None:
        return None
    level = context.get("level")
    ident = context.get("id")
    out = run_dir / "output"
    if not out.exists():
        return None
    try:
        if level == "project":
            proj = xn.projects[ident]
            res = _ensure_resource(proj, resource_name)
        elif level == "subject":
            subj = xn.subjects[ident]
            res = _ensure_resource(subj, resource_name)
        elif level == "experiment":
            exp = xn.experiments[ident]
            res = _ensure_resource(exp, resource_name)
        elif level == "scan":
            scan = xn.scans[ident]
            res = _ensure_resource(scan, resource_name)
        elif level == "resource":
            # Upload back to the same experiment that holds the resource (EXPID:RESNAME)
            if ":" in ident:
                exp_id, _ = ident.split(":", 1)
                exp = xn.experiments[exp_id]
                res = _ensure_resource(exp, resource_name)
            else:
                return None
        else:
            return None

        for p in out.rglob("*"):
            if p.is_file():
                res.upload(str(p), p.name)
        return f"{level}:{ident}/resource:{resource_name}"
    except Exception as e:
        (run_dir / "output_upload_error.txt").write_text(str(e))
        return None
