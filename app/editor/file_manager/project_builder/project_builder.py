from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from PyQt5.QtCore import QDir, Qt
from PyQt5.QtWidgets import (QApplication, QFileDialog, QMessageBox,
                             QProgressDialog)

from app.editor.file_manager.project_file_backend import DEFAULT_PROJECT

def execute(cmd):
    popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
    for stdout_line in iter(popen.stdout.readline, ""):
        yield stdout_line
    popen.stdout.close()
    return_code = popen.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, cmd)

PROGRESS_SENTINEL = "__PROGRESS_SENTINEL_STR__"

def build_project(current_proj: Path):
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
    for line in execute('pyinstaller --distpath "%s/dist" --workpath "%s/build" -y ./utilities/build_tools/engine.spec -- "%s" "%s"' % (output_dir, output_dir, current_proj.replace(".ltproj", ""), PROGRESS_SENTINEL)):
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
    subprocess.check_call(f'pyinstaller --icon=favicon.ico --distpath "{output_dir}/dist" --workpath "{output_dir}/build" --onefile --noconsole {project_name}.py', shell=True)
    progress_dialog.setValue(100)
    os.remove(tmp_run_exe_fname)
    os.remove(project_name + '.spec')