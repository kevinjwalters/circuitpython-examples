### MIT License

### Copyright (c) 2020 Kevin J. Walters

### Permission is hereby granted, free of charge, to any person obtaining a copy
### of this software and associated documentation files (the "Software"), to deal
### in the Software without restriction, including without limitation the rights
### to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
### copies of the Software, and to permit persons to whom the Software is
### furnished to do so, subject to the following conditions:

### The above copyright notice and this permission notice shall be included in all
### copies or substantial portions of the Software.

### THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
### IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
### FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
### AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
### LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
### OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
### SOFTWARE.


import time
import gc
import os
import struct
import random

import board
import displayio
from displayio import Group
import terminalio
import digitalio

import neopixel
from adafruit_display_text.label import Label


### Set to True for blue flashing when devices are annoucing players' names
JG_FLASH = True  ### TODO DISABLE THIS FOR THE ADAFRUIT RELEASE

### Top y position of first choice and pixel separate between choices
top_y_pos = 60
choice_sep = 60

BLUE=0x0000ff
BLACK=0x000000

DIM_TXT_COL_FG = 0x505050
DEFAULT_TXT_COL_FG = 0xa0a0a0
CURSOR_COL_FG = 0xc0c000
IWELCOME_COL_FG = 0x000010
WELCOME_COL_FG = 0x0000f0
BWHITE_COL_FG = 0xffffff
PLAYER_NAME_COL_FG = 0xc0c000
PLAYER_NAME_COL_BG = BLACK
OPP_NAME_COL_FG = 0x00c0c0
OPP_NAME_COL_BG = BLACK
ERROR_COL_FG = 0xff0000
TITLE_TXT_COL_FG = 0xc000c0
INFO_COL_FG = 0xc0c000
INFO_COL_BG = 0x000080
GS_COL = 0x202020
QM_SORT_FG = 0x808000
QM_SORTING_FG = 0xff8000
RED_COL = 0xff0000
ORANGE_COL = 0xff8000
YELLOW_COL = 0xffff00
DRAWLOSE_COL = 0x0000f0

### NeoPixel colours
GAMENO_GREEN = 0x001200
ROUNDNO_WHITE = 0x0181818
PLAYER_COL = 0xff0000
SCORE_COLS = (0x200600, 0x201300, 0x001200, 0x000020, 0x08000e, 0x140618)

### Colours for NeoPixels on display-less CPB
### Should be dim to avoid an opponent seeing choice from reflected light
### NB: these get << 5 in showPlayerVPlayerNeoPixels
CHOICE_COL = (0x040000,  ### Red for Rock
              0x030004,  ### Purple for Paper
              0x000004   ### Sapphire blue for Scissors
             )


### TODO - HACK TIL I CLEAN THIS ALL UP
DISPLAY_WIDTH = 240
DISPLAY_HEIGHT = 240
FONT_WIDTH = 6
FONT_HEIGHT = 14
SPRITE_SIZE = 16


def loadSprites(disp, filename, transparent=0):
    """Load horizontal sprite sheet if running with a display
    """
    if disp is None:
        return (None, None, None)

    import adafruit_imageload
    s_bit, s_pal = adafruit_imageload.load(filename,
                                           bitmap=displayio.Bitmap,
                                           palette=displayio.Palette)
    sprite_size = s_bit.height
    num_sprites = s_bit.width // s_bit.height
    
    ### For default value, make the first colour transparent
    if transparent is not None:
        s_pal.make_transparent(transparent)

    ### Make some sprites from the sprite sheet
    ### Sprites can only be in one layer (Group) at a time, need two copies
    ### to allow representation of a draw on screen
    sprites = []
    opp_sprites = []
    for idx in range(num_sprites):
        sprite = displayio.TileGrid(s_bit, pixel_shader=s_pal,
                                    width=1, height=1,
                                    tile_width=sprite_size, tile_height=sprite_size)
        sprite[0] = idx
        sprites.append(sprite)

        opp_sprite = displayio.TileGrid(s_bit, pixel_shader=s_pal,
                                        width=1, height=1,
                                        tile_width=sprite_size, tile_height=sprite_size)
        opp_sprite[0] = idx
        opp_sprites.append(opp_sprite)
        
    return (sprites, opp_sprites, sprite_size)


