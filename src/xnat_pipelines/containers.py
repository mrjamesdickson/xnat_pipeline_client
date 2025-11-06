from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

DEFAULT_ROUTES = {
    "commands": "/xapi/commands",
    "command_detail": "/xapi/commands/{command_id}",
}

@dataclass
class ContainerCommand:
    id: str
    name: str
    version: str
    image: str
    raw: Dict[str, Any]

    def __repr__(self) -> str:
        return f"<ContainerCommand id={self.id!r} name={self.name!r} version={self.version!r} image={self.image!r}>"

class ContainerClient:
    def __init__(self, requests_session, routes: Optional[Dict[str, str]] = None):
        self.sess = requests_session
        self.routes = {**DEFAULT_ROUTES, **(routes or {})}

    @classmethod
    def from_xnat(cls, xnat_session, routes: Optional[Dict[str, str]] = None) -> "ContainerClient":
        # Pass the xnat session itself - it has .get()/.post() methods
        return cls(xnat_session, routes)

    def list_commands(self) -> List[ContainerCommand]:
        r = self.sess.get(self.routes["commands"])
        r.raise_for_status()
        items = r.json()
        cmds: List[ContainerCommand] = []
        for c in items:
            cmds.append(ContainerCommand(
                id=str(c.get("id") or c.get("name")),
                name=c.get("name", ""),
                version=c.get("version", ""),
                image=c.get("image") or c.get("docker_image") or "",
                raw=c,
            ))
        return cmds

    def get_command(self, name_or_id: str) -> ContainerCommand:
        for c in self.list_commands():
            if c.id == name_or_id or c.name == name_or_id:
                return c
        raise KeyError(f"Command {name_or_id!r} not found")
