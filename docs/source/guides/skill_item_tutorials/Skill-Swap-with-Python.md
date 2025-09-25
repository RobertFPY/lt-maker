<small>`Created by #Octothorpe. Last updated 2025-09-21.`</small>

# [System] Skill Swap (with Bonus Intro to Python Scripting)

Lex Talionis Event Editor offers enough power to build custom systems. They can be quite complex, and this is the case with skill swap.

In this guide, I'll be be covering all the requirements to build a simple skill swap system using the tools available in the latest engine build. This can be extended to fit the needs of your project.

This guide expects the reader to have prior experience in the editors and components used, as most of them will be heavily glossed over due the amount of steps required. Check the documentation and other guides for information components.

As a secondary task, I recommend reading the Depreciated Skill Swap Guide. I based my design on his work, and while I rewrote large portions of it due to streamlining (or to update it to the latest engine), the knowledge within is incredibly solid, and I've pilfered sections of his guide to write mine, but I'm not dedicated enough to update his doc.

Here's a quick demo of what you should be able to do with this guide.

![Skill Swap](images/Skill-Swap/skill_swap.gif)

<big>**DISCLAIMER**</big>: 

I erred on the side of 'generic and repurposeable system that will not crash your engine,' but there may be some logic errors due to this not being my final implementation. It's up to you to find errors and fine tune this system based on your project requirements. This is **NOT** intended to be plug and play.


## Step 0.a: Set Up Your Events
To save time, create all of the listed events in advance, preferably using the same names, as those will be the ones listed in the guide. Don't forget to set their triggers as well. Those who have events listed as triggers have to be set as **None**. All of them use the Global level.

|Event|Trigger
|-|-
|`Skill_Swap_Unit_Initializer`|level_start
|`Check_Skill_Unlock`|unit_level_up
|`Skill_Swap_Class_Data`|`Skill_Swap_Unit_Initializer`
|`Skill_Swap_Level_Up`|`Check_Skill_Unlock`
|`Skill_Swap_Operations`|`Skill_Swap_Setup`
|`Skill_Swap_Select`|`base;` or `prep;` commands
|`Skill_Swap_Setup`|Interface|`Skill_Swap_Target_Fix`
|`Skill_Swap_Target_Fix`|`Skill_Swap_Select`
|`Skill_Swap_Add`,<br/>`Skill_Swap_Remove`,<br/>`Skill_Swap_Reorder`,<br/>`Skill_Swap_Replace`|Option|`Skill_Swap_Operations`

## Step 0.b: Remove All Skills
You need to remove all skills from all classes. This includes Canto from mounted units.

## Step 0.c: Set Up Raw Data
We need to build up a replacement for the data we deleted. This data will all be assigned to units via events, but it needs to be these first. We can do that by building a **raw data** list, named `ClassData`. It has three columns.

|nid|skill1|skill2|
|-|-|-
|Eirika_Lord|Speed_Plus2|Charm
|Knight|Crit_Plus15|Defense_Plus5
|Paladin|Defense_Plus2|Canto
|Soldier|Aether|RightfulKing
|Brigand|Luna|DualGuard+
|General|RallyDefense|Pavise

Just to reinforce an important point. 'nid' should be the exact nid of each class in your game, and the skill1 and skill2 for that class should be the exact nids of two skills that already exist. Continue until you have listed all classes and all skills.

In this guide, I'm assuming each class has only two skills that are unlocked at levels 5 and 15, respectively. You will need to extend this data for different functionality. Say, for a third skill. 

## Step 1: Code the Initializer
This is our first script. Fortunately, it's an easy one. Let's walk through it:

