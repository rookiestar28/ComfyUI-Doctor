import json
from pathlib import Path

import logger


def test_legacy_history_migration_creates_backup_marker(monkeypatch, tmp_path):
    """
    T13: verify logger legacy migration copies to canonical path and renames source
    to `.migrated-<timestamp>`.
    """
    legacy_root = tmp_path / "legacy_ext"
    legacy_logs = legacy_root / "logs"
    legacy_logs.mkdir(parents=True)
    legacy_file = legacy_logs / "error_history.json"
    legacy_payload = [{"error": "legacy"}]
    legacy_file.write_text(json.dumps(legacy_payload), encoding="utf-8")

    target_dir = tmp_path / "doctor_data"
    target_file = target_dir / "error_history.json"

    monkeypatch.setattr(logger, "doctor_paths", object())
    monkeypatch.setattr(logger, "_current_dir", str(legacy_root))
    monkeypatch.setattr(logger, "_history_file", str(target_file))

    logger._migrate_legacy_data()

    assert target_file.exists()
    migrated_payload = json.loads(target_file.read_text(encoding="utf-8"))
    assert migrated_payload == legacy_payload

    backups = list(legacy_logs.glob("error_history.json.migrated-*"))
    assert len(backups) == 1
    assert not legacy_file.exists()
