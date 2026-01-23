
import os
import sys
import unittest
import tempfile
from unittest.mock import MagicMock, patch

# Ensure we can import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services import doctor_paths

class TestDoctorPaths(unittest.TestCase):
    
    def test_is_desktop_resources_path(self):
        """Test heuristic for distinguishing Desktop resources paths."""
        self.assertTrue(doctor_paths.is_desktop_resources_path("C:\\Program Files\\ComfyUI\\resources\\app\\custom_nodes"))
        self.assertTrue(doctor_paths.is_desktop_resources_path("/Applications/ComfyUI/resources/comfyui/custom_nodes"))
        self.assertFalse(doctor_paths.is_desktop_resources_path("C:\\Users\\Win\\ComfyUI\\custom_nodes"))
        self.assertFalse(doctor_paths.is_desktop_resources_path("/home/user/ComfyUI/user_data"))

    @patch('services.doctor_paths.folder_paths')
    def test_get_doctor_data_dir_priority_1(self, mock_folder_paths):
        """Test priority 1: folder_paths.get_user_directory() exists."""
        # Setup mock
        with tempfile.TemporaryDirectory() as temp_user_dir:
            mock_folder_paths.get_user_directory.return_value = temp_user_dir
            
            result = doctor_paths.get_doctor_data_dir()
            
            expected = os.path.join(temp_user_dir, "ComfyUI-Doctor")
            self.assertEqual(result, expected)
            self.assertTrue(os.path.exists(result))

    def test_get_doctor_data_dir_priority_2(self):
        """Test priority 2: Sibling user_data (when folder_paths is missing/fails)."""
        with patch('services.doctor_paths.folder_paths', None):
            with tempfile.TemporaryDirectory() as fake_root:
                # Simulated layout:
                # fake_root/ComfyUI/custom_nodes/ComfyUI-Doctor/services/doctor_paths.py
                comfy_root = os.path.join(fake_root, "ComfyUI")
                comfy_doctor_services = os.path.join(comfy_root, "custom_nodes", "ComfyUI-Doctor", "services")
                os.makedirs(comfy_doctor_services, exist_ok=True)

                # Patch module __file__ so doctor_paths can resolve comfy_root via relative traversal.
                fake_doctor_paths_file = os.path.join(comfy_doctor_services, "doctor_paths.py")
                with patch.object(doctor_paths, "__file__", fake_doctor_paths_file):
                    result = doctor_paths.get_doctor_data_dir()

                expected = os.path.join(comfy_root, "user_data", "ComfyUI-Doctor")
                self.assertEqual(result, expected)
                self.assertTrue(os.path.exists(result))

    def test_fallback_to_temp_if_nothing_works(self):
        with patch('services.doctor_paths.folder_paths', None):
            # Also make sure the relative path calculation doesn't crash or ends up somewhere writable
            # If we are running tests, __file__ exists.
            
            path = doctor_paths.get_doctor_data_dir()
            self.assertTrue(os.path.exists(path))
            # It should be either a user_data sibling or temp.
            # Just asserting it returns a string and exists is a good smoke test.
            self.assertIsInstance(path, str)

if __name__ == '__main__':
    unittest.main()
