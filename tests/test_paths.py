import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

# Ensure we can import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services import doctor_paths


class TestDoctorPaths(unittest.TestCase):
    def test_is_desktop_resources_path(self):
        """Test heuristic for distinguishing Desktop resources paths."""
        self.assertTrue(
            doctor_paths.is_desktop_resources_path("C:\\Program Files\\ComfyUI\\resources\\app\\custom_nodes")
        )
        self.assertTrue(doctor_paths.is_desktop_resources_path("/Applications/ComfyUI/resources/comfyui/custom_nodes"))
        self.assertTrue(doctor_paths.is_desktop_resources_path("C:\\Program Files\\ComfyUI\\resources\\app.asar\\dist"))
        self.assertFalse(doctor_paths.is_desktop_resources_path("C:\\Users\\Win\\ComfyUI\\custom_nodes"))
        self.assertFalse(doctor_paths.is_desktop_resources_path("/home/user/ComfyUI/user"))

    def test_get_doctor_data_dir_priority_1_system_user(self):
        """Current ComfyUI hosts should use the private system-user directory."""
        with tempfile.TemporaryDirectory() as temp_user_dir:
            system_user_dir = os.path.join(temp_user_dir, "__comfyui_doctor")
            folder_paths = SimpleNamespace(
                get_system_user_directory=lambda name: system_user_dir,
                get_user_directory=lambda: temp_user_dir,
            )

            with patch("services.doctor_paths.folder_paths", folder_paths):
                result = doctor_paths.get_doctor_data_dir()
                diagnostics = doctor_paths.get_path_diagnostics()

            self.assertEqual(result, system_user_dir)
            self.assertEqual(diagnostics["folder_system_user_directory"], system_user_dir)
            self.assertEqual(diagnostics["source"], "folder_paths.get_system_user_directory")
            self.assertTrue(os.path.exists(result))

    def test_get_doctor_data_dir_legacy_user_fallback_without_system_user(self):
        """Older ComfyUI hosts without get_system_user_directory keep the legacy path."""
        with tempfile.TemporaryDirectory() as temp_user_dir:
            folder_paths = SimpleNamespace(get_user_directory=lambda: temp_user_dir)

            with patch("services.doctor_paths.folder_paths", folder_paths):
                result = doctor_paths.get_doctor_data_dir()
                diagnostics = doctor_paths.get_path_diagnostics()

            expected = os.path.join(temp_user_dir, "ComfyUI-Doctor")
            self.assertEqual(result, expected)
            self.assertEqual(diagnostics["folder_user_directory"], temp_user_dir)
            self.assertEqual(diagnostics["source"], "folder_paths.get_user_directory")
            self.assertTrue(os.path.exists(result))

    def test_get_doctor_data_dir_migrates_legacy_state_without_overwrite(self):
        """Existing legacy state is copied to the system-user path without replacing files."""
        with tempfile.TemporaryDirectory() as temp_user_dir:
            legacy_dir = os.path.join(temp_user_dir, "ComfyUI-Doctor")
            system_user_dir = os.path.join(temp_user_dir, "__comfyui_doctor")
            os.makedirs(os.path.join(legacy_dir, "nested"), exist_ok=True)
            os.makedirs(system_user_dir, exist_ok=True)
            with open(os.path.join(legacy_dir, "history.json"), "w", encoding="utf-8") as handle:
                handle.write("legacy")
            with open(os.path.join(legacy_dir, "nested", "state.json"), "w", encoding="utf-8") as handle:
                handle.write("nested")
            with open(os.path.join(system_user_dir, "history.json"), "w", encoding="utf-8") as handle:
                handle.write("current")

            folder_paths = SimpleNamespace(
                get_system_user_directory=lambda name: system_user_dir,
                get_user_directory=lambda: temp_user_dir,
            )

            with patch("services.doctor_paths.folder_paths", folder_paths):
                result = doctor_paths.get_doctor_data_dir()

            self.assertEqual(result, system_user_dir)
            with open(os.path.join(system_user_dir, "history.json"), encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "current")
            with open(os.path.join(system_user_dir, "nested", "state.json"), encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "nested")

    def test_get_doctor_data_dir_migration_skips_symlinks(self):
        """Legacy symlinks must not be followed into private state migration."""
        if not hasattr(os, "symlink"):
            self.skipTest("symlink support is unavailable")

        with tempfile.TemporaryDirectory() as temp_user_dir:
            legacy_dir = os.path.join(temp_user_dir, "ComfyUI-Doctor")
            system_user_dir = os.path.join(temp_user_dir, "__comfyui_doctor")
            os.makedirs(legacy_dir, exist_ok=True)
            os.makedirs(system_user_dir, exist_ok=True)
            target_file = os.path.join(temp_user_dir, "outside.txt")
            with open(target_file, "w", encoding="utf-8") as handle:
                handle.write("outside")
            link_path = os.path.join(legacy_dir, "linked.txt")
            try:
                os.symlink(target_file, link_path)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")

            folder_paths = SimpleNamespace(
                get_system_user_directory=lambda name: system_user_dir,
                get_user_directory=lambda: temp_user_dir,
            )

            with patch("services.doctor_paths.folder_paths", folder_paths):
                result = doctor_paths.get_doctor_data_dir()

            self.assertEqual(result, system_user_dir)
            self.assertFalse(os.path.exists(os.path.join(system_user_dir, "linked.txt")))

    def test_get_doctor_data_dir_priority_2_portable_user_dir(self):
        """Test portable/git-clone fallback resolves to `<ComfyUI root>/user/ComfyUI-Doctor`."""
        with patch("services.doctor_paths.folder_paths", None), tempfile.TemporaryDirectory() as fake_root:
            comfy_root = os.path.join(fake_root, "ComfyUI")
            comfy_doctor_services = os.path.join(comfy_root, "custom_nodes", "ComfyUI-Doctor", "services")
            os.makedirs(comfy_doctor_services, exist_ok=True)

            fake_doctor_paths_file = os.path.join(comfy_doctor_services, "doctor_paths.py")
            with patch.object(doctor_paths, "__file__", fake_doctor_paths_file):
                result = doctor_paths.get_doctor_data_dir()

            expected = os.path.join(comfy_root, "user", "ComfyUI-Doctor")
            self.assertEqual(result, expected)
            self.assertTrue(os.path.exists(result))

    def test_get_doctor_data_dir_desktop_venv_fallback(self):
        """Desktop `.venv` layout should map back to `<basePath>/user/ComfyUI-Doctor`."""
        with patch("services.doctor_paths.folder_paths", None), tempfile.TemporaryDirectory() as base_path:
            fake_python = os.path.join(base_path, ".venv", "Scripts", "python.exe")
            os.makedirs(os.path.dirname(fake_python), exist_ok=True)
            with open(fake_python, "w", encoding="utf-8") as handle:
                handle.write("")

            fake_doctor_paths_file = os.path.join(
                base_path,
                "resources",
                "ComfyUI",
                "custom_nodes",
                "ComfyUI-Doctor",
                "services",
                "doctor_paths.py",
            )
            os.makedirs(os.path.dirname(fake_doctor_paths_file), exist_ok=True)

            with (
                patch.object(doctor_paths.sys, "executable", fake_python),
                patch.object(doctor_paths, "__file__", fake_doctor_paths_file),
            ):
                result = doctor_paths.get_doctor_data_dir()
                diagnostics = doctor_paths.get_path_diagnostics()

            expected = os.path.join(base_path, "user", "ComfyUI-Doctor")
            self.assertEqual(result, expected)
            self.assertEqual(diagnostics["install_mode"], "desktop")
            self.assertEqual(diagnostics["source"], "python_executable:.venv")

    def test_get_doctor_data_dir_desktop_system_user_when_host_exposes_api(self):
        """Desktop user-directory layouts should resolve to the private system-user path on current hosts."""
        with tempfile.TemporaryDirectory() as base_path:
            user_dir = os.path.join(base_path, "user")
            system_user_dir = os.path.join(user_dir, "__comfyui_doctor")
            fake_python = os.path.join(base_path, ".venv", "Scripts", "python.exe")
            os.makedirs(os.path.dirname(fake_python), exist_ok=True)
            with open(fake_python, "w", encoding="utf-8") as handle:
                handle.write("")

            folder_paths = SimpleNamespace(
                get_system_user_directory=lambda name: system_user_dir,
                get_user_directory=lambda: user_dir,
            )

            with (
                patch("services.doctor_paths.folder_paths", folder_paths),
                patch.object(doctor_paths.sys, "executable", fake_python),
            ):
                result = doctor_paths.get_doctor_data_dir()
                diagnostics = doctor_paths.get_path_diagnostics()

            self.assertEqual(result, system_user_dir)
            self.assertEqual(diagnostics["install_mode"], "standard")
            self.assertEqual(diagnostics["source"], "folder_paths.get_system_user_directory")

    def test_portable_custom_nodes_beats_repo_venv_heuristic(self):
        """Portable custom_nodes layout should win even when the active Python lives in repo-local `.venv`."""
        with patch("services.doctor_paths.folder_paths", None), tempfile.TemporaryDirectory() as fake_root:
            comfy_root = os.path.join(fake_root, "ComfyUI")
            extension_root = os.path.join(comfy_root, "custom_nodes", "ComfyUI-Doctor")
            fake_python = os.path.join(extension_root, ".venv", "Scripts", "python.exe")
            os.makedirs(os.path.dirname(fake_python), exist_ok=True)
            with open(fake_python, "w", encoding="utf-8") as handle:
                handle.write("")

            fake_doctor_paths_file = os.path.join(
                extension_root,
                "services",
                "doctor_paths.py",
            )
            os.makedirs(os.path.dirname(fake_doctor_paths_file), exist_ok=True)

            with (
                patch.object(doctor_paths.sys, "executable", fake_python),
                patch.object(doctor_paths, "__file__", fake_doctor_paths_file),
            ):
                result = doctor_paths.get_doctor_data_dir()
                diagnostics = doctor_paths.get_path_diagnostics()

            expected = os.path.join(comfy_root, "user", "ComfyUI-Doctor")
            self.assertEqual(result, expected)
            self.assertEqual(diagnostics["install_mode"], "portable_or_git")
            self.assertEqual(diagnostics["source"], "extension_layout:custom_nodes")

    def test_fallback_to_temp_if_nothing_works(self):
        with patch("services.doctor_paths.folder_paths", None):
            path = doctor_paths.get_doctor_data_dir()
            self.assertTrue(os.path.exists(path))
            self.assertIsInstance(path, str)


if __name__ == "__main__":
    unittest.main()
