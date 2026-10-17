"""Task-runner regressions; standard library only so these also run on Windows."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import dev


class TaskTests(unittest.TestCase):
    def test_run_resolves_windows_command_shims_and_preserves_arguments(self):
        with (
            patch.object(dev.shutil, "which", return_value=r"C:\Program Files\nodejs\npm.cmd"),
            patch.object(dev.subprocess, "run") as invoke,
        ):
            dev.run("npm", "run", "build")
        self.assertEqual(
            invoke.call_args.args[0], [r"C:\Program Files\nodejs\npm.cmd", "run", "build"]
        )
        self.assertNotIn("shell", invoke.call_args.kwargs)

    def test_missing_tool_has_actionable_error(self):
        with patch.object(dev.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Missing executable: initdb"):
                dev.run("initdb")

    def test_install_preserves_existing_env(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("SECRET=keep-me\n")
            (root / ".env.example").write_text("SECRET=example\n")
            with patch.object(dev, "ROOT", root), patch.object(dev, "run") as invoke:
                dev.task("install")
            self.assertEqual((root / ".env").read_text(), "SECRET=keep-me\n")
            self.assertEqual(invoke.call_count, 3)

    def test_install_copies_missing_env(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env.example").write_text("EMAIL_MODE=disabled\n")
            with patch.object(dev, "ROOT", root), patch.object(dev, "run"):
                dev.task("install")
            self.assertEqual((root / ".env").read_text(), "EMAIL_MODE=disabled\n")

    def test_lock_is_universal_for_both_requirement_files(self):
        with patch.object(dev, "run") as invoke:
            dev.task("lock")
        self.assertEqual(invoke.call_count, 2)
        for call in invoke.call_args_list:
            self.assertIn("--universal", call.args)

    def test_backend_uses_virtualenv_module_and_explicit_import_path(self):
        with patch.object(dev, "run") as invoke:
            dev.task("backend")
        self.assertEqual(invoke.call_args.args[:4], (dev.PYTHON, "-m", "uvicorn", "iou.api:app"))
        self.assertEqual(
            invoke.call_args.kwargs["env"]["PYTHONPATH"], str(dev.ROOT / "backend/src")
        )

    def test_migration_requires_message_and_passes_it_as_one_argument(self):
        with self.assertRaisesRegex(RuntimeError, "--message"):
            dev.task("migration")
        with patch.object(dev, "run") as invoke:
            dev.task("migration", 'add "loan items"')
        self.assertEqual(invoke.call_args.args[-1], 'add "loan items"')

    def test_database_requires_initialized_cluster(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(dev, "DATA", Path(directory) / "data"):
                with self.assertRaisesRegex(RuntimeError, "db-init"):
                    dev.database("db-start")

    def test_database_init_preserves_existing_cluster(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            (data / "PG_VERSION").write_text("17")
            with patch.object(dev, "DATA", data), patch.object(dev, "run") as invoke:
                dev.database("db-init")
            invoke.assert_not_called()

    def test_database_rejects_unrelated_server(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "project data"
            data.mkdir()
            (data / "PG_VERSION").write_text("17")
            results = [
                subprocess.CompletedProcess([], 0),  # project cluster reports running
                subprocess.CompletedProcess([], 0, stdout=str(Path(directory) / "other data")),
            ]
            with patch.object(dev, "DATA", data), patch.object(dev, "run", side_effect=results):
                with self.assertRaisesRegex(RuntimeError, "refusing to proceed"):
                    dev.database("db-start")

    def test_database_start_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            (data / "PG_VERSION").write_text("17")
            results = [
                subprocess.CompletedProcess([], 0),
                subprocess.CompletedProcess([], 0, stdout=str(data)),
                subprocess.CompletedProcess([], 0, stdout="1\n"),
            ]
            with (
                patch.object(dev, "DATA", data),
                patch.object(dev, "run", side_effect=results) as invoke,
            ):
                dev.database("db-start")
            self.assertEqual(invoke.call_count, 3)


if __name__ == "__main__":
    unittest.main()
