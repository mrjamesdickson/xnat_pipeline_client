from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from xnat_pipelines.backends.remote import RemoteBackend


class DummySession(SimpleNamespace):
    """Session stub; only methods patched in tests are invoked."""


def make_backend() -> RemoteBackend:
    return RemoteBackend(xnat_session=DummySession())


class RemoteBackendTests(unittest.TestCase):
    def test_make_launch_payload_includes_context_and_inputs(self) -> None:
        backend = make_backend()
        context = {"level": "scan", "id": "SCAN123"}
        inputs = {"command": "echo hello", "bids": "y"}

        payload = backend._make_launch_payload("scan", context, inputs)

        self.assertEqual(payload["context"], "scan")
        self.assertEqual(payload["scan"], "SCAN123")
        self.assertEqual(json.loads(payload["inputs"]), inputs)
        self.assertEqual(payload["inputs.command"], "echo hello")
        self.assertEqual(payload["inputs.bids"], "y")

    def test_select_wrapper_matches_level_context(self) -> None:
        backend = make_backend()
        cmd_raw = {
            "xnat": [
                {"id": 13, "contexts": ["xnat:imageScanData"]},
                {"id": 70, "contexts": ["xnat:imageSessionData"]},
            ]
        }

        wrapper = backend._select_wrapper(cmd_raw, "scan")
        self.assertEqual(wrapper["id"], 13)

    def test_select_wrapper_raises_for_unknown_level(self) -> None:
        backend = make_backend()
        cmd_raw = {"xnat": [{"id": 13, "contexts": ["xnat:imageSessionData"]}]}

        with self.assertRaises(ValueError):
            backend._select_wrapper(cmd_raw, "scan")

    def test_container_matches_handles_archive_suffix(self) -> None:
        container = {
            "inputs": [
                {"name": "scan", "value": "/archive/experiments/X1/scans/2"},
            ]
        }
        self.assertTrue(RemoteBackend._container_matches(container, "scan", "2"))

    def test_await_container_returns_first_matching_entry(self) -> None:
        backend = make_backend()
        container = {
            "id": 101,
            "inputs": [
                {"name": "scan", "value": "/archive/experiments/X1/scans/2"},
            ],
        }

        backend._containers_query = lambda command_id: [container]  # type: ignore[assignment]

        result = backend._await_container(
            command_id=7,
            param_name="scan",
            level_id="2",
            seen_ids=[],
            timeout=5,
        )

        self.assertEqual(result, container)


if __name__ == "__main__":
    unittest.main()
