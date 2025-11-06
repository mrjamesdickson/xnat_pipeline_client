from __future__ import annotations
from dataclasses import dataclass
import io
import json
import time
import zipfile
from typing import Any, Dict, Optional, TYPE_CHECKING, Iterable, List, Sequence

from ..containers import ContainerClient

if TYPE_CHECKING:
    from ..executor import JobHandle

@dataclass
class _RemoteJob:
    sess: Any
    routes: Dict[str, str]
    job: Dict[str, Any]
    io: Dict[str, Any]

    def _refresh(self):
        jid = self.job.get("id") or self.job.get("containerId")
        url = f"/xapi/containers/{jid}"
        r = self.sess.get(url)
        r.raise_for_status()
        self.job = r.json()

    def status(self) -> str:
        return (self.job.get("status") or self.job.get("state") or "Unknown")

    def wait(self, timeout: int = 3600, poll: float = 2.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            st = self.status().lower()
            if st in ("complete","completed","succeeded","done","failed","error","aborted"):
                return
            time.sleep(poll)
            self._refresh()
        raise TimeoutError("remote job did not finish in allotted time")

    def stdout_tail(self, n: int = 2000) -> str:
        jid = self.job.get("id") or self.job.get("containerId")
        url = f"/xapi/containers/{jid}/logs/stdout"
        r = self.sess.get(f"{url}?tail={n}")
        r.raise_for_status()
        data = r.content
        if data.startswith(b"PK"):
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for name in zf.namelist():
                    with zf.open(name) as fh:
                        return fh.read().decode("utf-8", errors="replace")[-n:]
            return ""
        text = data.decode("utf-8", errors="replace")
        return text.lstrip("".join(chr(i) for i in range(0, 32)))[-n:]

    def cancel(self) -> None:
        jid = self.job.get("id") or self.job.get("containerId")
        url = f"/xapi/containers/{jid}"
        r = self.sess.delete(url)
        r.raise_for_status()

class RemoteBackend:
    def __init__(self, xnat_session, routes: Optional[Dict[str, str]] = None, io: Optional[Dict[str, Any]] = None):
        self.xn = xnat_session
        self.routes = routes or {}
        self.io = io or {}

    _LEVEL_CONFIG: Dict[str, Dict[str, Any]] = {
        "project": {
            "xsi_types": {"xnat:projectData"},
            "root_element": "xnat:projectData",
            "param": "project",
        },
        "subject": {
            "xsi_types": {"xnat:subjectData"},
            "root_element": "xnat:subjectData",
            "param": "subject",
        },
        "experiment": {
            "xsi_types": {"xnat:imageSessionData"},
            "root_element": "xnat:imageSessionData",
            "param": "session",
        },
        "scan": {
            "xsi_types": {"xnat:imageScanData"},
            "root_element": "xnat:imageScanData",
            "param": "scan",
        },
        "assessor": {
            "xsi_types": {"xnat:imageAssessorData"},
            "root_element": "xnat:imageAssessorData",
            "param": "assessor",
        },
        "resource": {
            "xsi_types": {"xnat:resourceData", "xnat:resourceCatalog"},
            "root_element": "xnat:resourceData",
            "param": "resource",
        },
    }

    @staticmethod
    def _as_list(value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def _select_wrapper(self, cmd_raw: Dict[str, Any], level: str) -> Dict[str, Any]:
        config = self._LEVEL_CONFIG.get(level)
        if not config:
            raise ValueError(f"Unsupported context level {level!r}")

        wrappers: Sequence[Dict[str, Any]] = []
        for key in ("xnat", "xnat-command-wrappers", "xnatCommandWrappers", "wrappers"):
            raw = cmd_raw.get(key)
            if isinstance(raw, list):
                wrappers = raw  # type: ignore[assignment]
                break

        if not wrappers:
            raise ValueError("Command does not expose any wrappers in the XNAT metadata")

        for wrapper in wrappers:
            contexts = self._as_list(wrapper.get("contexts") or wrapper.get("context"))
            if any(ctx in config["xsi_types"] for ctx in contexts):
                return wrapper

        raise ValueError(f"No wrapper found for level {level!r} (expected contexts {config['xsi_types']})")

    def _make_launch_payload(self, level: str, context: Dict[str, str], inputs: Dict[str, Any]) -> Dict[str, str]:
        config = self._LEVEL_CONFIG[level]
        param_name = config["param"]
        level_id = context.get("id")
        if not level_id:
            raise ValueError("Context must include 'id'")

        payload: Dict[str, str] = {
            "context": param_name,
            param_name: level_id,
        }

        if inputs:
            payload["inputs"] = json.dumps(inputs)
            for key, value in inputs.items():
                if value is None:
                    continue
                if isinstance(value, (dict, list)):
                    payload[f"inputs.{key}"] = json.dumps(value)
                else:
                    payload[f"inputs.{key}"] = str(value)

        return payload

    def _containers_query(self, command_id: Optional[int] = None) -> List[Dict[str, Any]]:
        body: Dict[str, Any] = {
            "size": 50,
            "sort": [{"field": "id", "direction": "desc"}],
        }
        if command_id is not None:
            body["filter"] = {"command-id": command_id}

        try:
            resp = self.xn.post("/xapi/containers", json=body)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                items = data.get("items") or data.get("containers") or data.get("ResultSet", {}).get("Result")
                if isinstance(items, list):
                    return items
            return []
        except Exception as exc:
            raise RuntimeError(f"Failed to query containers: {exc}") from exc

    @staticmethod
    def _container_matches(container: Dict[str, Any], param_name: str, level_id: str) -> bool:
        inputs = container.get("inputs")
        if not isinstance(inputs, Iterable):
            return False
        for entry in inputs:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            value = entry.get("value")
            if name == param_name:
                if isinstance(value, str):
                    if value == level_id or value.endswith(f"/{level_id}"):
                        return True
        return False

    def _await_container(self, command_id: Optional[int], param_name: str, level_id: str, seen_ids: Sequence[str], timeout: int = 120) -> Dict[str, Any]:
        deadline = time.time() + timeout
        known = set(seen_ids)
        while time.time() < deadline:
            try:
                containers = self._containers_query(command_id=command_id)
            except RuntimeError:
                containers = []

            for container in containers:
                cid = container.get("id") or container.get("container-id") or container.get("containerId")
                if cid is None:
                    continue
                cid_str = str(cid)
                if cid_str in known:
                    continue
                if self._container_matches(container, param_name, level_id):
                    return container
            time.sleep(2.0)
        raise TimeoutError("Launch acknowledged but container record did not appear in time")

    def run(self, command_ref: str, context: Dict[str, str], inputs: Dict[str, Any]) -> "JobHandle":
        from ..executor import JobHandle

        cc = ContainerClient.from_xnat(self.xn, routes=self.routes)
        cmd = cc.get_command(command_ref)
        level = context.get("level")
        if not level:
            raise ValueError("Context must include 'level'")

        wrapper = self._select_wrapper(cmd.raw, level)
        wrapper_id = wrapper.get("id") or wrapper.get("wrapper-id") or wrapper.get("wrapperId")
        if wrapper_id is None:
            raise ValueError("Wrapper is missing an identifier")

        config = self._LEVEL_CONFIG[level]
        root_element = wrapper.get("root-element") or wrapper.get("rootElement") or config["root_element"]
        if not isinstance(root_element, str):
            root_element = config["root_element"]

        launch_url = f"/xapi/wrappers/{wrapper_id}/root/{root_element}/launch"

        try:
            command_id_int = int(cmd.id)
        except (TypeError, ValueError):
            command_id_int = None

        existing = self._containers_query(command_id=command_id_int)
        existing_ids = [
            str(item.get("id") or item.get("container-id") or item.get("containerId"))
            for item in existing
            if item.get("id") or item.get("container-id") or item.get("containerId")
        ]

        form_payload = self._make_launch_payload(level, context, inputs)
        response = self.xn.post(launch_url, data=form_payload)
        response.raise_for_status()

        level_id = context["id"]
        try:
            container = self._await_container(command_id_int, self._LEVEL_CONFIG[level]["param"], level_id, existing_ids)
        except TimeoutError as exc:
            raise RuntimeError("Launch accepted but container record was not created within the timeout window") from exc

        return JobHandle(
            backend="remote",
            job_id=str(container.get("id") or container.get("container-id") or container.get("containerId")),
            _impl=_RemoteJob(self.xn, self.routes, container, self.io),
        )
