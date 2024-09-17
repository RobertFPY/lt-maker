# Evaluated Descriptions

## What Are They

Some descriptions in the editor allow you to use evaluated text. These are things like `{v:}` and `{e:}`.

Specifically at the moment this includes:

1. Unit descriptions
2. Item descriptions and skill descriptions

## Evaluated Variables

The evaluated text for the statements above all have access to a few common variables.

Like all evaluated statements evaluated text has access to a variable called `game`. This is the variable for the game state.

All descriptions also have access to a variable called `self`. This refers to the variable in the engine code that represents the object that the description belongs to. For example, the `self` variable for a unit description refers to a unit object in the engine code. Likewise for items and skills.

Items and skill descriptions have access to an additional variable called `unit`. This variable refers to the unit that currently owns this item or skill. This is equivalent to the statement `{e:game.get_unit(self.owner_nid)}` and is just a convenience variable.

## Examples

### Item Ownership

This is a simple concrete example. We can add a description for who's item it is in the item description. For example if Seth is holding a Steel Sword, we can modify the description of a Steel Sword to be `{unit}'s {e:self.name}`

This will be evaluated and displayed as `Seth's Steel Sword`.

![SteelSwordDescription](images/evaluated_descriptions/steel-sword-description-editor.png)
![SteelSwordDescription](images/evaluated_descriptions/steel-sword-description-game.png)

### Dynamic Gender and Pronouns

If we wanted to add dynamic gender we can use this feature. For example if we wanted dynamic gender for a certain unit, we can set a persistent variable during unit creation and use it in the description.

`"A wild {e:"man" if "{v:WildPronoun}" == "He" else "woman" if "{v:WildPronoun}" == "She" else "person"} raised in the forests of Nabu. Has a fear of blood and hates spiders."`

Lets say `WildPronoun` was set to `"He"` then the entire description would evaluate to: `A wild man raised in the forests of Nabu. Has a fear of blood and hates spiders.`

### Kill Tracker

We can add a kill tracker to an item or skill using this feature. We can set a persistent variable tracking the number of kills a unique weapon has been used for and show it in the description.

`"A blade that has taken {v:UniqueWeaponKills} lives."`

Lets say `UniqueWeaponKills` has tracked 10 kills so fa, then this description would evaluate to: `A blade that has taken 10 lives.`

## Advanced Usage

Since `self` refers to the object that the description belongs to, you have access to all variables accessible from that object. You can use that knowledge however you like.
