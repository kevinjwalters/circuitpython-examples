### clue-component 1.2

### A component tester similar to an oscilloscope/octopus component tester

### Draws x/y graph of the voltage across a pair of resistors
### and a component (device under test) to graphically show the
### type of component from an AC voltage, a +/- 3.3V sine wave

### Left button averages more values for better accuracy, attempts to
### identify the component with a set of rules and shows the nearest
### E12 value for resistors

### Tested with an Adafruit CLUE and CircuitPython and 6.2.0

### copy this file to CLUE board as code.py

### MIT License

### Copyright (c) 2021 Kevin J. Walters

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

### See https://www.instructables.com/member/kevinjwalters/ for the diagram
### showing the external circuit and connectivity

### The component tester works reasonably accurately works in the following
### ranges and a little bit beyond with less predictable results
### Resistors: 82ohm to 82k
### Capacitors: 22nF to 22uF
### Inductors: only very high values (> 220mH?) and will significantly over-read
### Diodes: most values, struggles with some blue/white LEDs

### This could be ported to any other device which has a screen
### and memory similar to the nRF52840

### The STM32F401RET6-based KittenBot Meowbit is one potential candidate
### when ulab gets added to that - has less memory but screen is lower
### resolution and could reduce analyse_cycles to claw back memory

### PyBadge/PyGamer would be interested as its SAMD51 is faster and
### has two DACs negating need to use PWM

### Potential Improvements

### Using the audio system to play back the sample pairs as a stereo
### looping sample could improve the jitter and increase performance
### of voltage sampling loop in setAndMeasureVoltage

### Add extra frequencies, waveforms and pulses to help determine
### accurate values

### Identification code could be moved into an object and/or library

### Improve documentation/comments in the code, more precision on
### impedance, reactance and resistance

import time
import math
import os
import gc

import board
import analogio
import pulseio
import displayio
import terminalio
import digitalio
import ulab
import ulab.numerical
import ulab.filter
import ulab.linalg

from adafruit_display_text.label import Label


debug = 1

### Measured values for 2k2 resistors in the circuit
r_neg = 2200   ### Set these to your resistor values
r_pos = 2220   ### Set these to your resistor values

### The number of cycles used to identify component quantitatively
analyse_cycles = 25

REF_V = 3.3
REF_V_RMS = REF_V / math.sqrt(2)

### PWM duty cycle values
ZERO_DCS = 0
MAX_DCS = 65535
HALF_MAX_DCS = (MAX_DCS + 1) // 2


def vToPairV(volts):
    if volts >= REF_V:
        return (ZERO_DCS, MAX_DCS)
    elif volts <= -REF_V:
        return (MAX_DCS, ZERO_DCS)
    else:
        half_offset_dc = round((volts / REF_V) * HALF_MAX_DCS)
        return (min(HALF_MAX_DCS - half_offset_dc, MAX_DCS),
                min(HALF_MAX_DCS + half_offset_dc, MAX_DCS))


sine_cycles = 2
sine_len = 120
### Allocate big arrays early on and tidy up memory first
gc.collect()
dc_pairs_sin = [vToPairV(REF_V * math.sin(step * 2 * math.pi / sine_len))
                for step in range(round(sine_len * sine_cycles))]
discard = round(sine_len * 0.5)
dc_pairs = dc_pairs_sin

sine_len_oc = 60
dc_pairs_sin_oc = [vToPairV(REF_V * math.sin(step * 2 * math.pi / sine_len_oc))
                   for step in range(round(sine_len_oc))]
dc_pairs_oc = dc_pairs_sin_oc


### Voltage sample store for the live view
vsample_data = [0] * (2 * len(dc_pairs))

### More compact ulab ndarray for larger data for analysis
### This could be made much smaller by not including the set voltages
analyse_store = ulab.zeros((len(dc_pairs_oc) * analyse_cycles, 4),
                           dtype=ulab.float)

def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


### Left (a) and right (b) buttons
clue_less = os.uname().machine.upper().find("MEOWBIT") >= 0

if clue_less:
    pin_a = board.BTNA
    pin_b = board.BTNB
    internal_res = 140   ### ?
else:
    pin_a = board.BUTTON_A
    pin_b = board.BUTTON_B
    internal_res = 140   ### guestimate

pin_but_a = digitalio.DigitalInOut(pin_a)
pin_but_a.switch_to_input(pull=digitalio.Pull.UP)
pin_but_b = digitalio.DigitalInOut(pin_b)
pin_but_b.switch_to_input(pull=digitalio.Pull.UP)
left_button = lambda: not pin_but_a.value
right_button = lambda: not pin_but_b.value

### P3/P12 for pwm voltage + P4/P10 for analogue read
### work on both the Adafruit Clue and the KittenBot Meowbit
### 65 different outputs at 250kHz PWM on nRF52840 - 0V to 3.3V
pwm_neg = pulseio.PWMOut(board.P3, frequency=250 * 1000)
pwm_pos = pulseio.PWMOut(board.P12, frequency=250 * 1000)

analogue_neg = analogio.AnalogIn(board.P4)
analogue_pos = analogio.AnalogIn(board.P10)

GRAPH_SHOW_TIME_NS = 6 * 1000 * 1000 * 1000
COMP_DELAY_TIME_NS = 2 * 1000 * 1000 * 1000

### Screen refresh is performed explicitly in the code
display = board.DISPLAY
display.auto_refresh = False

