# Equations Editor


_last updated 2024-11-13_

## Mana Display

By default, `MANA` is displayed on the right side of the unit info menu for LT projects. Removing the equation for `MANA` in this editor will prevent it from being displayed in the info menu for projects that do not use the mana system.

## Special Non-Default Equations

`THRACIA_CRIT`: Adding an equation with this name into the Equations editor will enable Jugdral critical hits, which multiply damage dealt *before* any form of damage reduction, such as applying defense. When using this calculation, set `CRIT_MULT` to 0, unless you want to implement some form of hybrid critical damage.