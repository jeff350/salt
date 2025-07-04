import json
import os

import pytest

from salt.utils.versions import Version
from tests.support.helpers import SaltVirtualEnv
from tests.support.pytest.helpers import FakeSaltExtension
from tests.support.runtests import RUNTIME_VARS

MISSING_SETUP_PY_FILE = not os.path.exists(
    os.path.join(RUNTIME_VARS.CODE_DIR, "setup.py")
)

pytestmark = [
    # These are slow because they create a virtualenv and install salt in it
    pytest.mark.slow_test,
    pytest.mark.timeout_unless_on_windows(240),
    pytest.mark.skipif(
        MISSING_SETUP_PY_FILE, reason="This test only work if setup.py is available"
    ),
]


@pytest.fixture(scope="module")
def salt_extension(tmp_path_factory):
    with FakeSaltExtension(
        tmp_path_factory=tmp_path_factory, name="salt-ext-loader-test"
    ) as extension:
        yield extension


@pytest.fixture
def venv(tmp_path):
    with SaltVirtualEnv(
        venv_dir=tmp_path / ".venv", system_site_packages=True
    ) as _venv:
        yield _venv


@pytest.fixture
def module_dirs(tmp_path):
    module_dir = tmp_path / "module-dir-base"
    module_dir.joinpath("modules").mkdir(parents=True)
    return [str(module_dir)]


def test_module_dirs_priority(venv, salt_extension, minion_opts, module_dirs):
    # Install our extension into the virtualenv
    venv.install(str(salt_extension.srcdir))
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name in installed_packages
    code = """
    import sys
    import json
    import salt._logging
    import salt.loader

    minion_config = json.loads(sys.stdin.read())
    salt._logging.set_logging_options_dict(minion_config)
    salt._logging.setup_logging()
    mod_dirs = salt.loader._module_dirs(minion_config, "modules", "module")
    print(json.dumps(mod_dirs))
    """
    minion_opts["module_dirs"] = module_dirs
    ret = venv.run_code(code, input=json.dumps(minion_opts))
    module_dirs_return = json.loads(ret.stdout)
    assert len(module_dirs_return) == 5
    for i, tail in enumerate(
        [
            "/module-dir-base/modules",
            "/var/cache/salt/minion/extmods/modules",
            "/module-dir-base",
            "/site-packages/salt_ext_loader_test/modules",
            "/site-packages/salt/modules",
        ]
    ):
        assert module_dirs_return[i].endswith(
            tail
        ), f"{module_dirs_return[i]} does not end with {tail}"

    # Test the deprecated mode as well
    minion_opts["features"] = {"enable_deprecated_module_search_path_priority": True}
    ret = venv.run_code(code, input=json.dumps(minion_opts))
    module_dirs_return = json.loads(ret.stdout)
    assert len(module_dirs_return) == 5
    for i, tail in enumerate(
        [
            "/module-dir-base/modules",
            "/module-dir-base",
            "/site-packages/salt_ext_loader_test/modules",
            "/var/cache/salt/minion/extmods/modules",
            "/site-packages/salt/modules",
        ]
    ):
        assert module_dirs_return[i].endswith(
            tail
        ), f"{module_dirs_return[i]} does not end with {tail}"


def test_new_entry_points_passing_module(venv, salt_extension, salt_minion_factory):
    # Install our extension into the virtualenv
    venv.install(str(salt_extension.srcdir))
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name in installed_packages
    code = """
    import sys
    import json
    import salt._logging
    import salt.loader

    minion_config = json.loads(sys.stdin.read())
    salt._logging.set_logging_options_dict(minion_config)
    salt._logging.setup_logging()
    loader = salt.loader.minion_mods(minion_config)
    print(json.dumps(list(loader)))
    """
    ret = venv.run_code(code, input=json.dumps(salt_minion_factory.config.copy()))
    loader_functions = json.loads(ret.stdout)

    # A non existing module should not appear in the loader
    assert "monty.python" not in loader_functions

    # But our extension's modules should appear on the loader
    assert "foobar.echo1" in loader_functions
    assert "foobar.echo2" in loader_functions