FONT_WIDTH, FONT_HEIGHT = terminalio.FONT.get_bounding_box()[:2]
DISPLAY_WIDTH, DISPLAY_HEIGHT = display.width, display.height
G_ORIGIN_X = DISPLAY_WIDTH // 2
G_ORIGIN_Y = DISPLAY_HEIGHT // 2

### The size of the resistor (including stubby leads) displayed
COMP_WIDTH = 129
COMP_HEIGHT = 32

r_neg += internal_res
r_pos += internal_res

### Theoretical max is around 750mA for a pair of 2k2
GRAPH_GRID_V = 3
GRAPH_GRIDSTEP_V = 1
GRAPH_GRID_UA = 600
GRAPH_GRIDSTEP_UA = 200

### Create a palette for drawing components
CC_BLACK  = 0x000000
CC_BROWN  = 0x702000
CC_RED    = 0xc00000
CC_ORANGE = 0xe08010
CC_YELLOW = 0xe0d000
CC_GREEN  = 0x00b000
CC_BLUE   = 0x0000a0
CC_VIOLET = 0x8020a0
CC_GREY   = 0x505050
CC_WHITE  = 0xd0d0d0

CC_SILVER_IDX = 10
CC_SILVER = 0x909090
CC_GOLD_IDX = 11
CC_GOLD   = 0xa08000

COMP_COL = (CC_BLACK,
            CC_BROWN,
            CC_RED,
            CC_ORANGE,
            CC_YELLOW,
            CC_GREEN,
            CC_BLUE,
            CC_VIOLET,
            CC_GREY,
            CC_WHITE)

RES_COLOUR_IDX = 12
RES_COLOUR = 0xb0c070   ### beige
WIRE_COLOUR_IDX = 13
WIRE_COLOUR = 0x505050

TRANSPARENT_IDX = 15

c_palette = displayio.Palette(16)
for c_idx, numbers in enumerate(COMP_COL):
    c_palette[c_idx] = COMP_COL[c_idx]

c_palette[CC_SILVER_IDX] = CC_SILVER
c_palette[CC_GOLD_IDX] = CC_GOLD
c_palette[RES_COLOUR_IDX] = RES_COLOUR
c_palette[WIRE_COLOUR_IDX] = WIRE_COLOUR
c_palette.make_transparent(TRANSPARENT_IDX)

### Create a bitmap with four colors for graphing
### More colours in bitmap increases the memory use on 2**n boundaries
BG_IDX = 0
BEAM_IDX = 1
VOLT_IDX = 2
GRID_IDX = 3
palette = displayio.Palette(4)
palette[BG_IDX] = 0x000000  ### background
palette[BEAM_IDX] = 0x80ff80  ### oscilloscope points for x/y
palette[VOLT_IDX] = 0x6060ff  ### for second channel in two channel mode
palette[GRID_IDX] = 0x404040  ### grid lines
bitmap = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, len(palette))

tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
group = displayio.Group()

TITLE_FONT_SCALE = 2
MAX_TITLE_LEN = int(DISPLAY_WIDTH / FONT_WIDTH / TITLE_FONT_SCALE)
title = Label(terminalio.FONT,
              text="",
              max_glyphs=MAX_TITLE_LEN,
              scale=TITLE_FONT_SCALE,
              color=0xc0c0c0)
title.y = round(FONT_HEIGHT / 2 * TITLE_FONT_SCALE * 1.5)

EXTRADETAIL_FONT_SCALE = 1
MAX_EXTRADETAIL_LEN = int(DISPLAY_WIDTH / FONT_WIDTH / EXTRADETAIL_FONT_SCALE)
extra_detail = Label(terminalio.FONT,
                     text="",
                     max_glyphs=MAX_EXTRADETAIL_LEN,
                     scale=EXTRADETAIL_FONT_SCALE,
                     color=0xc0c0c0)
extra_detail.x = FONT_WIDTH
extra_detail.y = DISPLAY_HEIGHT - round(FONT_HEIGHT / 2 * EXTRADETAIL_FONT_SCALE * 1.5)

component_grp = displayio.Group()

group.append(tile_grid)
group.append(title)
group.append(extra_detail)
group.append(component_grp)
display.show(group)


def setTitle(newtext):
    trimmed_text = newtext[:MAX_TITLE_LEN]
    title.text = trimmed_text
    title.x = (DISPLAY_WIDTH - TITLE_FONT_SCALE * FONT_WIDTH * len(trimmed_text)) // 2


def setExtradetail(newtext):
    trimmed_text = newtext[:MAX_EXTRADETAIL_LEN]
    extra_detail.text = trimmed_text


