# Constants Editor

## Game Unique Identifier

This ID is used to label the filenames of save files for LT games. As such, changing this will render existing saves inoperable unless all of their individual names are changed as well. Bear this in mind when determining your ID before a public release.

## Constants Dependent On Game Variables

While some constants have dedicated editors, such as Overworld and Supports, several constants require eventing to function, even when checked off in the Constants editor. These are:

> - `Turnwheel`: requires the turnwheel to be enabled via the `enable_turnwheel` event command, as well as `_max_turnwheel_uses` to be set if the game is meant to impose a limit on usage.
> - `Fatigue`: requires the `_fatigue` variable to be set to an applicable value.
> - `Global Leadership Stars`: requires a few different steps (see below).

For more information on variables used for these constants, please refer to [Special Variables](Special-Variables).

## Leadership Stars

*Thracia 776* style leadership stars are available in the **Lex Talionis** engine. To implement:

![GlobalLeadershipStars](../images/ConstantsEditorImages/LeadershipStarsConstantsEditor.png)

1. Check the "Global Leadership Stars" box in the Constants menu

![LEADStat](../images/ConstantsEditorImages/LEADStat.png)

2. Create a "LEAD" stat in the Stats editor. This stat will be the number of leadership stars a unit has.

![LEADEquation](../images/ConstantsEditorImages/LEADEquation.png)

3. Create a LEAD_HIT and LEAD_AVOID equation in the Equations editor. These equations will determine the bonus hit and avoid units will get from leadership stars

## Constants Dictionary

This section lists the functionality of each constant available in the Constants editor.

| Constant | Description |
| ------ | ------ |
| **Turnwheel** | Allows the player to access time rewind mechanic to restore the game to an earlier state within the same chapter. |
| **Per Unit Initiative Order** | Causes each unit to have its own turn, removing the Player/Enemy Phase division. |
| **Fatigue** | Causes units to accumulate fatigue each time they are deployed on a map. |
| **Pair Up** | Allows units to merge into a duo where one unit is the main unit in combat and the other grants passive bonuses. Allows for pair up attacks and guard stance as well. |
| **Limit Attack Stance to first attack only** | Pair Up constant. Restricts the benefits of Attack Stance to only the first attack if the unit doubles. |
| **Global Leadership Stars** | Adds a leadership star stat, visible through the info menu, that grants passive bonuses to all other units in the same army. |
| **Bonus Experience** | Allows accumulation of bonus experience that can be distributed to any unit in base. |
| **Always gain 3 stat-ups when using Bonus Exp.** | Any level gained using bonus experience will have exactly three stat increses. |
| **Supports** | Allows units to accumulate support ranks, granting passive bonuses to each other which can be modified based on affinity. |
| **Overworld** | Enables a traversable overworld with nodes for shopping and other events. |
| **Unit Notes** | Makes unit notes visible in the info menu. |
| **Allow Criticals** | Enables critical hits. |
| **Can trade items on map** | Allows units to trade items during a chapter while adjacent to each other. |
| **Can view unit growths in Info Menu** | The player can press the Aux button when looking at a unit's stats to view growth rates. |
| **Apply difficulty bonus growths to past levels** | Non-boss enemy units gain a bonus to their stats based on the bonus growths granted by the selected difficulty. |
| **Force items and abilities to obey line of sight rules** | Items cannot pass through walls and other terrain that break line of sight. |
| **Force auras to obey line of sight rules** | Skill auras cannot pass through walls and other terrain that break line of sight. |
| **Fog of War will also be affected by line of sight** | Areas blocked by walls and other similar terrain are not revealed under fog of war. |
| **AI will also be affected by Fog of War** | Non player-controlled units follow the same rules players follow for Fog of War. |
| **Defender can double counterattack** | Allows doubling for a unit that did not initiate the attack. |
| **Units will promote automatically upon reaching max level** | Surely this one is self explanatory. |
| **Promotion resets level back to 1** | When enabled, unit does not retain their level/exp when changing class through promotion and is instead reset to 1. |
| **Class Change resets level back to 1** | When enabled, unit does not retain their level/exp after changing class in any way. |
| **Generic units will be granted random feats when appropriate** | If a generic unit would have gained a feat at its current level, it gains one of any random skill marked as a feat. |
| **Final blow on boss will use critical animation** | Works even if the critical rate is 0 for that attack. |
| **Use battle platforms when battle backgrounds are on** | Enables display of battle platforms when using battle backgrounds. |
| **Items held by dead player units are sent to convoy** | Also self explanatory. |
| **Access the Repair Shop in prep and base** | Allows units to repair held items in the Manage section of preps and base menus. |
| **Unit can give a unit after taking a unit** | Refers to the rescue mechanic. |
| **Mana resets to full for units upon completion of the chapter** | When disabled, mana is unchanged between chapters. |
| **When doubling, splash/aoe is applied on the second attack** | When disabled, AoE effects only apply to the first attack when doubling. |
| **Enemy AI attacks even if Hit is 0** | Used to make the AI dumber. |
| **Enemy AI attacks even if damage is 0** | Allows the AI to choose to attack even if no damage or status would be dealt. |
| **Show Movement as 0 if AI does not move** | Applies when displaying NPC movement range/threat. Changing to a different AI will update the display. |
| **Display particle effect on title screen** | Used for the little glimmery things that float by in the title screen. |
| **Restart phase music at beginning of new phase** | Phase music plays from beginning each time phase changes. |
| **Restart battle music at beginning of each combat** | Battle music plays from the beginning for each battle. |
| **Kills give double weapon exp** | Very self explanatory. |
| **Each hit when doubling grants weapon exp** | If disabled, only one hit per combat grants weapon exp. |
| **Gain weapon exp even on miss** | Still self explanatory. |