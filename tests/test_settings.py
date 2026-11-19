from riad_data import settings


def test_env_file_then_environment_wins(tmp_path):
    env = tmp_path / ".env"
    env.write_text('# comment\nFABRIC_LAKEHOUSE=from-file\nTENANT_ID="t-file"\n')
    values = settings.load(env, {"TENANT_ID": "t-env"})
    assert values["FABRIC_LAKEHOUSE"] == "from-file"
    assert values["TENANT_ID"] == "t-env"
    assert values["FABRIC_WORKSPACE"] == "margin-copilot"


def test_missing_settings_stop_with_their_names(tmp_path):
    values = settings.load(tmp_path / "absent.env", {})
    try:
        settings.require(values, "TENANT_ID", "FABRIC_WORKSPACE")
    except SystemExit as stop:
        assert "TENANT_ID" in str(stop) and "FABRIC_WORKSPACE" not in str(stop)
    else:
        raise AssertionError("expected SystemExit")


def test_only_known_settings_are_taken_from_the_environment(tmp_path):
    values = settings.load(tmp_path / "absent.env", {"PATH": "/bin", "TENANT_ID": "t"})
    assert "PATH" not in values and values["TENANT_ID"] == "t"
