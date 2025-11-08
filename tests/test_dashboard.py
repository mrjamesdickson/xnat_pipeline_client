import json
import time

from xnat_pipelines.dashboard import scan_runs


def test_scan_runs_classifies_statuses(tmp_path):
    run1 = tmp_path / "run_100"
    run1.mkdir()
    (run1 / "run.json").write_text(json.dumps({"context": {"id": "E1"}, "cmd": ["cmd"]}))
    (run1 / "run.log").write_text("DRY RUN\npreview only")

    run2 = tmp_path / "run_200"
    run2.mkdir()
    (run2 / "run.json").write_text(json.dumps({"context": {"id": "E2"}, "cmd": ["cmd"]}))
    (run2 / "run.log").write_text("CMD: docker run...\nComplete\n")

    run3 = tmp_path / "run_300"
    run3.mkdir()
    (run3 / "run.json").write_text(json.dumps({"context": {"id": "E3"}, "cmd": ["cmd"]}))
    (run3 / "run.log").write_text("CMD: docker run...\ntraceback...\nerror happened\n")

    runs, counts = scan_runs(tmp_path)

    statuses = {r["context"]["id"]: r["status"] for r in runs}
    assert statuses["E1"] == "Prepared"
    assert statuses["E2"] == "Complete"
    assert statuses["E3"] == "Failed"

    assert counts["total"] == 3
    assert counts["complete"] == 1
    assert counts["failed"] == 1
