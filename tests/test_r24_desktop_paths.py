import os
import sys
from unittest.mock import patch

import system_info
from services import doctor_paths


def _fake_desktop_python(base_path: str) -> str:
    return os.path.join(base_path, '.venv', 'bin', 'python')


def test_system_environment_reports_desktop_runtime(tmp_path):
    base_path = str(tmp_path / 'ComfyUI')
    fake_python = _fake_desktop_python(base_path)
    os.makedirs(os.path.dirname(fake_python), exist_ok=True)

    with patch('services.doctor_paths.folder_paths', None), \
         patch.object(doctor_paths.sys, 'executable', fake_python), \
         patch.object(system_info.sys, 'executable', fake_python), \
         patch('system_info._run_pip_list', return_value=''), \
         patch('system_info._get_torch_info', return_value={
             'pytorch_version': None,
             'cuda_available': False,
             'cuda_version': None,
             'gpu_count': 0,
         }):
        system_info.clear_cache()
        info = system_info.get_system_environment(force_refresh=True)

    assert info['environment_type'] == 'desktop'
    assert info['runtime_layout_source'] == 'python_executable:.venv'

    canonical = system_info.canonicalize_system_info(info)
    assert canonical['environment_type'] == 'desktop'
    assert canonical['runtime_layout_source'] == 'python_executable:.venv'


def test_format_env_for_llm_includes_environment_type():
    env_info = {
        'os': 'Windows 11',
        'python_version': '3.12.0',
        'environment_type': 'desktop',
        'pytorch_info': {
            'pytorch_version': None,
            'cuda_available': False,
            'cuda_version': None,
            'gpu_count': 0,
        },
        'installed_packages': '',
        'cache_age_seconds': 0,
    }

    formatted = system_info.format_env_for_llm(env_info)
    assert 'Environment: desktop' in formatted