def test_new_entry_points_passing_func_returning_a_dict(
    venv, salt_extension, salt_minion_factory
):
    # Install our extension into the virtualenv
    venv.install(str(salt_extension.srcdir))
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name in installed_packages
    code = """
    import sys
    import json
    import salt._logging
    import salt.loader

    minion_config = json.loads(sys.stdin.read())
    salt._logging.set_logging_options_dict(minion_config)
    salt._logging.setup_logging()
    loader = salt.loader.runner(minion_config)
    print(json.dumps(list(loader)))
    """
    ret = venv.run_code(code, input=json.dumps(salt_minion_factory.config.copy()))
    loader_functions = json.loads(ret.stdout)

    # A non existing module should not appear in the loader
    assert "monty.python" not in loader_functions

    # But our extension's modules should appear on the loader
    assert "foobar.echo1" in loader_functions
    assert "foobar.echo2" in loader_functions


def test_old_entry_points_yielding_paths(venv, salt_extension, salt_minion_factory):
    # Install our extension into the virtualenv
    venv.install(str(salt_extension.srcdir))
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name in installed_packages
    code = """
    import sys
    import json
    import salt._logging
    import salt.loader

    minion_config = json.loads(sys.stdin.read())
    salt._logging.set_logging_options_dict(minion_config)
    salt._logging.setup_logging()
    functions = salt.loader.minion_mods(minion_config)
    utils = salt.loader.utils(minion_config)
    serializers = salt.loader.serializers(minion_config)
    loader = salt.loader.states(minion_config, functions, utils, serializers)
    print(json.dumps(list(loader)))
    """
    ret = venv.run_code(code, input=json.dumps(salt_minion_factory.config.copy()))
    loader_functions = json.loads(ret.stdout)

    # A non existing module should not appear in the loader
    assert "monty.python" not in loader_functions

    # But our extension's modules should appear on the loader
    assert "foobar.echoed" in loader_functions


def test_utils_loader_does_not_load_extensions(
    venv, salt_extension, salt_minion_factory
):
    # Install our extension into the virtualenv
    venv.install(str(salt_extension.srcdir))
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name in installed_packages
    code = """
    import sys
    import json
    import salt._logging
    import salt.loader

    minion_config = json.loads(sys.stdin.read())
    salt._logging.set_logging_options_dict(minion_config)
    salt._logging.setup_logging()
    loader = salt.loader.utils(minion_config)
    print(json.dumps(list(loader)))
    """
    ret = venv.run_code(code, input=json.dumps(salt_minion_factory.config.copy()))
    loader_functions = json.loads(ret.stdout)

    # A non existing module should not appear in the loader
    assert "monty.python" not in loader_functions

    # But our extension's modules should appear on the loader
    assert "foobar.echo" not in loader_functions


def test_extension_discovery_without_reload_with_importlib_metadata_installed(
    venv, salt_extension, salt_minion_factory
):
    # Install our extension into the virtualenv
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name not in installed_packages
    venv.install("importlib-metadata==4.6.4")
    code = """
    import sys
    import json
    import subprocess
    import salt._logging
    import salt.loader

    extension_path = "{}"

    minion_config = json.loads(sys.stdin.read())
    salt._logging.set_logging_options_dict(minion_config)
    salt._logging.setup_logging()
    loader = salt.loader.minion_mods(minion_config)

    if "foobar.echo1" in loader:
        sys.exit(1)

    # Install the extension
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", extension_path],
        check=False,
        shell=False,
        stdout=subprocess.PIPE,
    )
    if proc.returncode != 0:
        sys.exit(2)

    loader = salt.loader.minion_mods(minion_config)
    if "foobar.echo1" not in loader:
        sys.exit(3)

    print(json.dumps(list(loader)))
    """.format(
        salt_extension.srcdir
    )
    ret = venv.run_code(
        code, input=json.dumps(salt_minion_factory.config.copy()), check=False
    )
    # Exitcode 1 - Extension was already installed
    # Exitcode 2 - Failed to install the extension
    # Exitcode 3 - Extension was not found within the same python process after being installed
    assert ret.returncode == 0
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name in installed_packages

    loader_functions = json.loads(ret.stdout)

    # A non existing module should not appear in the loader
    assert "monty.python" not in loader_functions

    # But our extension's modules should appear on the loader
    assert "foobar.echo1" in loader_functions
    assert "foobar.echo2" in loader_functions