|Event|Trigger
|-|-
|`Skill_Swap_Unit_Initializer`|level_start

    game_var;SKILL_SWAP_CAP;5
    game_var;MY_CLASS;""

    for;FETCHED_UNIT;[u for u in game.get_all_units()]

        #u() is short for game.get_unit
        if;not u('{FETCHED_UNIT}').get_field('Initialized')

            game_var;MY_CLASS;u('{FETCHED_UNIT}').klass

            trigger_script;Global Skill_Swap_Class_Data;{FETCHED_UNIT}

            set_unit_field;{FETCHED_UNIT};Initialized;True
        end

    endf

    base;;;Skill Swap;;Global Skill_Swap_Select
    prep;;;Skill Swap;;Global Skill_Swap_Select

First step is to set up some variables at the beginning. SKILL_SWAP_CAP is an important one. That lists how many skills a unit can have. If you change the value, you can update it across the whole project.

Next, we loop through all units via the FETCHED_UNIT for loop, and simply check if it's initialized. If it is, we do nothing. If it's not, call an event we haven't written yet, and then we initialize it to 'True'. "What does 'initialize' mean in this context?" you might ask. Well, I'm glad you did. Inside this script and the following ones, we're going to be assigning some fields to our units. This will help us track their information. Initialized just means that we've done that.

Here is a list of all of the fields we're going to be making. None of these should be created in the GUI. It will all be done via events for simplicity.

|Field|Role
|--|--
|`Initialized`|Checks if the unit went through initialization to build its `MasteredClasses`, `LearnedSkills`, and `EquippedSkills` fields. We don't want to do this more than once.
|`MasteredClasses`|Lists all the classes this unit has access to the skills of. Useful for pre-promoted units.
|`LearnedSkills`|List containing all the skills learned by the unit.
|`EquippedSkills`|List containing all the currently equipped skills by the unit.

## Step 2: Code the Python Data Fetcher

Sounds hard, but it's easy, I promise! In `Skill_Swap_Unit_Initializer`, we had this line. This calls a script and passes in our unit to be initialized.

    trigger_script;Global Skill_Swap_Class_Data;{FETCHED_UNIT}

|Event|Trigger
|-|-
|`Skill_Swap_Class_Data`|`Skill_Swap_Unit_Initializer`

    #pyev1
    cur_unit = unit

    $set_unit_field cur_unit 'MasteredClasses' ['Knight','Paladin'] #THIS IS INCORRECT. DO NOT DO THIS.
    #$set_unit_field cur_unit 'MasteredClasses' [] #THIS IS CORRECT. DO THIS.
    $set_unit_field cur_unit 'LearnedSkills' []
    $set_unit_field cur_unit 'EquippedSkills' []

    if cur_unit.get_field('MasteredClasses'):
        for mastered in cur_unit.get_field('MasteredClasses'):
            for line in game.get_data('ClassData'):

                if mastered == line.nid:
                    if len(cur_unit.get_field('LearnedSkills')):
                        tmp=cur_unit.get_field('LearnedSkills')
                        tmp.append(line.skill1)
                        tmp.append(line.skill2)
                    else:
                        tmp=[line.skill1,line.skill2]
                    $set_unit_field cur_unit 'LearnedSkills' tmp


First thing we do here tell the engine that we want to code in Python with `#pyev1`. This event is much easier to write in Python since we need to read data from the `ClassData` table.

Next, we set the variable `unit` that we passed into the event and call it `cur_unit`. It helps us think about it as the "current unit we're working on", but it's not scrictly necessary. What happens next? All those other fields I mention in step 1 get created as empty. "Empty," you say, "what about that line that that says 'INCORRECT. DO NOT DO THIS?' " That line makes every unit have Knight and Paladin as their `MasteredClasses`, which is great for testing to make sure the system works! . . . But probably not so great for your game. So when you're done testing, delete that line and uncomment the line below that by deleting the octothorpe at the start of the line.

Continuing on, The '$' means that the line should be interpreted by the engine as the event-script.

Now, lines without the '$' are intrepreted as regular Python. This large block of code is quite simple.

