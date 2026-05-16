# Classes Editor

_last updated 2024-11-13_

## Class Tags

Unlike tags attached to a unit or those granted via events, tags conferred by classes cannot be removed, even via event. However, if you change a class's tags in the project, all existing save files will have units of that class updated as well. This is in contrast to units, items, and skills, where existing instances of those objects in a save file will not be automatically updated when you update the editor.

## Special Promotion Gain Values

There are three special values that can be entered for a class's Promotion Gains: -99, -98, and -97.

| Promotion Gain Value | Explanation |
|----------------------|-------------|
| **-99**              | Automatically sets a unit's stat to the class's base stat upon promotion. |
| **-98**              | Sets a unit's stat to the class's base stat upon promotion if the class's base stat is higher than the unit's current stat. Best used for Gaiden/Echoes-style promotions. |
| **-97**              | Changes a unit's stat by the difference between their current class's base stat and their new class's base stat. Useful for differentiating gains when two classes promote to the same class. |


Note that, in order to preserve movement booster gains when promoting, either -97 or specifying the movement gain directly (e.g. a +1 bonus for a 6 MOV unit that promotes from a 5 MOV unit) must be used, as -99 and -98 can both erase the gains of the movement booster under some circumstances.

## Combat Animation

If you 'Cancel' while in the Choose Combat Animation window in the class editor, it will unassign whatever the current combat animation is for that class. This is the only way to unassign combat animations from a class.