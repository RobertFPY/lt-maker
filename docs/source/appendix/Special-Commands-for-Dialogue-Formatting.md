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

`<wave>`: Can be used to change the text effect. Turn back to normal with `</wave>` or `</>`. Can also use `<wave2>`, `<sin>`, `<jitter>`, `<jitter2>`, etc.
Advanced usage: some text effects may have arguments that can be used to customize the effect. For example, wave has a `amplitude` argument that can be used to customize the amplitude of vertical wave oscillation.
The exact usage would look like `<wave amplitude=4.5>some text</>`. The general format for effect arguments is `<effect arg1=val1 arg2=val2 ...>`. Parsing for arguments is whitespace and case sensitive.
For a full effect list look at `app/engine/graphics/text/text_effects.py`. Both `TextEffect` and `CoordinatedTextEffect` classes are available to use as text effects in dialog, and the corresponding names for each effect is under the effect class as its `nid` and the available arguments for each effect is the arguments to its `__init__` function excluding `self` and `idx` arguments.

## Example