If the unit has any mastered classes upon initialization, then loop through every `MasteredClass`. Knight and Paladin, in our testcode. You then loop through every line in that beautiful `ClassData` table you created earlier. Then, if the mastered class matches the nid of that entry, you fill their `LearnedSkills` with all the skills from that class by creating a list and setting `LearnedSkills` to that list.

And boom. You're done initializing your units.

## Step 3: Code the Base Menu

If you recall `Skill_Swap_Unit_Initializer` has a 'base' command. That drops us in the base and creates a menu option "Skill Swap" that calls an event we haven't created yet. Time to create it.


|Event|Trigger
|-|-
|`Skill_Swap_Select`|`base;` or `prep;` commands

    game_var;AUX_STR;"Eirika,Vanessa,Seth,Moulder,Bone"
    choice;SELECTED_UNIT;Swap skills from which unit?;{v:AUX_STR};73;;top_left;;Global Skill_Swap_Target_Fix;type_unit;8,3;scroll_bar;persist;backable


We're back from Python-land, and we're coding in the eventing language. We create a list of chacters that we want to allow to swap skills, then offer the player a choice of who to swap skills, and run another event based on who we pick. Onwards we go to that event!

## Step 4: Code the Target

|Event|Trigger
|-|-
|`Skill_Swap_Target_Fix`|`Skill_Swap_Select`
    trigger_script;Global Skill_Swap_Setup;{v:SELECTED_UNIT}

Huh, that's a short script. Yup, that's whe whole script. "Why does this script even exist?" you may ask. It's actually very important.
If you recall this line from `Skill_Swap_Select`

    choice;SELECTED_UNIT;Swap skills from which unit? # . . . line continues

We need to grab the unit from the choice, but we also need to have the choice actually select the unit. We the take the selected unit saved in `SELECTED_UNIT`, and then we pass that into our next script.

## Step 5: Let's Swap Some Skills!

Time to get into some meat and potatos. This looks complicated, but it's not too bad if you break it down into little pieces.

|Event|Trigger
|-|-
|`Skill_Swap_Setup`|Interface|`Skill_Swap_Target_Fix`

    game_var;EXIT_SKILL_SWAP;True

    #Create a list of equipped skills
    game_var;EQUIPPED_SKILLS;','.join([s for s in u('{unit}').get_field('EquippedSkills')])

    #If you have no equipped skills, add a dummy skill called 'Add_New_Skill'
    if;len(unit.get_field('EquippedSkills')) == 0
        game_var;EQUIPPED_SKILLS;"Add_New_Skill"

    #Or, if you have skills, but you don't have the max number of swappable skills, also add the dummy skill.
    elif;len(unit.get_field('EquippedSkills')) < {v:SKILL_SWAP_CAP}
        game_var;EQUIPPED_SKILLS;"{v:EQUIPPED_SKILLS},Add_New_Skill"
    end

    #Create a list of every skill that you can learn (that you don't have equipped.
    if;len(unit.get_field('LearnedSkills')) > len(unit.get_field('EquippedSkills'))
        game_var;LEARNED_SKILLS;','.join([s for s in u('{unit}').get_field('LearnedSkills') if s not in unit.get_field('EquippedSkills')])
    else
        game_var;LEARNED_SKILLS;"Empty_Skill_List"
    end


    #Make a table of the learned skills so you can see your options for swapping skills
    table;UNIT_RIGHT_SKILLS;{v:LEARNED_SKILLS};Learned Skills;{v:SKILL_SWAP_CAP},1;100;top_right;menu_bg_base;type_skill;center

    #Make a choice for the player to select which skill to swap
    choice;UNIT_SELECTED_SKILL;Equipped Skills;{v:EQUIPPED_SKILLS};100;vert;top_left;;Global Skill_Swap_Operations;type_skill;{v:SKILL_SWAP_CAP},1;center;backable
    rmtable;UNIT_RIGHT_SKILLS

    if;not {v:EXIT_SKILL_SWAP}
        trigger_script;Global Skill_Swap_Setup
    end

