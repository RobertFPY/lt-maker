from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import List

from PyQt5.QtCore import QDir, Qt
from PyQt5.QtWidgets import (QApplication, QFileDialog, QMessageBox,
                             QProgressDialog)

from app.editor.file_manager.project_file_backend import DEFAULT_PROJECT
from app.utilities import file_utils

def execute(cmd):
    popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
    for stdout_line in iter(popen.stdout.readline, ""):
        yield stdout_line
    popen.stdout.close()
    return_code = popen.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, cmd)

PROGRESS_SENTINEL = "__PROGRESS_SENTINEL_STR__"


def icon_path(current_proj: Path, curr_plat: file_utils.Pltfm) -> Path:
    """Returns the icon path for a project. Pltfm is presently unused,
    because I'm not sure the icon best practices for other operating systems,
    but I expect we may end up using different files per OS.
    """
    project_icon_path = current_proj / 'resources' / 'system' / 'favicon.ico'
    if os.path.exists(project_icon_path):
        return project_icon_path
    return Path('favicon.ico')

def build_project(current_proj: Path):
    curr_plat = file_utils.Pltfm.current_platform()

    current_proj_basename = os.path.basename(current_proj)
    if(current_proj_basename) == DEFAULT_PROJECT:
        QMessageBox.warning(None, "Cannot build default project",
                            "Cannot build with default project! Please make a new project "
                            "before attempting to build.")
    project_name = current_proj_basename.replace('.ltproj', '')

    starting_path = Path(current_proj or QDir.currentPath()).parent
    starting_path = Path(starting_path) / (os.path.basename(current_proj) + '_build_' + time.strftime("%Y%m%d-%H%M%S"))
    output_dir, _ = QFileDialog.getSaveFileName(None, "Choose build location", str(starting_path),
                                         "All Files (*)")
    if not output_dir:
        return

    progress_dialog = QProgressDialog(
            "Building project %s" % project_name, None, 0, 100)
    progress_dialog.setAutoClose(True)
    progress_dialog.setWindowTitle("Building Project")
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

    progress_dialog.setValue(1)
    progress_dialog.show()
    QApplication.processEvents()

    kwargs: List[str] = []

    dist_cmd = '--distpath "%s/dist"' % output_dir
    work_cmd = '--workpath "%s/build"' % output_dir
    kwargs.append(dist_cmd)
    kwargs.append(work_cmd)

    icon = icon_path(Path(current_proj), curr_plat)

    spec_cmd = "-y ./utilities/build_tools/engine.spec"
    kwargs.append(spec_cmd)

    kwargstr = ' '.join(kwargs)
    # quirk of engine.spec
    project_path_without_extension = current_proj.replace(".ltproj", '')

    engine_build_cmd = f'pyinstaller {kwargstr} -- "{project_path_without_extension}" "{PROGRESS_SENTINEL}" "{icon}"'
    for line in execute(engine_build_cmd):
        if PROGRESS_SENTINEL in line:
            progress = int(line.replace(PROGRESS_SENTINEL, ""))
            progress_dialog.setValue(progress)
    shutil.rmtree(output_dir + "/build")

    # make the executable
    dir_path = Path(os.path.dirname(os.path.realpath(__file__)))
    tmp_run_exe_fname = '%s.py' % project_name
    with open(dir_path / 'run_exe_base.txt') as base:
        text = base.read()
        text = text.replace('__PROJECT_NAME__', project_name)
        with open(tmp_run_exe_fname, 'w') as out:
            out.write(text)

    exe_kwargs: List[str] = []
    exe_kwargs.append(dist_cmd)
    exe_kwargs.append(work_cmd)
    icon_cmd = '--icon=%s' % icon
    exe_kwargs.append(icon_cmd)

    exe_kwargstr = ' '.join(exe_kwargs)
    executable_build_cmd = f'pyinstaller --onefile --noconsole {exe_kwargstr} "{project_name}.py"'
    subprocess.check_call(executable_build_cmd, shell=True)
    progress_dialog.setValue(100)
    os.remove(tmp_run_exe_fname)
    os.remove(project_name + '.spec')

    # finally, for ease of use, open the folder for the user
    file_utils.startfile(f"{output_dir}/dist")