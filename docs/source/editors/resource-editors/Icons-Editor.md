# Icons Editor

_last updated 2024-11-13_

## Removing Icon Sheets

Icon sheets cannot be removed via the editor. Instead, you must go to the appropriate icons folder in the `resources` folder of your project and delete the icon sheet image there, as well as altering the `.json` file to no longer reference that sheet.

It is generally **not** recommended to alter files in this manner unless you are sufficiently experienced with the engine. Do this only if you absolutely must remove the icon sheet for whatever reason.

## Icons In Text

Any 16x16 icon can be displayed in text by using `<icon>ICONNAME</>`. As such, it is recommended to replace the name of any icon you may wish to reference, such as icons used to represent weapon effectiveness.