As you can see from the comments, overall, it's pretty simple from a conceptual point of view. Take our fields and turn them into something we can present the player as a menu. And put the entire thing in a big loop by calling itself. That way the player can keep swapping skills to his heart's content, untill the 'b' button gets in the way.


## Step 5: Operations

The previous event seems to have called another event! We could have never possibly forseen this. Guess we'll have to make that one, too.

|Event|Trigger
|-|-
|`Skill_Swap_Operations`|`Skill_Swap_Setup`

    game_var;EXIT_SKILL_SWAP;False
    game_var;AUX_STR;""

    if;"{v:LEARNED_SKILLS}" != "Empty_Skill_List"
        if;"{v:UNIT_SELECTED_SKILL}" == 'Add_New_Skill'
            game_var;AUX_STR;"Add,"
        else
            game_var;AUX_STR;"Swap,"
        end
    end

    if;'{v:UNIT_SELECTED_SKILL}' != 'Add_New_Skill'
        game_var;AUX_STR;"{v:AUX_STR}" + "Remove,"
        if;unit.get_field('EquippedSkills')[0] != "{v:AUX_SKILL}"
            game_var;AUX_STR;"{v:AUX_STR}" + "Reorder,"
        end
    end

    choice;SKILL_SWAP_OPERATION;;{v:AUX_STR}Cancel;40;backable

    if;'{v:SKILL_SWAP_OPERATION}' == 'Remove'
        trigger_script;Global Skill_Swap_Remove;{unit}
    elif;'{v:SKILL_SWAP_OPERATION}' == 'Reorder'
        trigger_script;Global Skill_Swap_Reorder;{unit}
    elif;'{v:SKILL_SWAP_OPERATION}' == 'Add'
        trigger_script;Global Skill_Swap_Add;{unit}
    elif;'{v:SKILL_SWAP_OPERATION}' == 'Swap'
        trigger_script;Global Skill_Swap_Replace;{unit}
    end

This script takes all the setup we did from the last script, and builds some options. It's divided into 3 sections. The part before the choice command builds the menu options based on how many skills you have. You don't want to have your menu ask if you want to swap our placeholder skill with a real one, for example. Tried that. All sorts of things happen, and most of them bad.

Then, you have the choice. Pretty straightforward at this point.

Finally, call the appropriate operation script based on what you want to do to your skills.

## Step 6: Operations (Once Again, with Feeling)

Now, we need to make each operation event. We're in the home stretch now.

### Step 6.a Add a Skill

|Event|Trigger
|-|-
|`Skill_Swap_Add`|`Skill_Swap_Operations`

    choice;UNIT_LEARNED_SKILLS;Learned Skills;{v:LEARNED_SKILLS};100;vert;top_right;;;type_skill;{v:SKILL_SWAP_CAP},1;scroll_bar;backable
    if;'{v:UNIT_LEARNED_SKILLS}' != 'BACK'

        give_skill;{unit};{v:UNIT_LEARNED_SKILLS};no_banner
        if;len(unit.get_field('EquippedSkills')) > 0
            game_var;AUX_STR;",'{v:UNIT_LEARNED_SKILLS}'"
        else
            game_var;AUX_STR;"'{v:UNIT_LEARNED_SKILLS}'"
        end

        game_var;AUX_STR;','.join("'" + s + "'" for s in unit.get_field('EquippedSkills')) + "{v:AUX_STR}"
        set_unit_field;{unit};EquippedSkills;[{v:AUX_STR}]
    end

This is pretty simple. It spawns a new menu that shows all skills that a unit has learned, but on the opposite side of the screen so you can see what skills you have equipped aleady. It then adds the skill to the `EquippedSkills` field. All that extra stuff is just because of the way the event commands behave around lists.

### Step 6.b: Remove a Skill

