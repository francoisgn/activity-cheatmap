"""Built-in pixel art for the `sprite` pattern.

Text-art format, 7 rows max (row 0 = Sunday): `#` or `4` = darkest,
`3`, `2`, `1` = lighter greens, space = empty (see patterns.load_text_art).
"""

from __future__ import annotations

SPRITES: dict[str, list[str]] = {
    "clawd": ["", " #######", " # ### #", "#########", " #######", " # # # #"],
    "invader": ["  #     #", "   #   #", "  #######", " ## ### ##", "###########", "# ####### #", "# #     # #"],
    "ghost": ["  ###", " #####", "## # ##", "#######", "#######", "#######", "# # # #"],
    "heart": ["", " ## ##", "#######", "#######", " #####", "  ###", "   #"],
    # 2020 scenes, one per year (up to 51 columns: a year has 53, one spare on each side)
    "covid-mask": [
        "             3 3     444   444  4   4 444 4444",
        " 4444444    34443   4   4 4   4 4   4  4  4   4",
        " 4 444 4   3442443  4     4   4 4   4  4  4   4",
        "441111144   42224   4     4   4 4   4  4  4   4",
        " 4111114   3442443  4     4   4 4   4  4  4   4",
        " 4 4 4 4    34443   4   4 4   4  4 4   4  4   4",
        "             3 3     444   444    4   444 4444",
    ],
    "covid-sleep": [
        "                33333  222        333 333 3 3 3 33",
        " 4444444            3    2        3   3 3 3 3 3 3 3",
        " 4244424   222     3    2         3   3 3 3 3 3 3 3",
        "444444444    2    3    2          3   3 3 3 3 3 3 3",
        " 4444444    2    3     222        333 333  3  3 33",
        " 4 4 4 4   2    3",
        "           222  33333",
    ],
    "covid-2020": [
        "             444   444   444   444",
        " 4444444    4   4 4   4 4   4 4   4    4444444",
        " 4 444 4        4 4  44     4 4  44    4 444 4",
        "441111144      4  4 4 4    4  4 4 4   441111144",
        " 4111114      4   44  4   4   44  4    4111114",
        " 4 4 4 4     4    4   4  4    4   4    4 4 4 4",
        "            44444  444  44444  444",
    ],
    "stay-home": [
        " 4444 44444  444  4   4     4   4  444  4   4 44444",
        "4       4   4   4 4   4     4   4 4   4 44 44 4",
        "4       4   4   4  4 4      4   4 4   4 4 4 4 4",
        " 444    4   44444   4       44444 4   4 4 4 4 4444",
        "    4   4   4   4   4       4   4 4   4 4   4 4",
        "    4   4   4   4   4       4   4 4   4 4   4 4",
        "4444    4   4   4   4       4   4  444  4   4 44444",
    ],
}

# The 2020 special of the menu: sprite name -> description.
SCENES_2020: dict[str, str] = {
    "covid-mask": "Clawd wearing a mask, a virus and COVID",
    "covid-sleep": "Clawd sleeping through it: z Z z, COVID in the corner",
    "covid-2020": "two masked Clawds around 2020",
    "stay-home": "STAY HOME",
}
