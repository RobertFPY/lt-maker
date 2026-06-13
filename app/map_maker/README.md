# Steps for making a new palette for the map maker

## Your tileset png is set up similarly to how the main png is organized in monastery_outdoors palette

1. Create a folder in map_maker/palettes/ with the name of your new palette.
2. Copy the files from another palette folder to your new palette folder

> Note: If you are making an indoor palette, then you would of course copy another indoor palette's files to your new palette folder.

3. We will be overwriting the files in your new folder with the colors of your main.png
4. Navigate to app/map_maker/scripts/simple_palette_exchanger.py
5. You will see in the middle of the script, three lines of importance:

```python
color_change_these_images = ['app/map_maker/palettes/monastery_outdoors/road.png'],
original_palette = 'app/map_maker/palettes/autumn_outdoors/main.png'
new_palette = 'app/map_maker/palettes/monastery_outdoors/main.png'
```

6. Modify `original_palette` to point to the original main.png of the folder you grabbed, for instance `'app/map_maker/palettes/monastery_outdoors/main.png'`.
7. Modify `new_palette` to point to your new main.png, which should be kept in some other location for now, so it doesn't get overwritten by the script.
8. Modify `color_change_these_images` to `['app/map_maker/palettes/{your_palette}/*.png]`
9. Run the python script from the main `lt-maker` directory: `python -m app.map_maker.scripts.palette_generation.simple_palette_exchanger`
10. Check that it made the expected changes to your new palette folder
11. If it checks out, modify the metadata.json file to match the correct value for your new palette.
12. Use it in the map maker!