def choiceToPixIdx(idx, length=10):
    """This maps the three choices to three pixels.
       It is also used for game and round numbers.
       The starting position is 0 which is just left of USB connector
       on Circuit Playground boards and going clockwise - this avoids
       the NeoPixels near the buttons which are likely to be under fingers."""
    return -idx % length


def getDisplayInfo(disp):
    return (disp.width, disp.height, disp.brightness)


def getFontInfo():
    """Return width, height for the 6x14 terminalio classic monospaced font.
    """
    return terminalio.FONT.get_bounding_box()


def fadeUpDown(disp, direction, brightness, duration=0.8, steps=10):
    """Fade the display up or down by varything the brightness of the backlight."""

    if disp is None:
        return

    if duration == 0.0:
        disp.brightness = 0.0 if direction == "down" else brightness
        return

    if direction == "down":
        step_iter = range(steps - 1, -1, -1)
    elif direction == "up":
        step_iter = range(1, steps + 1)
    else:
        raise ValueError("up or down")

    time_step = duration / steps
    for bri in [idx * brightness / steps for idx in step_iter]:
        disp.brightness = bri
        time.sleep(time_step)


def emptyGroup(dio_group):
    """Recursive depth first removal of anything in a Group.
       Intended to be used to clean-up a previous screen
       which may have elements in the new screen
       as elements cannot be in two Groups at once since this
       will cause "ValueError: Layer already in a group".
       This only deletes Groups, it does not del the non-Group content."""
    if dio_group is None:
        return

    ### Go through Group in reverse order
    for idx in range(len(dio_group) - 1, -1, -1):
        ### Avoiding isinstance here as Label is a sub-class of Group!
        if (type(dio_group[idx]) == Group):
            emptyGroup(dio_group[idx])
        del dio_group[idx]
    del dio_group  ### TODO - this line achieve nothing???


