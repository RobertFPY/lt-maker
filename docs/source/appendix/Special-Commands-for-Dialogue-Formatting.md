# Special Commands for Dialogue Formatting

_written by rainlash_
_last updated 2024-03-01_

## Introduction
In order to have your in-game dialog between characters or between the narrator and the player flow well and be more interesting to read, you can use several special dialog commands.

These dialog commands also work for help text accessed by pressing the R button in game.

## Command List

`{w}, {wait}`: Waits for the user to press A. Automatically placed at the end of any speak command unless text ends with {no_wait}.

`{no_wait}`: Place at the end of a dialog and the dialog will not wait for the user to press A.

`{br}, {break}`: Line break.

`{clear}`: Clear the text and line break.

`|`: shorthand for `{w}{br}` in sequence.

`{semicolon}`: Adds a `;`

`{tgs}`: Toggles whether the speaking sound occurs.

`{tgm}`: Toggles whether the portrait's mouth will move while talking.

`{max_speed}`: After this command, dialog will be drawn immediately to the screen.

`{starting_speed}`: After this command, dialog will be drawn at the normal speed to the screen.

`{command:??}, {c:??}`: Allows you to run any event command inline while dialog is being drawn to the screen. For instance: `s;Eirika;I'm... so.... {c:set_expression;Eirika;CloseEyes} sleepy...`

`<red>`: Can be used to turn the font to red color. Turn back to normal with `</red>` or `</>`. Can also use `<blue>`, `<green>`, etc.

`<icon>??</>`: Paste any 16x16 icon with a name directly into the text. For instance, `<icon>Waffle</>`.

`<text>`: Can be used to change the font. Turn back to normal with `</text>` or `</>`. Can also use `<nconvo>`, `<narrow>`, `<iconvo>`, `<bconvo>`, etc. 

## Example

