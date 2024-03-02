import os, subprocess, sys

def startfile(fn: str):
    if sys.platform == "win32" or os.name == 'nt':  # Windows
        os.startfile(fn)
    elif sys.platform == "darwin":  # MacOS
        opener = "open"
        subprocess.call([opener, fn])
    else:  # Linux??
        opener = "xdg-open"
        subprocess.call([opener, fn])