def showChoice(disp, pix, disp_group, sprites,
               ch_idx,
               game_no=None, round_no=None, rounds_tot=None,
               won_sf=None, drew_sf=None, lost_sf=None):
    """TODO DOC"""
    if disp is None:
        pix.fill(BLACK)
        pix[choiceToPixIdx(ch_idx)] = CHOICE_COL[ch_idx]
        return disp_group
        
    emptyGroup(disp_group)
    ### Would be slightly better to create this Group once and re-use it
    round_choice_group = Group(max_size=3)

    if round_no is not None:
        title_dob = Label(terminalio.FONT,
                          text="Game {:d}  Round {:d}/{:d}".format(game_no,
                                                                   round_no,
                                                                   rounds_tot),
                          scale=2,
                          color=TITLE_TXT_COL_FG)
        title_dob.x = round((DISPLAY_WIDTH - len(title_dob.text) * 2 * FONT_WIDTH) // 2)
        title_dob.y = round(FONT_HEIGHT // 2)
        round_choice_group.append(title_dob)

    if won_sf is not None:
        gamesum_dob = Label(terminalio.FONT,
                            text="Won {:d} Drew {:d} Lost {:d}".format(won_sf,
                                                                       drew_sf,
                                                                       lost_sf),
                            scale=2,
                            color=TITLE_TXT_COL_FG)
        gamesum_dob.x = round((DISPLAY_WIDTH - len(gamesum_dob.text) * 2 * FONT_WIDTH) // 2)
        gamesum_dob.y = round(DISPLAY_HEIGHT - 2 * FONT_HEIGHT // 2)
        round_choice_group.append(gamesum_dob)

    s_group = Group(scale=3, max_size=1)
    s_group.x = 32
    s_group.y = (DISPLAY_HEIGHT - 3 * SPRITE_SIZE) // 2
    s_group.append(sprites[ch_idx])

    round_choice_group.append(s_group)

    disp.show(round_choice_group)
    return round_choice_group


def blankScreen(disp, pix, disp_group):
    """A blank screen used to hide any serial console output."""
    if disp is None:
        return disp_group

    emptyGroup(disp_group)
    inky_void_group = Group(max_size=1)
    disp.show(inky_void_group)
    return inky_void_group


def introductionScreen(disp, pix, disp_group, sample, sprites, button_y_pos):
    """Introduction screen."""
    new_group = disp_group

    if disp is not None:
        emptyGroup(disp_group)
        intro_group = Group(max_size=7)
        welcometo_dob = Label(terminalio.FONT,
                              text="Welcome To",
                              scale=3,
                              color=IWELCOME_COL_FG)
        welcometo_dob.x = (DISPLAY_WIDTH - 10 * 3 * FONT_WIDTH) // 2
        ### Y pos on screen looks lower than I would expect
        welcometo_dob.y = 3 * FONT_HEIGHT // 2
        intro_group.append(welcometo_dob)

        extra_space = 8
        spacing = 3 * SPRITE_SIZE + extra_space
        for idx, sprite in enumerate(sprites):
            s_group = Group(scale=3, max_size=1)
            s_group.x = -96
            s_group.y = round((DISPLAY_HEIGHT - 1.5 * SPRITE_SIZE) // 2
                              + (idx - 1) * spacing)
            s_group.append(sprite)
            intro_group.append(s_group)

        arena_dob = Label(terminalio.FONT,
                          text="Arena",
                          scale=3,
                          color=IWELCOME_COL_FG)
        arena_dob.x = (DISPLAY_WIDTH - 5 * 3 * FONT_WIDTH) // 2
        arena_dob.y = DISPLAY_HEIGHT - 3 * FONT_HEIGHT // 2
        intro_group.append(arena_dob)

        new_group = intro_group
        disp.show(intro_group)

    ### The color modification here is fragile as it only works
    ### if the text colour is blue, i.e. data is in lsb only
    sample.play("welcome-to")
    while sample.playing():
        if disp is not None and intro_group[0].color < WELCOME_COL_FG:
            intro_group[0].color += 0x10
            time.sleep(0.120)

    onscreen_x_pos = 96

    ### Move each sprite onto the screen while saying its name with wav file
    anims = (("rock", 10, 1, 0.050),
             ("paper", 11, 2, 0.050),
             ("scissors", 7, 3, 0.050))
    for idx, (audio_name, x_shift, grp_idx, delay_s) in enumerate(anims):
        if disp is None:
            showChoice(disp, pix, disp_group, sprites, idx)
        sample.play(audio_name)
        ### Audio needs to be long enough to finish movement
        while sample.playing():
            if disp is not None:
                if intro_group[grp_idx].x < onscreen_x_pos:
                    intro_group[grp_idx].x += x_shift
                    time.sleep(delay_s)

    ### Set NeoPixels back to black
    if disp is None:
        pix.fill(BLACK)

    sample.play("arena")
    while sample.playing():
        if disp is not None and intro_group[4].color < WELCOME_COL_FG:
            intro_group[4].color += 0x10
            time.sleep(0.060)

    ### Button Guide for those with a display
    if disp is not None:
        left_dob = Label(terminalio.FONT,
                         text="< Select    ",
                         scale=2,
                         color=INFO_COL_FG,
                         background_color=INFO_COL_BG)
        left_width = len(left_dob.text) * 2 * FONT_WIDTH
        left_dob.x = -left_width
        left_dob.y = button_y_pos
        intro_group.append(left_dob)

        right_dob = Label(terminalio.FONT,
                          text=" Transmit >",
                          scale=2,
                          color=INFO_COL_FG,
                          background_color=INFO_COL_BG)
        right_width = len(right_dob.text) * 2 * FONT_WIDTH
        right_dob.x = DISPLAY_WIDTH
        right_dob.y = button_y_pos
        intro_group.append(right_dob)

        ### Move left button text onto screen, then right
        steps = 20
        for x_pos in [left_dob.x + round(left_width * x / steps)
                      for x in range(1, steps + 1)]:
            left_dob.x = x_pos
            time.sleep(0.06)

        for x_pos in [right_dob.x - round(right_width * x / steps)
                      for x in range(1, steps + 1)]:
            right_dob.x = x_pos
            time.sleep(0.06)

        time.sleep(8)  ### leave on screen for further 6 seconds

    return new_group

pl_x_pos = pl_y_cur_pos = pl_y_off = None  ### TODO - TIDY UP THIS MONSTROSITY

def playerListScreen(disp, pix, disp_group, max_players):
    if disp is None:
        return disp_group

    emptyGroup(disp_group)
    playerlist_group = Group(max_size=max_players)

    global pl_x_pos, pl_y_cur_pos, pl_y_off  ### TODO - TIDY UP THIS MONSTROSITY
    pl_x_pos = 20
    pl_y_cur_pos = 7
    pl_y_off = 2 * FONT_HEIGHT + 1
    disp.show(playerlist_group)
    return playerlist_group


def addPlayerDOB(name, p_group):
    global pl_y_cur_pos

    pname_dob = Label(terminalio.FONT,
                      text=name,
                      scale=2,
                      color=DEFAULT_TXT_COL_FG)
    pname_dob.x = pl_x_pos
    pname_dob.y = pl_y_cur_pos
    pl_y_cur_pos += pl_y_off
    p_group.append(pname_dob)


def flashNeoPixels(pix, col):
    """The briefest of flashes on the NeoPixels."""
    pix.fill(col)
    pix.fill(BLACK)


def showGameRound(disp, pix,
                  game_no=0, round_no=0, rounds_tot=None):
    """Show the game and round number on NeoPixels for screenless devices.
       Only used for Gizmo-less CPB."""
    if disp is None:
        ### Gradually light NeoPixels in green to show game number
        for p_idx in range(game_no):
            pix[choiceToPixIdx(p_idx)] = GAMENO_GREEN
            time.sleep(0.5)

        time.sleep(2)

        ### Flash white five times at position to indicate round number
        bg_col = pix[round_no - 1]
        for _ in range(5):
            pix_idx = choiceToPixIdx(round_no - 1)
            pix[pix_idx] = ROUNDNO_WHITE
            time.sleep(0.1)
            pix[pix_idx] = bg_col
            time.sleep(0.3)

        pix.fill(BLACK)


def showGameResultScreen(disp, pla, disp_group, sco, rounds_tot=None):
    """Display a high score table with some visual sorting."""
    fadeUpDown(disp, "down")
    emptyGroup(disp_group)

    ### Score list group + background + question mark for sorting
    gs_group = Group(max_size=4)

    ### TODO increase size and split this into two
    ### Add a background with centered GAME over SCORES
    bg_scale = 6
    sbg_dob1 = Label(terminalio.FONT,
                     text="GAME",
                     scale=bg_scale,
                     color=GS_COL)
    sbg_dob1.x = (DISPLAY_WIDTH - 4 * bg_scale * FONT_WIDTH) // 2
    sbg_dob1.y = DISPLAY_HEIGHT // 3
    sbg_dob2 = Label(terminalio.FONT,
                     text="SCORES",
                     scale=bg_scale,
                     color=GS_COL)
    sbg_dob2.x = (DISPLAY_WIDTH - 6 * bg_scale * FONT_WIDTH) // 2
    sbg_dob2.y = DISPLAY_HEIGHT // 3 * 2
    gs_group.append(sbg_dob1)
    gs_group.append(sbg_dob2)
    disp.show(gs_group)
    fadeUpDown(disp, "up")

    ### Calculate maximum length player name
    ### and see if scores happen to already be in order
    max_len = 0
    prev_score = sco[0]
    descending = True
    for idx, (name, macaddr) in enumerate(pla):
        max_len = max(max_len, len(name))
        if sco[idx] > prev_score:
            descending = False
        prev_score = sco[idx]

    fmt = "{:" + str(max_len) + "s} {:2d}"
    x_pos = (DISPLAY_WIDTH - (max_len + 3) * 2 * FONT_WIDTH) // 2
    scale = 2
    spacing = 4 if len(pla) <= 6 else 0
    top_y_pos = round((DISPLAY_HEIGHT
                      - len(pla) * scale * FONT_HEIGHT
                      - (len(pla) - 1) * spacing) // 2
                      + scale * FONT_HEIGHT // 2)
    scores_group = Group(max_size=len(pla))
    gs_group.append(scores_group)
    for idx, (name, macaddr) in enumerate(pla):
        op_dob = Label(terminalio.FONT,
                       text=fmt.format(name, sco[idx]),
                       scale=2,
                       color=(PLAYER_NAME_COL_FG if idx == 0 else OPP_NAME_COL_FG))
        op_dob.x = x_pos
        op_dob.y = top_y_pos + idx * (scale * FONT_HEIGHT + spacing)
        scores_group.append(op_dob)
        time.sleep(0.2)

    ### Sort the entries if needed
    sort_scores = list(sco)  ### Make an independent local copy
    if not descending:
        empty_group = Group()  ### minor hack to aid swaps in scores_group
        step = 4
        qm_dob = Label(terminalio.FONT,
                       text="?",
                       scale=2,
                       color=QM_SORT_FG)
        qm_dob.x = round(x_pos - 1.5 * scale * FONT_WIDTH)
        gs_group.append(qm_dob)
        while True:
            swaps = 0
            for idx in range(0, len(sort_scores) -1):
                above_score = sort_scores[idx]
                above_y = scores_group[idx].y
                below_y = scores_group[idx + 1].y
                qm_dob.y = (above_y + below_y) // 2
                if above_score < sort_scores[idx + 1]:
                    qm_dob.text = "<"
                    qm_dob.color = QM_SORTING_FG
                    swaps += 1

                    ### make list of steps
                    range_y = below_y - above_y
                    offsets = list(range(step, range_y + 1, step))
                    ### Ensure this goes to the exact final position
                    if offsets[-1] != range_y:
                        offsets.append(range_y)

                    for offset in offsets:
                        scores_group[idx].y = above_y + offset
                        scores_group[idx + 1].y = below_y - offset
                        time.sleep(0.040)

                    ### swap the scores around
                    sort_scores[idx] = sort_scores[idx + 1]
                    sort_scores[idx + 1] = above_score

                    ### swap the graphical objects around using empty_group
                    ### to avoid ValueError: Layer already in a group
                    old_above_dob = scores_group[idx]
                    old_below_dob = scores_group[idx + 1]
                    scores_group[idx + 1] = empty_group
                    scores_group[idx] = old_below_dob
                    scores_group[idx + 1] = old_above_dob

                    qm_dob.text = "?"
                    qm_dob.color = QM_SORT_FG
                    time.sleep(0.2)
                else:
                    time.sleep(0.6)

            if swaps == 0:
                break   ### Sort complete if no values were swapped
        gs_group.remove(qm_dob)
    return gs_group


def showGameResultNeoPixels(pix, pla, sco, rounds_tot=None):
    """Display a high score table on NeoPixels.
       Sorted into highest first order then displayed by
       flashing position pixel to indicate player number and
       gradually lighting up pixels in a circle using rainbow
       colours for each revolution of the NeoPixels starting at orange.
       """
    idx_n_score = [(s, sco[s]) for s in range(len(sco))]
    idx_n_score.sort(key=lambda s: s[1], reverse=True)
    num_pixels = len(pix)

    bg_col = BLACK
    for idx, score in idx_n_score:
        playerIdx = choiceToPixIdx(idx)
        for score in range(score):
            scoreIdx = choiceToPixIdx(score)
            rev = min(score // num_pixels, len(SCORE_COLS) - 1)
            pix[scoreIdx] = SCORE_COLS[rev]
            if scoreIdx == playerIdx:
                bg_col = SCORE_COLS[rev]
            time.sleep(0.09)
            pix[playerIdx] = PLAYER_COL
            time.sleep(0.09)
            pix[playerIdx] = bg_col

        for _ in range(4):
            pix[playerIdx] = bg_col
            time.sleep(0.5)
            pix[playerIdx] = PLAYER_COL
            time.sleep(0.5)

        pix.fill(BLACK)


def showGameResult(disp, pix, disp_group, pla, sco,
                   rounds_tot=None):
    new_group = disp_group
    
    if disp is None:
        showGameResultNeoPixels(pix, pla, sco, rounds_tot=rounds_tot)
    else:
        new_group = showGameResultScreen(disp, disp_group,
                                         pla, sco, rounds_tot=rounds_tot)

    if sco[0] == 0:
        sample.play("humiliation")
    elif sco[0] >= int((len(sco) - 1) * rounds_tot * 1.5):
        sample.play("excellent")

    if disp is not None:
        time.sleep(10)  ### Leave displayed scores visible

    sample.wait()
    return new_group


def showPlayerVPlayerScreen(disp, disp_group, me_name, op_name, my_ch_idx, op_ch_idx,
                            result, summary, win, draw, void):
    """Display a win, draw, lose or error message."""
    new_group = disp_group
    fadeUpDown(disp, "down")
    emptyGroup(disp_group)

    if void:
        error_tot = 3
        error_group = Group(max_size=error_tot + 1)
        ### TODO - this would benefit from having op_name on the screen
        ### Put three error messages to go on screen to match sound sample
        op_dob = Label(terminalio.FONT,
                       text=op_name,
                       scale=2,
                       color=OPP_NAME_COL_FG)
        op_dob.x = 40
        op_dob.y = FONT_HEIGHT
        error_group.append(op_dob)
        new_group = error_group  ### The return value
        disp.show(error_group)
        fadeUpDown(disp, "up", duration=0.4)
        if result is not None:
            sample.play(result)
        font_scale = 2
        for idx in range(error_tot):
            error_dob = Label(terminalio.FONT,
                              text="Error!",
                              scale=font_scale,
                              color=ERROR_COL_FG)
            error_dob.x = 40
            error_dob.y = 60 + idx * 60
            error_group.append(error_dob)
            time.sleep(0.5)  ### Small attempt to synchronise audio with text
            font_scale += 1

    else:
        ### Would be slightly better to create this Group once and re-use it
        pvp_group = Group(max_size=3)

        ### Add player's name and sprite just off left side of screen
        ### and opponent's just off right
        player_detail = [[me_name, sprites[my_ch_idx], -16 - 3 * SPRITE_SIZE,
                          PLAYER_NAME_COL_FG, PLAYER_NAME_COL_BG],
                         [op_name, opp_sprites[op_ch_idx], 16 + DISPLAY_WIDTH,
                          OPP_NAME_COL_FG, OPP_NAME_COL_BG]]
        idx_lr = [0, 1]  ### index for left and right sprite
        if win:
            player_detail.reverse()  ### this player is winner so put last
            idx_lr.reverse()

        ### Add some whitespace around winner's name
        player_detail[1][0] = " " + player_detail[1][0] + " "

        for (name, sprite,
             start_x,
             fg, bg) in player_detail:
            s_group = Group(scale=2, max_size=2)  ### Audio is choppy at scale=3
            s_group.x = start_x
            s_group.y = (DISPLAY_HEIGHT - 2 * (SPRITE_SIZE + FONT_HEIGHT)) // 2

            s_group.append(sprite)
            p_name_dob = Label(terminalio.FONT,
                               text=name,
                               scale=1,  ### This is scaled by the group
                               color=fg,
                               background_color=bg)
            ### Centre text below sprite - values are * Group scale
            p_name_dob.x = (SPRITE_SIZE - len(name) * FONT_WIDTH) // 2
            p_name_dob.y = SPRITE_SIZE + 4
            s_group.append(p_name_dob)

            pvp_group.append(s_group)

        ### max_glyphs is set to the maximum len of all the possible strings
        ### the + 1 is workaround in case a buggy version of library is used
        summary_dob = Label(terminalio.FONT,
                           text="",
                           max_glyphs=8 + 1,
                           scale=3,
                           color=BLACK)
        summary_dob.y = round(DISPLAY_HEIGHT - (3 * FONT_HEIGHT / 2))
        pvp_group.append(summary_dob)

        new_group = pvp_group  ### The return value
        disp.show(new_group)
        fadeUpDown(disp, "up", duration=0.4)

        ### Start audio half way through animations
        if draw:
            ### Move sprites onto the screen leaving them at either side
            for idx in range(16):
                pvp_group[idx_lr[0]].x += 6
                pvp_group[idx_lr[1]].x -= 6
                if idx == 8 and result is not None:
                    sample.play(result)
                time.sleep(0.2)
        else:
            ### Move sprites together, winning sprite overlaps and covers loser
            for idx in range(16):
                pvp_group[idx_lr[0]].x += 10
                pvp_group[idx_lr[1]].x -= 10
                if idx == 8 and result is not None:
                    sample.play(result)
                time.sleep(0.2)

        sample.wait()  ### Wait for first sample to finish

        if summary is not None:
            sample.play(summary)
        ### max length of sum_text must be set in max_glyphs in summary_dob
        if draw:
            sum_text = "Draw"
        elif win:
            sum_text = "You win"
        else:
            sum_text = "You lose"
        summary_dob.text = sum_text
        summary_dob.x = round((DISPLAY_WIDTH - 3 * FONT_WIDTH * len(sum_text)) // 2)

        ### Flash colours for win, fad up to blue for rest
        if not draw and win:
            colours = [YELLOW_COL, ORANGE_COL, RED_COL] * 5
        else:
            colours = [DRAWLOSE_COL * sc // 15 for sc in range(1, 15 + 1)]
        for col in colours:
            summary_dob.color = col
            time.sleep(0.120)

    sample.wait()  ### Ensure second sample has completed
    return new_group


def showPlayerVPlayerNeoPixels(pix, op_idx, my_ch_idx, op_ch_idx,
                               result, summary, win, draw, void):
    """This indicates the choices by putting the colours
       associated with rock paper scissors on the first pixel
       for the player and on subsequent pixels for opponents.
       A win brightens the winning pixel as the result audio plays.
       Pixel order is based on the game's definition and not
       the native NeoPixel list order.
       Errors are indicated by flashing all pixels but keeping the
       opponent's one dark."""

    pix_op_idx = choiceToPixIdx(op_idx)
    if void:
        if result is not None:
            sample.play(result)
        ramp_updown = (list(range(8, 128 + 1, 8))
                       + list(range(128 - 8, 0 - 1, -8)))
        ### This fills all NeoPixels so will clear the RPS choice
        for _ in range(3):
            for ramp in ramp_updown:
                pix.fill((ramp, 0, 0))  ### modulate red led from RGB
                pix[pix_op_idx] = BLACK  ### blackout the opponent pixel
                time.sleep(0.013)  ### attempt to to sync with audio

    else:
        if result is not None:
            sample.play(result)

        ### Clear the RPS choice and show the player and opponent choices
        pix.fill(BLACK)
        if draw:
            pix[0] = CHOICE_COL[my_ch_idx] << 2
            pix[pix_op_idx] = CHOICE_COL[op_ch_idx] << 2
            time.sleep(0.25)
        else:
            pix[0] = CHOICE_COL[my_ch_idx]
            pix[pix_op_idx] = CHOICE_COL[op_ch_idx]
            ### Brighten the pixel for winner
            brigten_idx = 0 if win else pix_op_idx
            for _ in range(5):
                rr, gg, bb = pix[brigten_idx]
                pix[brigten_idx] = (rr << 1, gg << 1, bb << 1)
                time.sleep(0.45)

        if summary is not None:
            sample.wait()
            sample.play(summary)
    sample.wait()  ### Ensure first or second sample have completed
    time.sleep(0.5)
    pix.fill(BLACK)


def showPlayerVPlayer(disp, pix, disp_group,
                      me_name, op_name, op_idx, my_ch_idx, op_ch_idx,
                      win, draw, void):
    new_group = disp_group
    
    if void:
        result_wav = "error"
        summary_wav = None
    elif draw:
        result_wav = None
        summary_wav = "draw"
    else:
        result_wav = winnerWav(my_ch_idx, op_ch_idx)
        summary_wav = "you-win" if win else "you-lose"

    if disp is None:
        showPlayerVPlayerNeoPixels(pix, op_idx, my_ch_idx, op_ch_idx,
                                   result_wav, summary_wav, win, draw, void)
    else:
        new_group = showPlayerVPlayerScreen(disp, disp_group,
                                            me_name, op_name, my_ch_idx, op_ch_idx,
                                            result_wav, summary_wav, win, draw, void)
    return new_group
