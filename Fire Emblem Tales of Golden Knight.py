import subprocess
import os

if __name__ == '__main__':
    os.chdir('./Fire Emblem Tales of Golden Knight')
    fname = 'Fire Emblem Tales of Golden Knight.exe'
    subprocess.Popen(fname, shell=True)