TILEWIDTH, TILEHEIGHT = 16, 16
# Logical viewport size in tiles. Phase 1 of the resolution bump:
# 20x15 tiles == 320x240 px (matches PS1 Tearing Saga / SNES).
TILEX, TILEY = 20, 15
WINWIDTH, WINHEIGHT = int(TILEX * TILEWIDTH), int(TILEY * TILEHEIGHT)

# Legacy GBA-style canvas size (240x160). Combat animations, the promotion
# screen, and many fixed-size art assets were authored at this resolution.
# When WINWIDTH/WINHEIGHT exceed these values, those sub-systems are rendered
# into a GAME_NES-sized inner surface and letterboxed onto the main canvas.
GAME_NES_WIDTH, GAME_NES_HEIGHT = 240, 160
LETTERBOX_X = (WINWIDTH - GAME_NES_WIDTH) // 2
LETTERBOX_Y = (WINHEIGHT - GAME_NES_HEIGHT) // 2

PORTRAIT_WIDTH, PORTRAIT_HEIGHT = 128, 112
COLORKEY = 128, 160, 128
FPS = 60
FRAMERATE = 1000//FPS

AUTOTILE_FRAMES = 16

VERSION = "2026.02.17a"

if __name__ == '__main__':
    print(VERSION)

APP_AUTHOR = "rainlash"
APP_NAME = "Lex Talionis"
