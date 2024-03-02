(AddingLanguageSupport)=
# Adding Language Support

Some LT games are made for languages using non-Latin alphabets. While LT does not have native support for these alphabets, it's straightforward to add them.

> NOTA BENE: You **must** have your editor **closed** while doing this, otherwise there is risk of data corruption.

First, download a font which supports the alphabet of your choice. Below are a few recommendations - some of the developers have personally tested these and confirmed them to be suitable for use in LT.

| Language | Font |
| ------ | ------ |
| **Mandarin Chinese** | [Firefly Sung](https://github.com/rougier/freetype-gl/blob/master/fonts/fireflysung.ttf) |
| **Japanese** | [PixelMPlus](https://itouhiro.hatenablog.com/entry/20130602/font) |

Next, move the font into your project's fonts folder, located at `MyProject.ltproj/resources/fonts`.

Finally, open up the `fonts.json` file in that directory. You will see a list of entries like this:

```json
{
        "nid": "bconvo",
        "fallback_ttf": null,
        "fallback_size": 16,
        "default_color": "black",
        "outline_font": false,
        "palettes": {
            "black": [
                [
                    40,
                    40,
                    40,
                    255
                ],
                [
                    184,
                    184,
                    184,
                    255
                ]
            ]
        }
}
```

In order to add your new font (let's say you decided to download `fireflysung.ttf`), you will change the `fallback_ttf` field to `fireflysung.ttf`. You may also need to play with the `fallback_size` field in order to ensure your font renders correctly: for example, the `PixelMPlus` font comes in a 10-pixel and 12-pixel version, and will render very badly if you do not set the size accordingly.

Once you change those two fields, you're done!

# Special Notes

Some fonts in the game render with outlines. We support these as well! However, it requires additional work for certain font-styles. You must set the `outline_font` to `true` for these fonts (although this has already been set for the most common outlined fonts), and you must order each color in the palette such that the primary text color is the first RGBA value (in the example above, `black` has a primary color of `40, 40, 40, 255`), and the secondary text color is the second RGBA value (again, in the example above, the secondary color is `184, 184, 184, 255`). The primary will be used for the main text body, while the secondary will be used as the outline.