def makeResistor(value, width=110, height=32):
    res_tg = None
    bands = colourBands(quantizeValue(value))
    if bands:
        res = displayio.Bitmap(width, height, len(c_palette))
        res.fill(TRANSPARENT_IDX)

        ### Wires
        lead_length = width // 5
        lead_thickness = height // 8
        for x in range(0, lead_length):
            for y in range((height - lead_thickness) // 2,
                           (height + lead_thickness) // 2):
                res[x, y] = WIRE_COLOUR_IDX
                res[width - x - 1, y] = WIRE_COLOUR_IDX
        ### Resistor body
        body_height = height
        body_width = width - lead_length * 2
        for x in range(lead_length, lead_length + body_width):
            for y in range((height - body_height) // 2,
                           (height + body_height) // 2):
                res[x, y] = RES_COLOUR_IDX

        ## band_heights = (body_height,) * len(bands)
        ## body_width = width - 2 * lead_length
        ### Five bands with six surrouding spaces
        band_count = max(5, len(bands))
        band_space_exact = (body_width - 2) / (band_count * 2 + 1)
        band_pos = [range(lead_length + round(band_space_exact * (2 * pos + 1)),
                          lead_length + 2 + round(band_space_exact * (2 * pos + 2))) for pos in range(band_count)]

        for b_idx, band_idx in enumerate(bands):
            if b_idx >= 3 and b_idx == len(bands) - 1:
                xrange = band_pos[-1]
            else:
                xrange = band_pos[b_idx]

            for x in xrange:
                for y in range((height - body_height) // 2,
                               (height + body_height) // 2):
                    res[x, y] = band_idx
        res_tg = displayio.TileGrid(res, pixel_shader=c_palette)

    return res_tg


def pwmVoltageOff():
    pwm_neg.duty_cycle = 0
    pwm_pos.duty_cycle = 0


def setVoltage(volts):
    v1, v2 = vToPairV(volts)
    pwm_neg.duty_cycle = v1
    pwm_pos.duty_cycle = v2


def setAndMeasureVoltage(volt_pairs, store,
                         store_idx=0,
                         start=None, end=None,
                         runs=1):
    s_idx = store_idx
    v_set_neg = v_set_pos = 0
    v_meas_neg = v_meas_pos = 0

    ### Different output styles for list vs ndarray
    ### Use of outer if is for performance
    if isinstance(store, list):
        for _ in range(runs):
            for idx in range(0 if start is None else start,
                             len(volt_pairs) if end is None else end):
                v_set_neg, v_set_pos = volt_pairs[idx]
                pwm_neg.duty_cycle = v_set_neg
                pwm_pos.duty_cycle = v_set_pos
                v_meas_neg = analogue_neg.value
                v_meas_pos = analogue_pos.value
                store[s_idx] = v_meas_neg
                store[s_idx + 1] = v_meas_pos
                s_idx += 2
    else:
        for _ in range(runs):
            for idx in range(0 if start is None else start,
                             len(volt_pairs) if end is None else end):
                v_set_neg, v_set_pos = volt_pairs[idx]
                pwm_neg.duty_cycle = v_set_neg
                pwm_pos.duty_cycle = v_set_pos
                v_meas_neg = analogue_neg.value
                v_meas_pos = analogue_pos.value
                store_p = store[s_idx]
                store_p[2] = v_meas_neg
                store_p[3] = v_meas_pos
                s_idx += 1

    return s_idx


def circularFilter(cdata, weights):

    extras = len(weights) - 1
    padded_data = ulab.concatenate((cdata[-extras:],
                                    cdata,
                                    cdata[:extras]))
    filt_pad_data = ulab.filter.convolve(padded_data, weights)
    ### There are pros/cons to copy() here but it's needed because of
    ### https://github.com/adafruit/circuitpython/issues/4753
    return filt_pad_data[extras:-extras].copy()


def capacitorCorrection(m_cap):
    """Apply a correction to the measured capacitance value
       to get a value closer to the real value.

       One reason this may differ is measurement varies based on frequency.
       The measurements are performed at 30Hz but capacitance values
       are normally quoted for 1kHz.

       The coefficients are based on mutiple linear regression in R
       using rms-based measurements of capacitors vs readings from multimeter
       plus a fudge for small values!
    """

    ### These are based on 30Hz sine wave with 2x2k2 + 2x10nF
    ### + internal_res = 200 and no esr correction
    ###return -7.599263e-08 + 9.232542e-01 * m_cap + 1.690527e+04 * m_cap * m_cap

    ### 31Hz sine 2x2k2 + 2x10nF with internal_res = 140 no esr correction
    poly2_cor = -6.168148e-08 + 8.508691e-01 * m_cap + 2.556320e+04 * m_cap * m_cap
    return poly2_cor if poly2_cor > 30e-9 else m_cap * 0.2


def circularDifferentiate(x_d, y_d):

    delta_x = ulab.numerical.roll(x_d, -1) - x_d
    delta_y = ulab.numerical.roll(y_d, -1) - y_d

    delta_y /= delta_x  ### in-place division
    return delta_y


def phaseDifference_peaks(v1, v2):
    """Compare peaks of v1 and v2 and return phase difference
       between -pi and pi or None if data is not consistent."""

    if len(v1) != len(v2):
        raise ValueError("Only works with same size vectors")

    v1_trough_idx = ulab.numerical.argmin(v1)
    v1_peak_idx = ulab.numerical.argmax(v1)
    v2_trough_idx = ulab.numerical.argmin(v2)
    v2_peak_idx = ulab.numerical.argmax(v2)

    peak_diff = (v2_peak_idx - v1_peak_idx) / len(v1)
    trough_diff = (v2_trough_idx - v1_trough_idx) / len(v1)
    if peak_diff < 0.0:
        peak_diff += 1.0
    if trough_diff < 0.0:
        trough_diff += 1.0

    ### check for distance between the two values
    ### also check for "wrap around" distance as 0.99 is very close to 0.01
    if (abs(peak_diff - trough_diff) < 0.2 or
            (1.0 - max(peak_diff, trough_diff))
            + min(peak_diff, trough_diff) < 0.2):
        phase_two = peak_diff + trough_diff  ### now in range 0 to 2.0
        ### absenst /2 for avg and 2 in 2*pi cancel out
        return (phase_two - 2.0 if phase_two > 1.0 else phase_two) * math.pi

    ### Reaching here means a sanity check on waveform has failed
    return None


def averageVI(store, cycles_n, scale=1):
    """Calculate the voltages and currents for a cycle by averaging all cycles.
       Calculate the resistance from those values."""

    avg_len = store.shape[0] // cycles_n
    avg_v = ulab.zeros(avg_len)
    avg_i = ulab.zeros(avg_len)
    for s_idx, (v_set_neg, v_set_pos, v_meas_neg, v_meas_pos) in enumerate(store):
        i5 = (v_meas_neg - v_set_neg) / r_neg
        i6 = (v_set_pos - v_meas_pos) / r_pos
        c_v = v_meas_pos - v_meas_neg
        c_i = (i5 + i6) / 2
        v_idx = s_idx % avg_len
        avg_v[v_idx] += c_v
        avg_i[v_idx] += c_i

    avg_r = avg_v / avg_i
    avg_v *= scale / cycles_n
    avg_i *= scale / cycles_n
    return (avg_r, avg_v, avg_i)


def removeLowVoltage(avg_r, avg_v, low_v=(10e-3,)):

    ### Pick out anything below measured +/- 50mV (or failing that lower values)
    ### used to discard iffy resistance values
    for lowest_value in low_v:
        avg_r_nolowv = avg_r[abs(avg_v) > lowest_value]
        if len(avg_r_nolowv) > 0:
            break

    ### Go with the low level noise if there's nothing else
    if len(avg_r_nolowv) == 0:
        avg_r_nolowv = avg_r
    return avg_r_nolowv


def isResistor(median_avg_r, median_r_nolowv, avg_r_nolowv_tl_relsd):
    identified = None

    ### Allow more deviation away from mean for higher values
    if (avg_r_nolowv_tl_relsd < 0.5 or
            median_avg_r > 12500 and avg_r_nolowv_tl_relsd < median_avg_r / 25000):
        round_r = round(median_r_nolowv)
        if round_r < 1000.0:
            identified = "Resistor {:.0f}".format(round_r)
        else:
            identified = "Resistor {:.3g}k".format(median_r_nolowv / 1000.0)

    return (identified, median_r_nolowv)


def isAnyDiode(lpf_avg_v_vorder, lpf_avg_i_vorder, *,
               target_current=120e-6,
               zener_rev_current=-200e-6,
               neglible_current=40e-6):
    identified = None
    vforward = None
    vforward_idx = None
    vreverse = None
    vreverse_idx = None

    diode_rc = False      ### found reverse conducting
    diode_reg_nc_farzero = None   ### found non-conducting region
    diode_reg_nc_nearzero = False  ### found non-conducting region
    diode_reg_c = False   ### found conducting region

    for v_idx, m_v in enumerate(lpf_avg_v_vorder):
        d_print(4, "isDiode V vs I", m_v, lpf_avg_i_vorder[v_idx])
        if m_v < -0.5:
            if lpf_avg_i_vorder[v_idx] < zener_rev_current:
                diode_rc = True
                vreverse = m_v
                vreverse_idx = v_idx
                diode_reg_nc_farzero = False
            elif diode_reg_nc_farzero is None:
                diode_reg_nc_farzero = True
        elif m_v < -0.1:
            if abs(lpf_avg_i_vorder[v_idx]) < neglible_current:
                diode_reg_nc_nearzero = True
            else:
                break
        else:
            ### Germanium diodes seem to have an occasional rocky upward slope at low voltages
            if (lpf_avg_i_vorder[v_idx] > target_current
                    or v_idx >= 1 and lpf_avg_i_vorder[v_idx - 1] > target_current
                    or v_idx >= 2 and lpf_avg_i_vorder[v_idx - 2] > target_current):
                diode_reg_c = True
                if vforward is None:
                    vforward = m_v
                    vforward_idx = v_idx
            elif diode_reg_c:
                ### In conducting region but current has fallen back
                diode_reg_c = False
                break

    if diode_reg_c:
        if diode_rc:
            diode_type = "Zener diode"
        elif diode_reg_nc_farzero and diode_reg_nc_nearzero:
            if vforward > 1.0:
                diode_type = "LED"
            elif vforward > 0.4:
                diode_type = "Si diode"
            elif vforward > 0.16:
                diode_type = "Schottky"
            else:
                diode_type = "Ge diode"
        identified = diode_type

    return (identified, vforward, vforward_idx, vreverse, vreverse_idx)


def isCapacitor(lpf_avg_v, lpf_avg_i,
                avg_f, phase_diff, phase_diff_deg,
                v_sd, i_sd):
    identified = None
    raw_cap = None
    cap = None
    res = None

    ### The standard deviation minima in if condition should prevent
    ### division by zero
    if (-90 - 20 < phase_diff_deg < -90 + 20
            and v_sd > 15e-3 and i_sd > 12e-6):
        rmsvxlen = math.sqrt(ulab.linalg.dot(lpf_avg_v, lpf_avg_v))
        rmsixlen = math.sqrt(ulab.linalg.dot(lpf_avg_i, lpf_avg_i))
        d_print(3, "isCapacitor RMSxLEN V I", rmsvxlen, rmsixlen)
        z_rl_mag = rmsvxlen / rmsixlen  ### array lengths cancel out

        ### ESR is too small for low resolution/accuracy phase_diff to
        ### be useful in calculations, better to assume 90 degree shift
        raw_cap = 1 / (2 * math.pi * avg_f * z_rl_mag)
        cap = capacitorCorrection(raw_cap)
        if cap > 0.8e-6:
            identified = "Capacitor {:.3g}uF".format(cap * 1e6)
        else:
            identified = "Capacitor {:.0f}nF".format(cap * 1e9)

    return (identified, raw_cap, cap, res)


def isInductor(lpf_avg_v, lpf_avg_i,
               avg_f, phase_diff, phase_diff_deg,
               v_sd, i_sd,
               median_avg_r):
    identified = None
    ind = None
    res = None

    ### Phase is 60 degrees on my 230ohm relay coil
    ### 73 on 20VA on half primary of transformer
    ### The standard deviation minima in if condition should prevent
    ### division by zero
    if (90 - 75 < phase_diff_deg < 90 + 20
            and median_avg_r < 6000
            and v_sd > (15e-3 + 10e-3) and i_sd > 12e-6):
        rmsvxlen = math.sqrt(ulab.linalg.dot(lpf_avg_v, lpf_avg_v))
        rmsixlen = math.sqrt(ulab.linalg.dot(lpf_avg_i, lpf_avg_i))
        d_print(3, "isInductor RMSxLEN V I", rmsvxlen, rmsixlen)
        z_rl_mag = rmsvxlen / rmsixlen  ### array lengths cancel out
        ### Should this be capped at pi/2 (90 degrees)??
        z_rl_ang = phase_diff
        z_r = math.cos(z_rl_ang) * z_rl_mag
        z_l = math.sin(z_rl_ang) * z_rl_mag
        d_print(3, "isInductor Z", [math.degrees(z) for z in (z_rl_mag, z_r, z_l)])

        res = z_r
        ind = z_l / ( 2 * math.pi * avg_f)
        identified = "Inductor {:.3g}H".format(ind)

    return (identified, ind, res)


def extrapolateVFVR(voltage, v_idx,
                    v_vorder, i_vorder,
                    *,
                    forward=True,
                    rlim=(0, float("inf")),
                    steepen=1,
                    target_i=20e-3,
                    min_points=4):
    """Extrapolate I/V points to find a forward or reverse voltage at
       a higher current based on the final gradient and an increased
       gradient from a steepen factor that reduces the resistance.

       This could be improved by only using the final partition
       of the upware curve.
       """

    new_v = None
    if voltage is None or v_idx is None:
        return new_v

    ### Pick the two groups of points to use for gradient calculation
    range1 = range2 = ()
    if forward and v_idx < len(i_vorder) - min_points:
        mean_width = 3 if v_idx < len(i_vorder) - (min_points + 1) else 2
        range1 = slice(v_idx, v_idx + mean_width)
        range2 = slice(-mean_width, None)
    elif not forward and v_idx >= min_points:
        mean_width = 3 if v_idx >= (min_points + 1) else 2
        range1 = slice(v_idx + 1 - mean_width, v_idx + 1)
        range2 = slice(0, mean_width)

    if range1:
        ### Take the average of each group of points and work
        ### out difference for the gradient
        diode_dv = (ulab.numerical.mean(v_vorder[range2]) -
                    ulab.numerical.mean(v_vorder[range1]))
        diode_di = (ulab.numerical.mean(i_vorder[range2]) -
                    ulab.numerical.mean(i_vorder[range1]))

        try:
            diode_cslope_r = diode_dv / diode_di
            ### Check the start of the slope is within reasonable range
            if rlim[0] < diode_cslope_r < rlim[1]:
                ### Increase the gradient
                diode_cslope_steeper_r = diode_cslope_r / steepen
                start_i = i_vorder[v_idx]
                extra_v = (target_i - start_i) * diode_cslope_steeper_r
                new_v = voltage + extra_v
        except ZeroDivisionError:
            pass

    return new_v


def sortByVoltage(arrays, voltages):
    sort_idx_v = ulab.numerical.argsort(voltages, axis=0)
    o_arrays = [ulab.zeros(len(a)) for a in arrays]
    ### ulab doesn't seem to implement indexing by an array, hence
    ### the for loop
    for a, o_a in zip(arrays, o_arrays):
        for idx in range(len(sort_idx_v)):
            o_a[idx] = a[sort_idx_v[idx]]
    return o_arrays


def quantizeValue(value, *, per_decade=12):
    """Quantize to nearest mathematical E12 value or any other series."""

    if value <= 0.0:
        return value
    q_step = math.log(value, 10) * per_decade
    q_value = 10 ** (round(q_step) / per_decade)
    return q_value


def remapE24(digit1, digit2):
    """The E24 series which includes E12 and E6 as subsets has a few values
       which do not map exactly to the mathematical values."""
    e24_digit2 = digit2

    if (digit1 == 2 and digit2 == 6
            or digit1 == 3 or digit1 == 4):
        e24_digit2 += 1
    elif digit1 == 8:
        e24_digit2 -= 1
    return e24_digit2


def colourBands(value, digits=2, tolerance=None, thermal=None, *, e24=True):

    if value <= 0.0:
        return None

    try:
        ### Use the scientific formating to pull out the
        ### 2 significant figures and power of ten
        mantissa_s, exponent_s = "{:.1e}".format(value).split("e")
        dig1_s, dig2_s = mantissa_s.split(".")
        dig1 = ord(dig1_s) - ord("0")
        dig2 = ord(dig2_s) - ord("0")
        if e24 and digits == 2:
            dig2 = remapE24(dig1, dig2)
        zeros = int(exponent_s) - 1
        if zeros == -1:
            zeros = CC_GOLD_IDX
        elif zeros == -2:
            zeros = CC_SILVER_IDX

        if not -2 <= zeros <= 9 or not 0 <= dig1 <= 9 or not 0 <= dig2 <= 9:
            return None
    except (ValueError, IndexError):
        return None
    return (dig1, dig2, zeros)


def analyseData(store, cycles=1, frequency=1):
    identified = None
    ddata = {}

    ### Convert values in store from two observed voltages
    ### to applied voltage across component and current
    avg_r, avg_v, avg_i = averageVI(store, cycles, scale=REF_V / MAX_DCS)
    median_avg_r = ulab.numerical.median(avg_r)
    avg_v_sd = ulab.numerical.std(avg_v)
    avg_i_sd = ulab.numerical.std(avg_i)
    avg_r_relsd = abs(ulab.numerical.std(avg_r) / ulab.numerical.mean(avg_r))
    avg_r_nolowv = removeLowVoltage(avg_r, avg_v, low_v=(50e-3, 25e-3, 8e-3))

    d_print(3, "Resistance med={:f} relsd={:f}".format(median_avg_r, avg_r_relsd))
    d_print(3, "Voltage relsd={:f} low_n={:d}/{:d}".format(avg_v_sd,
                                                           len(avg_r_nolowv),
                                                           len(avg_v)))
    d_print(3, "Current relsd={:f}".format(avg_i_sd))

    mean_r_nolowv = 0.0
    median_r_nolowv = 0.0
    if len(avg_r_nolowv) > 0:
        ### median() crashes on empty ndarray
        mean_r_nolowv = ulab.numerical.mean(avg_r_nolowv)
        median_r_nolowv = ulab.numerical.median(avg_r_nolowv)

    d_print(3, "Filtered (no low v) R mean={:f} med={:f}".format(mean_r_nolowv,
                                                                 median_r_nolowv))

    ### Smooth the points with a low pass filter across them
    ### in the original order and wraparound
    fir_taps = ulab.array([0.14, 0.18, 0.36, 0.18, 0.14])
    lpf_avg_v = circularFilter(avg_v, fir_taps)
    lpf_avg_i = circularFilter(avg_i, fir_taps)

    lpf_local_r = circularDifferentiate(lpf_avg_i, lpf_avg_v)
    lpf_local_r_sorted = ulab.numerical.sort(lpf_local_r)

    perc4 = round(len(lpf_local_r_sorted) * 3 / 100)
    lpf_local_r_s_tailless = (lpf_local_r_sorted if perc4 == 0
                              else ulab.numerical.sort(lpf_local_r[perc4:-perc4]))

    lpf_local_r_s_tailless_relsd = abs(ulab.numerical.std(lpf_local_r_s_tailless)
                                       / ulab.numerical.mean(lpf_local_r_s_tailless))

    perc4 = round(len(avg_r_nolowv) * 3 / 100)
    avg_r_nolowv_tailless = (avg_r_nolowv if perc4 == 0
                             else ulab.numerical.sort(avg_r_nolowv[perc4:-perc4]))
    avg_r_nolowv_tl_relsd = abs(ulab.numerical.std(avg_r_nolowv_tailless)
                                / ulab.numerical.mean(avg_r_nolowv_tailless))
    d_print(3, "Filtered (no low v, no tails) "
            "R relsd={:f}, ".format(avg_r_nolowv_tl_relsd)
            + "local R relsd={:f}".format(lpf_local_r_s_tailless_relsd))

    res = None
    if not identified:
        identified, res  = isResistor(median_avg_r, median_r_nolowv, avg_r_nolowv_tl_relsd)

    lpf_local_r_vorder, lpf_avg_i_vorder, lpf_avg_v_vorder = sortByVoltage((lpf_local_r,
                                                                            lpf_avg_i,
                                                                            lpf_avg_v),
                                                                           lpf_avg_v)

    if debug >= 4:
        d_print(4, "DV/DI", list(lpf_local_r))
        d_print(4, "DV/DI ordered", list(lpf_local_r_vorder))
        d_print(4, "I ORDERED", list(lpf_avg_i_vorder))

    phase_peaks = phaseDifference_peaks(lpf_avg_v, lpf_avg_i)
    phase_peaks_deg = math.degrees(phase_peaks) if phase_peaks is not None else phase_peaks
    d_print(3, "PHASE-P", phase_peaks_deg)

    ### Look for uniform low voltage
    count_lpf_avg_lowv = ulab.numerical.sum(abs(lpf_avg_v) > 20e-3)
    meanabs_lpf_avg_v = ulab.numerical.mean(abs(lpf_avg_v))

    d_print(3, "C+M V", count_lpf_avg_lowv, meanabs_lpf_avg_v)

    ### Look for uniform low current
    count_lpf_avg_lowi = ulab.numerical.sum(abs(lpf_avg_i) > 20e-6)
    meanabs_lpf_avg_i = ulab.numerical.mean(abs(lpf_avg_i))

    if count_lpf_avg_lowv == 0 and meanabs_lpf_avg_v < 10e-3:
        identified = "Conductor"
    elif count_lpf_avg_lowi == 0 and meanabs_lpf_avg_i < 10e-6:
        identified = "Open circuit"

    ### Diode match including 3.3V and below zeners
    vforward = None
    vreverse = None
    if not identified:
        (identified,
         vforward, vforward_idx,
         vreverse, vreverse_idx) = isAnyDiode(lpf_avg_v_vorder, lpf_avg_i_vorder)
        if identified:
            vforward_norm = extrapolateVFVR(vforward, vforward_idx,
                                            lpf_avg_v_vorder, lpf_avg_i_vorder,
                                            rlim=(80, 1500), steepen=15, target_i=10e-3)

            vreverse_norm = extrapolateVFVR(vreverse, vreverse_idx,
                                            lpf_avg_v_vorder, lpf_avg_i_vorder,
                                            forward=False,
                                            rlim=(80, 4000), steepen=30, target_i=-30e-3)

            ### Note unary minus on the reverse voltages
            twodigv = " {:.2f}V"
            ### pylint: disable=invalid-unary-operand-type
            if vreverse_norm is not None:
                identified += twodigv.format(-vreverse_norm)
            elif vreverse is not None:
                identified += twodigv.format(-vreverse)
            elif vforward_norm is not None:
                identified += twodigv.format(vforward_norm)
            elif vforward is not None:
                identified += twodigv.format(vforward)
        else:
            ### Not a diode so clear out any values here to prevent display
            vforward = vreverse = None

    esr = None
    raw_cap = None
    if not identified and phase_peaks is not None:
        ### ESR value is discarded here as it's not likely to be
        ### accurate
        identified, raw_cap, cap, _ = isCapacitor(lpf_avg_v, lpf_avg_i,
                                                  frequency,
                                                  phase_peaks, phase_peaks_deg,
                                                  avg_v_sd, avg_i_sd)

    ### If not identified then try for an inductor
    ind = None
    if not identified and phase_peaks is not None:
        identified, ind, esr = isInductor(lpf_avg_v, lpf_avg_i,
                                          frequency,
                                          phase_peaks, phase_peaks_deg,
                                          avg_v_sd, avg_i_sd,
                                          median_avg_r)

    ### Clean up any values
    if not ind and not raw_cap:
        phase_peaks_deg = None  ### likely to unreliable

    d_print(1, "Identification:", identified)
    show_default_graph = True
    finish_update = False
    comp_dio = None
    comp_shown = False
    add_comp = False
    now_ns = time.monotonic_ns()
    end_wait_ns = now_ns + GRAPH_SHOW_TIME_NS
    show_comp_ns = now_ns + COMP_DELAY_TIME_NS
    while time.monotonic_ns() < end_wait_ns:
        if show_default_graph or left_button():
            show_default_graph = False
            bitmap.fill(BG_IDX)
            drawGrid(bitmap)
            for a_v, a_i in zip(lpf_avg_v, lpf_avg_i):
                x = G_ORIGIN_X + round(a_v * vx_si_scale)
                y = G_ORIGIN_Y - round(a_i * i_si_scale)
                if 0 <= y < DISPLAY_HEIGHT:
                    bitmap[x, y] = BEAM_IDX

            add_comp = True
            finish_update = True

        if right_button():
            bitmap.fill(BG_IDX)
            drawAxis(bitmap)

            x_idx_scale = (DISPLAY_WIDTH - 2) / (len(lpf_avg_v) - 1)
            for vi_idx, (a_v, a_i) in enumerate(zip(lpf_avg_v, lpf_avg_i)):
                x = 1 + round(vi_idx * x_idx_scale)
                y_v = G_ORIGIN_X - round(a_v * vy_si_scale)
                y_i = G_ORIGIN_Y - round(a_i * i_si_scale)
                ### Use a unique colour for the two variables
                if 0 <= y_v < DISPLAY_HEIGHT:
                    bitmap[x, y_v] = BEAM_IDX
                if 0 <= y_i < DISPLAY_HEIGHT:
                    bitmap[x, y_i] = VOLT_IDX

            ### Lose the component graphic for this graph
            add_comp = False
            if comp_shown and comp_dio:
                component_grp.pop()
                comp_shown = False

            finish_update = True

        if finish_update:
            if identified:
                setTitle(identified)
            extras = (vforward,
                      vreverse,
                      esr,
                      raw_cap,
                      phase_peaks_deg,
                      esr)
            if any(e is not None for e in extras):
                ed = " ".join(e for e in
                              ["Vf={:.2f}V".format(vforward)
                               if vforward is not None else "",
                               "Vr={:.2f}V".format(vreverse)
                               if vreverse is not None else "",
                               "ESR={:.0f}".format(esr)
                               if esr is not None else "",
                               "C={:.3g}uF".format(raw_cap * 1e6)
                               if raw_cap is not None else "",
                               "PhaseD={:.0f}".format(phase_peaks_deg)
                               if phase_peaks_deg is not None else "",
                               "f={:.0f}".format(frequency)
                              ] if e)
                setExtradetail(ed)

            display.refresh()
            finish_update = False  ### until next time
            ### Start timer again
            end_wait_ns = time.monotonic_ns() + GRAPH_SHOW_TIME_NS

        if add_comp and not comp_shown and time.monotonic_ns() > show_comp_ns:
            if identified and identified.lower().startswith("res") and res is not None:
                comp_dio = makeResistor(res, COMP_WIDTH, COMP_HEIGHT)
                if comp_dio:
                    component_grp.append(comp_dio)
                    component_grp[0].x = DISPLAY_WIDTH - COMP_WIDTH - DISPLAY_WIDTH // 60
                    component_grp[0].y = DISPLAY_HEIGHT - COMP_HEIGHT - FONT_HEIGHT
                    display.refresh()
            comp_shown = True

    ### Remove items from display
    setTitle("")
    setExtradetail("")
    if comp_dio and len(component_grp) == 1:
        component_grp.pop()

    return ddata


def drawAxis(bmp):

    for xpos in range(DISPLAY_WIDTH):
        bmp[xpos, G_ORIGIN_Y] = GRID_IDX
    for ypos in range(DISPLAY_HEIGHT):
        bmp[G_ORIGIN_X, ypos] = GRID_IDX


def drawGrid(bmp):

    drawAxis(bmp)

    for volts in range(-GRAPH_GRID_V, GRAPH_GRID_V + 1, GRAPH_GRIDSTEP_V):
        if volts:
            for pos in range(0, DISPLAY_HEIGHT, 4):
                bmp[G_ORIGIN_X + round(volts * vx_si_scale), pos] = GRID_IDX

    for current_ua in range(-GRAPH_GRID_UA, GRAPH_GRID_UA + 1, GRAPH_GRIDSTEP_UA):
        if current_ua:
            for pos in range(0, DISPLAY_WIDTH, 4):
                bmp[pos, G_ORIGIN_Y + round(current_ua * 1e-6 * i_si_scale)] = GRID_IDX


def drawRTGraph(bmp, volt_set, volt_meas,
                scale_xv=0, scale_yi=0,
                *, start=0):

    vm_idx = start * 2
    for vs_idx in range(start, len(volt_set)):
        v_set_neg, v_set_pos = volt_set[vs_idx]
        ## test_v = v_set_pos - v_set_neg
        v_meas_neg = volt_meas[vm_idx]
        v_meas_pos = volt_meas[vm_idx + 1]
        vm_idx += 2

        i5 = (v_meas_neg - v_set_neg) / r_neg
        i6 = (v_set_pos - v_meas_pos) / r_pos
        c_v = v_meas_pos - v_meas_neg
        c_i = (i5 + i6) / 2
        ## c_r = c_v / c_i if c_i != 0.0 else math.copysign(float("inf"), c_v)

        x = G_ORIGIN_X + round(c_v * scale_xv)
        y = G_ORIGIN_Y - round(c_i * scale_yi)
        if 0 <= x < DISPLAY_WIDTH and 0 <= y < DISPLAY_HEIGHT:
            bmp[x, y] = 1


def identifyComponent(cycles=1):

    wavestart_ns = 0
    wavestop_ns = 0
    ### Good time to do a garbage collection to reduce chance of an
    ### interruption during the measurement process
    gc.collect()

    ### First two whole cycles are discarded as a simple way
    ### to deal with charging capacitor/inductor
    _discard1 = setAndMeasureVoltage(dc_pairs_oc, vsample_data)
    _discard2 = setAndMeasureVoltage(dc_pairs_oc, vsample_data)
    wavestart_ns = time.monotonic_ns()
    as_idx = setAndMeasureVoltage(dc_pairs_oc,
                                  analyse_store,
                                  runs=cycles)
    wavestop_ns = time.monotonic_ns()
    setVoltage(0)
    ### About 30-32Hz on an Adafruit CLUE with CircuitPython 6.2.0
    freq = (1e9 * (cycles + 1)) / (wavestop_ns - wavestart_ns)
    ### Fill in the voltages in second pass - this is done
    ### to keep the measurements as fast as possible
    as_idx = 0
    for _ in range(cycles):
        for v_s_neg, v_s_pos in dc_pairs_oc:
            analyse_store[as_idx][0] = v_s_neg
            analyse_store[as_idx][1] = v_s_pos
            as_idx += 1
    d_print(3, "Analysis frequency (Hz)", freq)
    return analyseData(analyse_store, cycles=analyse_cycles, frequency=freq)


vx_si_scale = DISPLAY_WIDTH / (REF_V * 2.2)
vy_si_scale = DISPLAY_HEIGHT / (REF_V * 2.2)
i_si_scale = 100 * (r_neg + r_pos) / REF_V

SI_TO_DC = REF_V / MAX_DCS
vx_scale = vx_si_scale * SI_TO_DC
vy_scale = vy_si_scale * SI_TO_DC
i_scale = i_si_scale * SI_TO_DC


while True:
    if left_button():
        data = identifyComponent(analyse_cycles)
        continue

    ### The real-time display of x/y data
    _ = setAndMeasureVoltage(dc_pairs, vsample_data)
    setVoltage(0)

    ### Graph data
    bitmap.fill(BG_IDX)
    drawRTGraph(bitmap, dc_pairs, vsample_data,
                scale_xv=vx_scale, scale_yi=i_scale,
                start=discard)
    display.refresh()

    if debug >= 3:
        gc.collect()
        d_print(3, "GC MEM (end of main loop)", gc.mem_free())
