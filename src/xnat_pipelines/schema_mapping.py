from __future__ import annotations
from typing import Any, Dict, List, Tuple

def map_inputs_and_mounts(cmd_raw: Dict[str,Any], user_inputs: Dict[str,Any]) -> Tuple[List[str], Dict[str,str]]:
    """
    Returns (extra_args, env_map) based on command schema.
    - extra_args: list of additional CLI args (e.g., ['--threshold','0.3'])
    - env_map: dict of ENV var name -> value
    We also look for mounts in cmd_raw.get('mounts') and expect local backend to handle volumes accordingly.
    """
    extra_args: List[str] = []
    env_map: Dict[str,str] = {}
    inputs = cmd_raw.get('inputs') or []
    # inputs may be list or dict; normalize to list of objects with 'name'
    if isinstance(inputs, dict):
        items = []
        for k,v in inputs.items():
            iv = {'name': k}
            if isinstance(v, dict):
                iv.update(v)
            items.append(iv)
        inputs = items

    # Build args/env from schema
    for spec in inputs:
        name = spec.get('name')
        if not name:
            continue
        val = user_inputs.get(name, spec.get('default'))
        if val is None:
            continue
        # Prefer explicit env or arg mapping if present
        env_key = spec.get('env')
        arg_flag = spec.get('arg')  # e.g., '--threshold'
        if env_key:
            env_map[str(env_key)] = str(val)
        elif arg_flag:
            extra_args += [str(arg_flag), str(val)]
        else:
            # default: env UPPERCASE
            env_map[str(name).upper()] = str(val)

    return extra_args, env_map

def resolve_mounts(cmd_raw: Dict[str,Any], default_in='/input', default_out='/output'):
    mounts = cmd_raw.get('mounts') or {}
    in_mnt = mounts.get('input', default_in)
    out_mnt = mounts.get('output', default_out)
    return in_mnt, out_mnt