|Event|Trigger
|-|-
|`Skill_Swap_Remove`|`Skill_Swap_Operations`

    game_var;AUX_STR;""
    game_var;BUFFER;""

    for;FETCHED_SKILL;[s for s in u('{unit}').get_field('EquippedSkills')]
        if;'{FETCHED_SKILL}' == '{v:UNIT_SELECTED_SKILL}'
            remove_skill;{unit};{FETCHED_SKILL};no_banner
        elif;'{FETCHED_SKILL}' != 'Add_New_Skill'
            game_var;AUX_STR;"{v:AUX_STR}" + "'{FETCHED_SKILL}',"
        end
    endf

    set_unit_field;{unit};EquippedSkills;[{v:AUX_STR}]

This one is even easier. It removes the skill from the unit and the `EquippedSkills` list.

### Step 6.c: Replace a Skill
|Event|Trigger
|-|-
|`Skill_Swap_Replace`|`Skill_Swap_Operations`

    choice;SKILL_TO_LEARN;Learned Skills;{v:LEARNED_SKILLS};100;vert;top_right;;;type_skill;{v:SKILL_SWAP_CAP},1;center;backable

    if;'{v:SKILL_TO_LEARN}' != 'BACK'
        game_var;AUX_STR;""

        for;FETCHED_SKILL;[s for s in u('{unit}').get_field('EquippedSkills')]
            remove_skill;{unit};{FETCHED_SKILL};no_banner
            if;'{FETCHED_SKILL}' == '{v:UNIT_SELECTED_SKILL}'
                game_var;AUX_STR;"{v:AUX_STR}" + "'{v:SKILL_TO_LEARN}',"
                give_skill;{unit};{v:SKILL_TO_LEARN};no_banner
            else
                game_var;AUX_STR;"{v:AUX_STR}" + "'{FETCHED_SKILL}',"
                give_skill;{unit};{FETCHED_SKILL};no_banner
            end

        endf

        set_unit_field;{unit};EquippedSkills;[{v:AUX_STR}]
    end

This one is basically a combination of remove and add. However, when a unit learns a skill, the game adds it to the bottom of the list. We're better than that. We want to replace the skill in the same place, so we work our magic. First step is to remove each skill in the loop. Then we need to add them back in the same order.

`{v:UNIT_SELECTED_SKILL}` is the secret; it is a variable that is set many events ago. `Skill_Swap_Setup` to be precise. That is the skill choice we selected to be removed. If the loop sees that the skill it's looping through is the selected skill (aka, the skill to be swapped out), it instead adds the new skill. Otherwise, it just re-adds every skill it just removed.

### Step 6.d: Reorder a Skill
|Event|Trigger
|-|-
|`Skill_Swap_Reorder`|`Skill_Swap_Operations`

    #Rebuild the equipped skills list so that the player can't swap real skills with the dummy skill
    game_var;CURRENT_SKILLS_NO_EMPTY_SLOT;','.join([s for s in u('{unit}').get_field('EquippedSkills') if s != 'Add_New_Skill'])

    choice;SKILL_TO_REORDER;Learned Skills;{v:EQUIPPED_SKILLS};100;vert;top_right;;;type_skill;{v:SKILL_SWAP_CAP},1;scroll_bar;backable
    if;'{v:SKILL_TO_REORDER}' != 'BACK'
        game_var;AUX_STR;""

        for;FETCHED_SKILL;[s for s in u('{unit}').get_field('EquippedSkills')]
            remove_skill;{unit};{FETCHED_SKILL};no_banner
        endf

        for;FETCHED_SKILL;[s for s in u('{unit}').get_field('EquippedSkills')]
            if;'{FETCHED_SKILL}' == '{v:UNIT_SELECTED_SKILL}'
                game_var;AUX_STR;"{v:AUX_STR}" + "'{v:SKILL_TO_REORDER}',"
                give_skill;{unit};{v:SKILL_TO_REORDER};no_banner

            elif;'{FETCHED_SKILL}' == '{v:SKILL_TO_REORDER}'
                game_var;AUX_STR;"{v:AUX_STR}" + "'{v:UNIT_SELECTED_SKILL}',"
                give_skill;{unit};{v:UNIT_SELECTED_SKILL};no_banner

            else
                game_var;AUX_STR;"{v:AUX_STR}" + "'{FETCHED_SKILL}',"
                give_skill;{unit};{FETCHED_SKILL};no_banner
            end

        endf

        set_unit_field;{unit};EquippedSkills;[{v:AUX_STR}]
    end

