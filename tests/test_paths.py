import os
import sys
import unittest
import tempfile
from unittest.mock import patch

# Ensure we can import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services import doctor_paths


class TestDoctorPaths(unittest.TestCase):

    def test_is_desktop_resources_path(self):
        """Test heuristic for distinguishing Desktop resources paths."""
        self.assertTrue(doctor_paths.is_desktop_resources_path("C:\\Program Files\\ComfyUI\\resources\\app\\custom_nodes"))
        self.assertTrue(doctor_paths.is_desktop_resources_path("/Applications/ComfyUI/resources/comfyui/custom_nodes"))
        self.assertTrue(doctor_paths.is_desktop_resources_path("C:\\Program Files\\ComfyUI\\resources\\app.asar\\dist"))
        self.assertFalse(doctor_paths.is_desktop_resources_path("C:\\Users\\Win\\ComfyUI\\custom_nodes"))
        self.assertFalse(doctor_paths.is_desktop_resources_path("/home/user/ComfyUI/user"))

    @patch('services.doctor_paths.folder_paths')
    def test_get_doctor_data_dir_priority_1(self, mock_folder_paths):
        """Test priority 1: folder_paths.get_user_directory() exists."""
        with tempfile.TemporaryDirectory() as temp_user_dir:
            mock_folder_paths.get_user_directory.return_value = temp_user_dir

            result = doctor_paths.get_doctor_data_dir()

            expected = os.path.join(temp_user_dir, "ComfyUI-Doctor")
            self.assertEqual(result, expected)
            self.assertTrue(os.path.exists(result))

    def test_get_doctor_data_dir_priority_2_portable_user_dir(self):
        """Test portable/git-clone fallback resolves to `<ComfyUI root>/user/ComfyUI-Doctor`."""
        with patch('services.doctor_paths.folder_paths', None):
            with tempfile.TemporaryDirectory() as fake_root:
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
        with patch('services.doctor_paths.folder_paths', None):
            with tempfile.TemporaryDirectory() as base_path:
                fake_python = os.path.join(base_path, '.venv', 'Scripts', 'python.exe')
                os.makedirs(os.path.dirname(fake_python), exist_ok=True)
                with open(fake_python, 'w', encoding='utf-8') as handle:
                    handle.write('')

                fake_doctor_paths_file = os.path.join(
                    base_path,
                    'resources',
                    'ComfyUI',
                    'custom_nodes',
                    'ComfyUI-Doctor',
                    'services',
                    'doctor_paths.py',
                )
                os.makedirs(os.path.dirname(fake_doctor_paths_file), exist_ok=True)

                with patch.object(doctor_paths.sys, 'executable', fake_python), \
                     patch.object(doctor_paths, '__file__', fake_doctor_paths_file):
                    result = doctor_paths.get_doctor_data_dir()
                    diagnostics = doctor_paths.get_path_diagnostics()

                expected = os.path.join(base_path, 'user', 'ComfyUI-Doctor')
                self.assertEqual(result, expected)
                self.assertEqual(diagnostics['install_mode'], 'desktop')
                self.assertEqual(diagnostics['source'], 'python_executable:.venv')

    def test_fallback_to_temp_if_nothing_works(self):
        with patch('services.doctor_paths.folder_paths', None):
            path = doctor_paths.get_doctor_data_dir()
            self.assertTrue(os.path.exists(path))
            self.assertIsInstance(path, str)


if __name__ == '__main__':
    unittest.main()
