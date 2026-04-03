=============================
[WINDOWS]
How to Play:
1) Extract the game folder from the .zip/archive file and store it in any folder you wish, !!AS LONG AS THAT FOLDER IS NOT BACKED UP BY ONEDRIVE OR OTHER CLOUD STORAGE!!.
2) Double-click "GAMENAME.exe" or "double_click_to_play.bat" to start the game. Both options do the same thing.

=============================
[LINUX - PROTON]
How to play (No terminal required, recommended):
1) Extract the game folder from the .zip/archive file and store it in any folder you wish, !!AS LONG AS THAT FOLDER IS NOT BACKED UP BY CLOUD STORAGE!!.
2) Install the Steam client via your preferred package manager or from the Steam website.
3) In the lower left corner of your Steam library, click the "Add a Game" button, and select "Add a non-Steam game...".
4) Click "Browse...", navigate to the folder where you stored the game, and select "GAMENAME.exe". Then, click "Add selected programs" and the game now shows up in your Steam library.

=============================
[LINUX - WINE]
How to play (Requires terminal):
1) Extract the game folder from the .zip/archive file and store it in any folder you wish, !!AS LONG AS THAT FOLDER IS NOT BACKED UP BY CLOUD STORAGE!!.
2) Install your preferred version of Wine from the WineHQ website;
    https://www.winehq.org/
        It is recommended to install Wine manually, as the package distributed by many package managers are outdated. Version 11.0 is known to run LT games in a stable manner. Older versions are untested.
3) Open "GAMENAME.exe" with Wine.

=============================
If you wish to build from source on Linux, or play on MacOS or Android, refer to the last paragraphs of this document.

=============================
[CONTROLS]

Function   | Keyboard | Mouse | Xbox Controller | PS Controller
===============================================================
Select     | X        | Left  | A               | Cross
Back       | Z        | Right | B               | Circle
Info       | C        | Middle| X               | Square
AUX        | A        |       | Back            | Share
Move       | Arrows   | Hover | Left Stick      | Left Stick
Start      | S        |       | Start / Y       | Options / Triangle
Screenshot | ` / F12  |       |                 |

* The AUX key is used to focus the cursor on your units when on the map and to toggle the Growth Rate display on the Unit Info Menu.
* Screenshots are saved as .bmp files if the ` key was pressed or .png files if F12 was pressed. Screenshots are saved within the game folder.
* You can soft reset by holding Select, Back, and Start.
* You can rebind which key on your keyboard does what in the Options > Controls menu in-game. Controller button remapping has not been implemented yet, although you can use an input remapper to bind controller input to keyboard keys as a workaround.

=============================
[KNOWN ISSUES]
* Windows Defender and other common anti-virus programs do not like LT-Maker games. Just choose to run the game anyway and/or make it an exception for Windows Defender.

* The EXP gain SFX may sound weird on some computers. (The pitch is sound card dependent.) To adjust this, go into saves/config.ini. Change sound_buffer_size to a small even number until the SFX sounds right. Make sure to close the game while editing these settings, and to save the file after editing it.

=============================
[CARRYING OVER SAVE FILES]

If the game gets an update and you would like to transfer your saves from an old version to a new version, follow these steps:

1) Open the GAMENAME folder of the older version.
2) Open the saves folder.
3) Move all the files within the saves folder into the saves folder of the newer version.
4) Restart the chapter to ensure the changes are implemented.

=============================
[TIPS AND TRICKS]

* You can change the screen size in-game through: Extras > Options > Config > Screen Size
** The full-screen option is wonky and not recommended.

* You can toggle mouse controls in-game through: Extras > Options > Config > Mouse

=============================
[ADVANCED INSTALLATIONS] - Linux (source), MacOS, Android
=============================
[LINUX - BUILD FROM SOURCE]
NOTE: Most creators will ship the blank .exe engine with their game files attached. If this is the case, you can build the game from source. However, if the creator has included engine hacking in their project, this method WILL NOT WORK. If you are unsure, please contact the developer(s) of the LT game you want to play. If the developer(s) have a native version for linux available for download, you can skip step 3.

1) Install the following programs (preferred versions if possible);
    python==3.11*
    python3pip
    pygame-ce==2.3.2
    pyinstaller==6.2.0
    typing-extensions==4.8.0
    PyQt5==5.15.10**
    mypy==1.8.0
    mypy-extensions==1.0.0
        *LT is potentially unstable or will not boot on newer versions of python. While there have been little to no reports of major issues on Linux specifically, do keep that in mind.
        **Some Linux distributions (mainly Ubuntu and Ubuntu-based distributions) may have trouble installing PyQt5. In that case, try: "sudo apt-get install python3-pyqt5".

2) Clone the following repository to your prefered storage location;
    https://gitlab.com/rainlash/lt-maker.git***
        ***If the creator has their own repository set up, clone that instead.

3) Grab the folder named "GAMETITLE.ltproj" from the windows version and put it inside the "lt-maker" folder. Delete the "default.ltproj" folder.

4) Open a terminal window in the folder and type "python3 run_engine.py". The engine should now boot up with the desired game.**** You can also create a script to perform this command. It is recommended to run this script in the terminal, as the game uses the terminal as a log.
    ****If the desired game does not boot up, change the command to "python3 run_editor.py", click the "Open other" button and select the "GAMENAME.ltproj" folder. Once the editor opens, click the play icon in the icon bar and then select the "Test Full Game..." option. From there, you can play as normal.

=============================
[MacOS - WINE]
NOTE: Most creators will ship the blank .exe engine with their game files attached. For maximum stability, the MacOS version needs the python version of the engine to run in Wine. If you are unsure, please contact the developer(s) of the LT game you want to play.

How to play:
1) Download and extract the game folder from its archive file to a desired location.
2) Install Homebrew
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
3) Install Wine
    brew install wine-stable
4) Install Miniconda
    brew install --cask miniconda
5) Initialize conda in your shell
    conda init "$(basename "${SHELL}")"

6) Perform the following steps before first boot;
    cd lt-maker
    conda create -n fe-i-lt python=3.11.7
    conda activate fe-i-lt
7) Setup Windows Python;
    curl -O https://www.python.org/ftp/python/3.11.7/python-3.11.7-amd64.exe
    wine python-3.11.7-amd64.exe
8) Install the following requirements IN Wine Python;
    wine pip install -r
    python3pip
    pygame-ce==2.3.2
    pyinstaller==6.2.0
    typing-extensions==4.8.0
    PyQt5==5.15.10
    mypy==1.8.0
    mypy-extensions==1.0.0
9) Execute the following commands;
    cd lt-maker
    conda activate fe-i-lt
    wine python run_engine.py

=============================
[ANDROID]
Refer to the following links;
1) https://feuniverse.us/t/lex-talionis-on-android-its-time/28374
2) https://feuniverse.us/t/lex-talionis-on-android-its-time/28374/6

=============================