This command isn't strictly necessary, but it makes me happy. And wait a second, this event looks really familiar. We basically already wrote it. It's almost the same as the `Skill_Swap_Replace`. Only two differences.

The first difference is the loop removing all of the skills first. This is necessary because we can end up in the situation when reordering of trying to add a skill that already exists, which will fail.

The second difference is that we have two conditions. Not only are we looking for `{v:UNIT_SELECTED_SKILL}`, we're also looking for `{v:SKILL_TO_REORDER}`. If you see the first, you need to add the second in its place, and vise versa.



## Step 7: Wait, How Do We Get NEW Skills On Units?

Very astute question. At this point, all we've done is made a way to swap around already learned skills. We've also removed all skills from all units. Time to remedy that. To do that, we need to look at our trusty friend `ClassData` again. You know what that means. Back to Python we go~!

|Event|Trigger
|-|-
|`Check_Skill_Unlock`|unit_level_up


    #pyev1
    cur_unit=unit
    skillnid=None

    skltmp=[]
    if len(cur_unit.get_field('LearnedSkills')):
        skltmp=cur_unit.get_field('LearnedSkills')

    clstmp=[]
    if len(cur_unit.get_field('MasteredClasses')):
        clstmp=cur_unit.get_field('MasteredClasses')

    equtmp=[]
    if len(cur_unit.get_field('EquippedSkills')):
        equtmp=cur_unit.get_field('EquippedSkills')


    if cur_unit.level==5:
        for line in game.get_data('ClassData'):
            if unit.klass==line.nid:
                skltmp.append(line.skill1)
                skillnid=line.skill1
                $set_unit_field cur_unit 'LearnedSkills' skltmp

    elif cur_unit.level==15:
        for line in game.get_data('ClassData'):
            if unit.klass==line.nid:
                skltmp.append(line.skill2)
                skillnid=line.skill2
                $set_unit_field cur_unit 'LearnedSkills' skltmp

                clstmp.append(line.nid)
                $set_unit_field cur_unit 'MasteredClasses' clstmp

    if skillnid is not None:
        if str(skillnid) not in unit.get_field('EquippedSkills') and len(unit.get_field('EquippedSkills')) < game.game_vars.get('SKILL_SWAP_CAP'):

            equtmp.append(skillnid)

            $set_unit_field cur_unit 'EquippedSkills' equtmp
            $give_skill cur_unit skillnid

        else:
            $gvar 'NEW_SKILL_TO_SWAP_IN' skillnid
            $trigger_script 'Global Skill_Swap_Level_Up' cur_unit

This script runs on every unit's level up. It looks complicated, but we'll walk through it. And trust me, you wouldn't want to see it in event script, especially if you need to extend it.

The first couple of statements just set our variables to known values (and define them as empty lists so we can append to them later). Or, if the unit already has values in our important fields, we use those. Don't want to overwrite them and ruin all our hard work.

Once we get into the thick of it, the first block just checks if a unit is level 5. As per our assumptions, all units learn their first skill at level 5. Loop in `ClassData` until you find the unit's class. Then stick in our `LearnedSkills` pool.

The second block is much the same thing, except we also assume we've mastered the class upon learning the second skill. So also update the `MasteredClasses` much the same way.

