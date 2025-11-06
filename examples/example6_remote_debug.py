#!/usr/bin/env python3
"""
Example 6: Launch the XNAT debug container remotely via the Container Service REST API.

This script mirrors the workflow used in the xnat_proxy_site project:
  1. Fetch command + wrapper metadata.
  2. Download the launch UI definition to inspect required fields.
  3. Optionally submit a launch request against /xapi/wrappers/{id}/root/{rootElement}/launch.

By default the script only inspects the launch UI. Pass --submit to post the job.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Dict, Iterable, Optional

import requests


LEVEL_PARAM_MAP = {
    "xnat:projectData": "project",
    "xnat:subjectData": "subject",
    "xnat:imageSessionData": "session",
    "xnat:imageScanData": "scan",
    "xnat:imageAssessorData": "assessor",
    "xnat:resourceData": "resource",
    "xnat:resourceCatalog": "resource",
}


def resolve_command(session: requests.Session, base_url: str, command_name: str) -> Dict[str, Any]:
    resp = session.get(f"{base_url}/xapi/commands", params={"format": "json"})
    resp.raise_for_status()
    for entry in resp.json():
        if str(entry.get("name")) == command_name or str(entry.get("id")) == command_name:
            return entry
    raise SystemExit(f"Command {command_name!r} not found on {base_url}")


def resolve_wrapper(command: Dict[str, Any], wrapper_id: int) -> Dict[str, Any]:
    for key in ("xnat", "xnat-command-wrappers", "xnatCommandWrappers", "wrappers"):
        wrappers = command.get(key)
        if isinstance(wrappers, list):
            for wrapper in wrappers:
                if int(wrapper.get("id") or wrapper.get("wrapper-id") or wrapper.get("wrapperId", -1)) == wrapper_id:
                    return wrapper
    raise SystemExit(f"Wrapper {wrapper_id} not found for command {command.get('name')}")


def fetch_launch_ui(
    session: requests.Session,
    base_url: str,
    wrapper_id: int,
    root_param: str,
    target_id: str,
) -> Dict[str, Any]:
    params = {"context": root_param, root_param: target_id}
    resp = session.get(f"{base_url}/xapi/wrappers/{wrapper_id}/launch", params=params)
    resp.raise_for_status()
    return resp.json()


def launch_container(
    session: requests.Session,
    base_url: str,
    wrapper_id: int,
    root_element: str,
    root_param: str,
    target_id: str,
    inputs: Dict[str, Any],
) -> Dict[str, Any]:
    payload: Dict[str, str] = {
        "context": root_param,
        root_param: target_id,
        "inputs": json.dumps(inputs),
    }
    for key, value in inputs.items():
        payload[f"inputs.{key}"] = json.dumps(value) if isinstance(value, (dict, list)) else str(value)

    resp = session.post(
        f"{base_url}/xapi/wrappers/{wrapper_id}/root/{root_element}/launch",
        data=payload,
    )
    resp.raise_for_status()
    if resp.headers.get("content-type", "").startswith("application/json"):
        return resp.json()
    return {"status": "Unknown", "raw": resp.text}


def recent_containers(
    session: requests.Session,
    base_url: str,
    command_id: Optional[int],
    limit: int = 5,
) -> Iterable[Dict[str, Any]]:
    body: Dict[str, Any] = {
        "size": limit,
        "sort": [{"field": "id", "direction": "desc"}],
    }
    if command_id is not None:
        body["filter"] = {"command-id": command_id}
    resp = session.post(f"{base_url}/xapi/containers", json=body)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        items = data.get("items") or data.get("containers") or data.get("ResultSet", {}).get("Result")
        if isinstance(items, list):
            return items
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote debug container launch example.")
    parser.add_argument("--base-url", default="http://demo02.xnatworks.io", help="XNAT server base URL")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default="admin")
    parser.add_argument("--command-name", default="debug", help="Container command to use")
    parser.add_argument("--wrapper-id", type=int, default=70, help="Wrapper ID that matches the experiment/session context")
    parser.add_argument("--target-id", default="XNAT_E00001", help="XNAT context identifier (session, scan, etc.)")
    parser.add_argument("--output-file", default="remote-example.txt", help="Name for the generated output resource")
    parser.add_argument("--message", default="echo remote example from xnat_pipelines", help="Command to run inside the container")
    parser.add_argument("--submit", action="store_true", help="Submit the container launch instead of previewing only")
    args = parser.parse_args()

    session = requests.Session()
    session.auth = (args.user, args.password)

    command = resolve_command(session, args.base_url, args.command_name)
    try:
        command_id_int = int(command.get("id"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        command_id_int = None

    wrapper = resolve_wrapper(command, args.wrapper_id)
    root_element = wrapper.get("root-element") or wrapper.get("rootElement")
    if not isinstance(root_element, str):
        contexts = wrapper.get("contexts") or wrapper.get("context") or []
        if isinstance(contexts, list):
            root_element = next((ctx for ctx in contexts if ctx in LEVEL_PARAM_MAP), "xnat:imageSessionData")
        else:
            root_element = "xnat:imageSessionData"

    root_param = LEVEL_PARAM_MAP.get(root_element, "session")

    print(f"Command: {command.get('name')} (id={command.get('id')})")
    print(f"Wrapper: {wrapper.get('name')} (id={args.wrapper_id})")
    print(f"Root element: {root_element} • Form parameter: {root_param}")
    print(f"Target {root_param}: {args.target_id}")

    launch_ui = fetch_launch_ui(session, args.base_url, args.wrapper_id, root_param, args.target_id)
    input_config = launch_ui.get("input-config") or launch_ui.get("inputs") or []
    input_values = launch_ui.get("input-values") or []

    print("\nLaunch form fields discovered:")
    if not input_config:
        print("  (No input-config returned)")
    else:
        for item in input_config:
            label = item.get("label") or item.get("name")
            required = "required" if item.get("required") else "optional"
            print(f"  - {label} ({required})")

    if input_values:
        print("\nPre-resolved values:")
        for value in input_values:
            vals = value.get("values") or []
            if vals and isinstance(vals, list):
                display = ", ".join(str(v.get("value", v)) for v in vals)
            else:
                display = str(value.get("value"))
            print(f"  • {value.get('name')}: {display}")

    if not args.submit:
        print("\nPreview complete. Re-run with --submit to launch the container.")
        return

    launch_inputs = {
        "command": args.message,
        "output-file": args.output_file,
    }

    print("\nSubmitting launch request…")
    report = launch_container(
        session,
        args.base_url,
        args.wrapper_id,
        root_element,
        root_param,
        args.target_id,
        launch_inputs,
    )
    print("Launch response:", json.dumps(report, indent=2))

    if command_id_int is not None:
        print("Waiting for container record to appear …")
        time.sleep(3)
        try:
            containers = list(recent_containers(session, args.base_url, command_id_int, limit=5))
        except Exception as exc:  # noqa: BLE001
            print(f"Could not query containers: {exc}")
            return

        for container in containers:
            inputs = container.get("inputs") or []
            session_values = [
                entry.get("value")
                for entry in inputs
                if isinstance(entry, dict) and entry.get("name") == root_param
            ]
            if any(str(args.target_id) in str(val) for val in session_values):
                print("\nMost recent matching container:")
                print(json.dumps(container, indent=2))
                break
        else:
            print("No new container matching the target ID was found yet. Check the XNAT UI for updates.")


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as exc:
        print(f"HTTP error: {exc.response.status_code} {exc.response.text}", file=sys.stderr)
        sys.exit(1)
