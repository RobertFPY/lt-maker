(PythonEventing)=
# Python Eventing

_last updated v0.1_

*If you haven't read [Event-Overview](EventOverview) yet, please do so before reading this article.*

While the event script can be written with the traditional Event Commands (as demonstrated in the [Event Commands Section](EventCommands)), the intrepid scripter can take advantage of Python syntax to achieve more sophisticated functionality. Rather than using a simplified custom syntax, the Python Eventing engine allows you to write scripts in fully integrated Python.

## Why use Python Eventing?

For the casual user, there is no real advantage (or disadvantage) in doing so.

For users that use eventing to implement abilities, do calculations, and so on, the advantages are numerous.

For example: working with variables and doing calculations in original command form is clumsy, as there are no intuitive semantics for assigning and accessing non-primitive variables. Moreover, Event Script does not distinguish well between string objects and non-string objects, leading to situations like these:

```
game_var;seen_maps;v('seen_maps') + [v('next')]
game_var;next_reward;'{v:the_reward}'
```

Which are difficult to parse - `[v('next')]` is a variable name wrapped in a string wrapped inside a variable getter wrapped inside a list wrapper, placed as the argument of a variable setter. `'{v:the_reward}'` is a variable string getter wrapped inside a string. These are needless levels of indirection. In Python Eventing, this would be rendered as:

```
seen_maps.append(next)
next_reward = the_reward
```

Ultimately, Python Eventing is a cleaner and more maintainable method of writing events.

Python Eventing also gives you access to all standard Python functions, notably including list operations. You can sort lists, create lists, append to lists, and so forth, that are difficult to impossible to do in traditional event script.

## Python Event Sample

For the most part, there are only three things that one needs to know about Python Eventing.

1) To have a script use the Python Eventing engine, you must include the text `#pyev1` at the top.
2) There are three important characters when writing an LT command. `$` at the beginning of a line indicates that you're calling an event command. ` ` - a space - is the delimiter for event command arguments. Finally, `,` - the comma - ends the command and delimits the beginning of the section of flags. For example, to add a portrait, instead of the event script `add_portrait;Seth;left;no_block`, you might do `$add_portrait "Seth" "left", no_block`. You can use parenthesis if you need to add spaces to an argument: `$add_portrait ("Seth" + "_hurt") "left", no_block`.
3) All lines that do not begin with a `$` character will be parsed as normal Python.

Here are some snippets that illustrate the appearance and syntax of Python Events.

### Dialogue

The following event snippet creates a SpeakStyle - a collection of formatting hints for a speak command. In this case, it indicates that the `eirika` style refers to a style using `Eirika` as the speaker, and has a text box 3 lines tall.

> **N.B.** The `say` command appears to spread out over five lines. You can format individual commands across multiple lines using line breaks - usually entered via the `Shift-Enter` key combination. You **cannot** use normal newlines (input via the `Enter` key) in the middle of event commands.

```python
#pyev1

eirika = SpeakStyle('eirika_speak_style', speaker="Eirika", num_lines=3)

$add_portrait eirika "FarLeft" ExpressionList=["Smile", "CloseEyes"] Slide="right"
$say eirika "Four score and seven years ago"
            "our fathers brought forth, upon this continent,"
            "a new nation, conceived in liberty,"
            "and dedicated to the proposition"
            "that all men are created equal." FontColor="green"
$remove_portrait eirika
```

### For Loop

The following event snippet spawns 5 civilians near the unit `Bone`. For those familiar with Python, this is an ordinary for loop. It's important to note that you can put most normal event commands inside Python for loops as well.

```python
#pyev1
for i in range(5):
    $make_generic str(i) "Citizen" 1 "player"
    $add_unit str(i) "Bone" "immediate" "closest"
```

### Variables

The following event is an example of how you might use python variables to hold onto references to specific units and ease calculation. In normal event script, these would be crammed into single, dense, unreadable lines.

```python
#pyev1

seth_unit = u("Seth")
reduced_hp = seth_unit.get_current_hp() - 5
reduced_luck = seth_unit.stats['LCK'] - 5

$set_stats seth_unit {"HP": reduced_hp, "LCK": reduced_luck}, immediate

$add_portrait seth_unit "Right"
$say seth_unit "What happened to my HP?" NumLines=1
```