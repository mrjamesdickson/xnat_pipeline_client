from pathlib import Path
from types import SimpleNamespace

from xnat_pipelines.io_utils import stage_from_xnat, upload_outputs_to_xnat


class FakeFile:
    def __init__(self, label, data="data"):
        self.label = label
        self._data = data
        self.downloads = []

    def download(self, path: str):
        Path(path).write_text(self._data)
        self.downloads.append(path)


class FakeResource:
    def __init__(self, label, files):
        self.label = label
        self.files = files
        self.uploads = []

    def upload(self, path, name):
        self.uploads.append((path, name))


class FakeExperiment:
    def __init__(self, resources):
        self.resources = resources

    def create_resource(self, name):
        res = FakeResource(name, {})
        self.resources[name] = res
        return res


def test_stage_from_xnat_downloads_filtered(tmp_path):
    files = {
        "a.dcm": FakeFile("a.dcm", "dicom"),
        "b.txt": FakeFile("b.txt", "text"),
    }
    resources = {"DICOM": FakeResource("DICOM", files)}
    exp = FakeExperiment(resources)
    xn = SimpleNamespace(experiments={"EXP1": exp})

    run_dir = tmp_path / "run"
    run_dir.mkdir()

    stage_from_xnat(
        xn,
        {"level": "experiment", "id": "EXP1"},
        run_dir,
        resource_filters={"resource_names": ["DICOM"], "patterns": ["*.dcm"]},
    )

    assert (run_dir / "input" / "a.dcm").read_text() == "dicom"
    assert not (run_dir / "input" / "b.txt").exists()


def test_upload_outputs_to_xnat_creates_resource(tmp_path):
    exp = FakeExperiment(resources={})
    xn = SimpleNamespace(experiments={"EXP9": exp})

    run_dir = tmp_path / "run"
    output_dir = run_dir / "output"
    output_dir.mkdir(parents=True)
    (output_dir / "result.txt").write_text("hello")

    artifact = upload_outputs_to_xnat(
        xn,
        {"level": "experiment", "id": "EXP9"},
        run_dir,
        resource_name="processed",
    )

    assert artifact == "experiment:EXP9/resource:processed"
    resource = exp.resources["processed"]
    assert resource.uploads[0][1] == "result.txt"
