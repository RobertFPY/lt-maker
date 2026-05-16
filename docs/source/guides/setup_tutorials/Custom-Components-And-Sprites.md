# Custom Components and Sprites

_last updated 2024-11-13_

If you've developed your own custom components or engine sprites, those custom assets will be necessary to run your game/project. However, up until now your only option to distribute these custom assets was:

1. Petition rainlash to add your custom components to the master branch of the engine, so that others using your custom assets would have access to them.
2. Distribute your own bespoke version of the engine to your players that includes the custom assets.

Well, now there's a third option. **Project Specific Custom Components and Sprites**

## Project Specific Custom Components

In your project's *resources* directory, there should be a directory called `custom_components`. Within that directory, there'll be two files: `custom_item_components.py` and `custom_skill_components.py`.

These will be loaded at runtime when you start the editor or the engine and load up your project, so players of your game can use the canonical Lex Talionis engine with your .ltproj project and its bespoke custom components without any friction.

To learn how to write components, you should reference the other component tutorials in this section, as well as the existing component code within the engine, located in `app/engine/item_components/` and `app/engine/skill_components`

## Project Specific Custom Sprites

As with custom components, your project's *resources* directory should contain a directory called `custom_sprites`. This directory will contain nothing at all by default.

Any image placed within this directory will take precedence over an image with the same name in the *sprites* directory of the engine. You can do this to overwrite various engine graphics without touching the engine directory directly, such as the title screen image.