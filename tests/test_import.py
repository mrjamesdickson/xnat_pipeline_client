def test_version_matches_package():
    import xnat_pipelines

    assert xnat_pipelines.__version__ == "1.0.0"