def test_extension_discovery_without_reload_with_importlib_metadata_5_installed(
    venv, salt_extension, salt_minion_factory
):
    # Install our extension into the virtualenv
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name not in installed_packages
    venv.install("importlib-metadata>=3.3.0")
    code = """
    import sys
    import json
    import subprocess
    import salt._logging
    import salt.loader

    extension_path = "{}"

    minion_config = json.loads(sys.stdin.read())
    salt._logging.set_logging_options_dict(minion_config)
    salt._logging.setup_logging()
    loader = salt.loader.minion_mods(minion_config)

    if "foobar.echo1" in loader:
        sys.exit(1)

    # Install the extension
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", extension_path],
        check=False,
        shell=False,
        stdout=subprocess.PIPE,
    )
    if proc.returncode != 0:
        sys.exit(2)

    loader = salt.loader.minion_mods(minion_config)
    if "foobar.echo1" not in loader:
        sys.exit(3)

    print(json.dumps(list(loader)))
    """.format(
        salt_extension.srcdir
    )
    ret = venv.run_code(
        code, input=json.dumps(salt_minion_factory.config.copy()), check=False
    )
    # Exitcode 1 - Extension was already installed
    # Exitcode 2 - Failed to install the extension
    # Exitcode 3 - Extension was not found within the same python process after being installed
    assert ret.returncode == 0
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name in installed_packages

    loader_functions = json.loads(ret.stdout)

    # A non existing module should not appear in the loader
    assert "monty.python" not in loader_functions

    # But our extension's modules should appear on the loader
    assert "foobar.echo1" in loader_functions
    assert "foobar.echo2" in loader_functions


def test_extension_discovery_without_reload_with_bundled_importlib_metadata(
    venv, salt_extension, salt_minion_factory
):
    # Install our extension into the virtualenv
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name not in installed_packages
    if "importlib-metadata" in installed_packages:
        importlib_metadata_version = installed_packages["importlib-metadata"]
        if Version(importlib_metadata_version) >= Version("3.3.0"):
            venv.install("-U", "importlib-metadata<3.3.0")
    code = """
    import sys
    import json
    import subprocess
    import salt._logging
    import salt.loader

    extension_path = "{}"

    minion_config = json.loads(sys.stdin.read())
    salt._logging.set_logging_options_dict(minion_config)
    salt._logging.setup_logging()
    loader = salt.loader.minion_mods(minion_config)
    if "foobar.echo1" in loader:
        sys.exit(1)

    # Install the extension
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", extension_path],
        check=False,
        shell=False,
        stdout=subprocess.PIPE,
    )
    if proc.returncode != 0:
        sys.exit(2)

    loader = salt.loader.minion_mods(minion_config)
    if "foobar.echo1" not in loader:
        sys.exit(3)

    print(json.dumps(list(loader)))
    """.format(
        salt_extension.srcdir
    )
    ret = venv.run_code(
        code, input=json.dumps(salt_minion_factory.config.copy()), check=False
    )
    # Exitcode 1 - Extension was already installed
    # Exitcode 2 - Failed to install the extension
    # Exitcode 3 - Extension was not found within the same python process after being installed
    assert ret.returncode == 0
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name in installed_packages

    loader_functions = json.loads(ret.stdout)

    # A non existing module should not appear in the loader
    assert "monty.python" not in loader_functions

    # But our extension's modules should appear on the loader
    assert "foobar.echo1" in loader_functions
    assert "foobar.echo2" in loader_functions