Now, we should probably add this skill to our unit offially. We don't want to have to wait until basecamp to sub it in. We check to see if the `skillnid` is set. If so, we automatically assign it if there's room. If not, we trigger our very last script.

## Step 8: Swap Skills on Level Up

If we have full skills, but we just learned Aether, it'd be really sad to not be able to equip it immediately. That's where this event comes into play.

|Event|Trigger
|-|-
|`Skill_Swap_Level_Up`|`Check_Skill_Unlock`

    game_var;AUX_STR;""

    #Create a list of equipped skills
    game_var;EQUIPPED_SKILLS;','.join([s for s in u('{unit}').get_field('EquippedSkills')])

    #If you have no equipped skills, add a dummy skill called 'Add_New_Skill'
    if;len(unit.get_field('EquippedSkills')) == 0
        game_var;EQUIPPED_SKILLS;"Add_New_Skill"

    #Or, if you have skills, but you don't have the max number of swappable skills, also add the summy skill.
    elif;len(unit.get_field('EquippedSkills')) < {v:SKILL_SWAP_CAP}
        game_var;EQUIPPED_SKILLS;"{v:EQUIPPED_SKILLS},Add_New_Skill"
    end

    #Make a table of the learned skills so you can see your options for swapping skills
    table;UNIT_RIGHT_SKILLS;{v:NEW_SKILL_TO_SWAP_IN};Learn New Skill?;{v:SKILL_SWAP_CAP},1;100;top_right;menu_bg_base;type_skill;center

    #Make a choice for the player to select which skill to swap out
    choice;UNIT_SELECTED_SKILL;Equipped Skills;{v:EQUIPPED_SKILLS};100;vert;top_left;;;type_skill;{v:SKILL_SWAP_CAP},1;center;backable

    #Make a table with the new skill as the only selection
    choice;SKILL_TO_LEARN;Learn New Skill?;{v:NEW_SKILL_TO_SWAP_IN};100;vert;top_right;;;type_skill;{v:SKILL_SWAP_CAP},1;center;backable

    rmtable;UNIT_RIGHT_SKILLS

    if;'{v:SKILL_TO_LEARN}' != 'BACK'
        game_var;AUX_STR;""

        for;FETCHED_SKILL;[s for s in u('{unit}').get_field('EquippedSkills')]
            remove_skill;{unit};{FETCHED_SKILL};no_banner
            if;'{FETCHED_SKILL}' == '{v:UNIT_SELECTED_SKILL}'
                game_var;AUX_STR;"{v:AUX_STR}" + "'{v:SKILL_TO_LEARN}',"
                give_skill;{unit};{v:SKILL_TO_LEARN}
            else
                game_var;AUX_STR;"{v:AUX_STR}" + "'{FETCHED_SKILL}',"
                give_skill;{unit};{FETCHED_SKILL};no_banner
            end

        endf

        set_unit_field;{unit};EquippedSkills;[{v:AUX_STR}]
    end


Look familiar again? This is a mashup of `Skill_Swap_Reorder` and `Skill_Swap_Setup`. Nothing new under the sun. Only this time, we're building a list of skills that can be learned with only one item, namely, the new skill.

This step could be done more cleanly, but I just wanted to demonstrate how easy it is to hook into this framework once you have it up and running. Don't be afraid to hack and slash, using pieces that already exist to create what you're envisioning. 

## Step 9: Next Steps

Now everything is done. Assuming this guide hasn't rotted from neglect, that is. You did remember remove that offending line that makes everyone promote from Knight and Paladin right? 

Either way, congrats on making it this far. I hope this guide was of some use to you. You're well on your way to skill swapping in your very own project. Your next steps are all up to you. How will you assign `MasteredClasses` to pre-promotes? (Hint, the answer is always events.) Will you add more skills? Will you add personal or secret skills? The possibilitess are endless. Happy debugging!