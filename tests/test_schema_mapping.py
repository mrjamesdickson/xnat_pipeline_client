from xnat_pipelines import schema_mapping


def test_map_inputs_and_mounts_handles_args_env_and_defaults():
    cmd_raw = {
        "inputs": [
            {"name": "message", "arg": "--message"},
            {"name": "sleep", "env": "SLEEP_SECS", "default": 5},
            {"name": "should_fail"},
        ]
    }
    user_inputs = {"message": "hi", "should_fail": False}

    extra_args, env_map = schema_mapping.map_inputs_and_mounts(cmd_raw, user_inputs)

    assert extra_args == ["--message", "hi"]
    assert env_map == {"SLEEP_SECS": "5", "SHOULD_FAIL": "False"}


def test_resolve_mounts_falls_back_to_defaults():
    in_mnt, out_mnt = schema_mapping.resolve_mounts({})
    assert in_mnt == "/input"
    assert out_mnt == "/output"

    overrides = {"mounts": {"input": "/data/in", "output": "/data/out"}}
    assert schema_mapping.resolve_mounts(overrides) == ("/data/in", "/data/out")
