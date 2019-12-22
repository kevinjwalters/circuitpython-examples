### audio-phasebug v1.0
### This demonstrates a very strange bug where A0 and A1 samples do NOT
### maintain their synchronisation, i.e. as if one sample is longer than
### the other but an even number of samples are supplied to audioio.RawSample
### with channel_count=2
### Starts with A0 and A1 aligned and then takes about 60 seconds for them to return to
### that state, repeats ad infinitum

### copy this file to PyGamer (or other M4 board) as code.py

### MIT License

### Copyright (c) 2019 Kevin J. Walters

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
import math
import array

import board
import audioio

### A0 will be x, A1 will be y
dacs = audioio.AudioOut(board.A0, right_channel=board.A1)

### PyPortal DACs seem to stop around 53000
### There's 2 100 ohm resistors on each output - relevant?
dac_x_max = 32768
dac_y_max = 32768

rawdata = array.array("H",
[23570,
32596,
23629,
32554,
23688,
32512,
23748,
32470,
23807,
32428,
23867,
32386,
23926,
32343,
23948,
32276,
23970,
32208,
23992,
32141,
24014,
32073,
24036,
32005,
24058,
31938,
24080,
31870,
24102,
31803,
24103,
31724,
24104,
31645,
24105,
31566,
24106,
31487,
24107,
31408,
24108,
31330,
24109,
31251,
24110,
31172,
24111,
31093,
24112,
31014,
24113,
30935,
24114,
30857,
24115,
30778,
24116,
30699,
24117,
30620,
24118,
30541,
24119,
30462,
24120,
30384,
24120,
30305,
24121,
30226,
24122,
30147,
24123,
30068,
24124,
29989,
24125,
29911,
24126,
29832,
24127,
29753,
24128,
29674,
24129,
29595,
24130,
29517,
24131,
29438,
24132,
29359,
24133,
29280,
24134,
29201,
24135,
29122,
24136,
29044,
24137,
28965,
24138,
28886,
24139,
28807,
24139,
28728,
24140,
28649,
24141,
28571,
24142,
28492,
24143,
28413,
24144,
28334,
24145,
28255,
24146,
28176,
24147,
28098,
24148,
28019,
24148,
27940,
24147,
27862,
24146,
27784,
24146,
27705,
24145,
27627,
24145,
27549,
24144,
27470,
24144,
27392,
24143,
27313,
24143,
27235,
24142,
27157,
24142,
27078,
24141,
27000,
24141,
26922,
24140,
26843,
24140,
26765,
24139,
26686,
24139,
26608,
24138,
26530,
24138,
26451,
24137,
26373,
24137,
26295,
24136,
26216,
24136,
26138,
24135,
26060,
24135,
25981,
24134,
25903,
24133,
25824,
24133,
25746,
24132,
25668,
24132,
25589,
24131,
25511,
24131,
25433,
24130,
25354,
24130,
25276,
24129,
25197,
24129,
25119,
24128,
25041,
24128,
24962,
24127,
24884,
24127,
24806,
24126,
24727,
24126,
24649,
24125,
24571,
24125,
24492,
24124,
24414,
24124,
24335,
24123,
24257,
24123,
24179,
24109,
24103,
24095,
24027,
24081,
23952,
24068,
23876,
24054,
23800,
24040,
23725,
24026,
23649,
24013,
23574,
23999,
23498,
23985,
23422,
23971,
23347,
23958,
23271,
23944,
23195,
23930,
23120,
23916,
23044,
23903,
22968,
23889,
22893,
23875,
22817,
23861,
22742,
23827,
22674,
23792,
22607,
23757,
22540,
23723,
22472,
23688,
22405,
23653,
22338,
23618,
22270,
23584,
22203,
23549,
22136,
23514,
22069,
23469,
22009,
23423,
21949,
23378,
21890,
23332,
21830,
23287,
21771,
23241,
21711,
23196,
21652,
23150,
21592,
23105,
21533,
23059,
21473,
23000,
21423,
22941,
21372,
22881,
21322,
22822,
21272,
22763,
21221,
22703,
21171,
22644,
21121,
22585,
21070,
22525,
21020,
22466,
20970,
22407,
20919,
22347,
20869,
22288,
20819,
22229,
20768,
22169,
20718,
22110,
20667,
22051,
20617,
21992,
20567,
21932,
20516,
21873,
20466,
21814,
20416,
21754,
20370,
21694,
20323,
21633,
20277,
21573,
20231,
21513,
20185,
21453,
20139,
21393,
20092,
21470,
20115,
21546,
20137,
21622,
20160,
21699,
20182,
21775,
20204,
21852,
20227,
21928,
20249,
22004,
20272,
22079,
20286,
22154,
20300,
22228,
20314,
22303,
20328,
22378,
20342,
22452,
20356,
22527,
20370,
22602,
20384,
22676,
20398,
22751,
20412,
22825,
20426,
22900,
20440,
22975,
20455,
23049,
20469,
23124,
20483,
23199,
20497,
23273,
20511,
23352,
20506,
23430,
20501,
23509,
20497,
23587,
20492,
23666,
20487,
23744,
20482,
23823,
20478,
23901,
20473,
23980,
20468,
24058,
20463,
24137,
20458,
24215,
20454,
24294,
20449,
24372,
20444,
24451,
20439,
24529,
20435,
24603,
20412,
24676,
20389,
24750,
20366,
24823,
20343,
24897,
20320,
24970,
20297,
25043,
20274,
25117,
20251,
25190,
20228,
25264,
20205,
25337,
20182,
25411,
20159,
25484,
20136,
25558,
20113,
25631,
20090,
25705,
20067,
25778,
20044,
25847,
20009,
25916,
19975,
25985,
19940,
26054,
19906,
26123,
19872,
26193,
19837,
26262,
19803,
26331,
19768,
26400,
19734,
26469,
19699,
26538,
19665,
26607,
19630,
26676,
19596,
26745,
19561,
26814,
19527,
26883,
19493,
26948,
19446,
27013,
19400,
27078,
19354,
27143,
19308,
27207,
19262,
27272,
19216,
27337,
19170,
27402,
19124,
27467,
19078,
27532,
19031,
27596,
18985,
27661,
18939,
27726,
18893,
27791,
18847,
27856,
18801,
27920,
18755,
27985,
18709,
28050,
18663,
28115,
18617,
28180,
18570,
28244,
18524,
28309,
18478,
28374,
18432,
28439,
18386,
28504,
18340,
28568,
18294,
28633,
18248,
28698,
18202,
28763,
18155,
28828,
18109,
28893,
18063,
28957,
18017,
29022,
17971,
29087,
17925,
29152,
17879,
29217,
17833,
29281,
17787,
29346,
17740,
29411,
17694,
29476,
17648,
29541,
17602,
29605,
17556,
29670,
17510,
29735,
17464,
29800,
17418,
29865,
17372,
29930,
17326,
29994,
17279,
30059,
17233,
30124,
17187,
30189,
17141,
30251,
17093,
30313,
17045,
30375,
16996,
30437,
16948,
30498,
16900,
30560,
16852,
30622,
16803,
30684,
16755,
30746,
16707,
30808,
16659,
30870,
16610,
30932,
16562,
30994,
16514,
31056,
16466,
31118,
16418,
31180,
16369,
31242,
16321,
31304,
16273,
31366,
16225,
31428,
16176,
31489,
16128,
31551,
16080,
31613,
16032,
31675,
15983,
31737,
15935,
31799,
15887,
31861,
15839,
31923,
15790,
31985,
15742,
32047,
15694,
32109,
15646,
32171,
15597,
32233,
15549,
32295,
15501,
32357,
15453,
32419,
15405,
32481,
15356,
32542,
15308,
32604,
15260,
32632,
15191,
32659,
15123,
32686,
15055,
32713,
14986,
32741,
14918,
32768,
14849,
32767,
14774,
32767,
14699,
32766,
14624,
32766,
14549,
32765,
14474,
32765,
14399,
32739,
14328,
32712,
14257,
32686,
14186,
32660,
14115,
32633,
14044,
32607,
13973,
32557,
13917,
32507,
13861,
32456,
13805,
32406,
13749,
32356,
13693,
32306,
13637,
32232,
13611,
32158,
13586,
32083,
13560,
32009,
13534,
31935,
13509,
31861,
13483,
31787,
13458,
31713,
13432,
31638,
13406,
31564,
13381,
31490,
13355,
31416,
13330,
31342,
13304,
31268,
13278,
31194,
13253,
31119,
13227,
31045,
13201,
30971,
13176,
30897,
13150,
30823,
13125,
30749,
13099,
30674,
13073,
30600,
13048,
30526,
13022,
30452,
12997,
30378,
12971,
30304,
12945,
30229,
12920,
30155,
12894,
30081,
12868,
30007,
12843,
29933,
12817,
29859,
12792,
29784,
12766,
29710,
12740,
29636,
12715,
29562,
12689,
29488,
12664,
29414,
12638,
29340,
12612,
29265,
12587,
29191,
12561,
29117,
12535,
29043,
12510,
28967,
12487,
28891,
12464,
28814,
12441,
28738,
12418,
28662,
12394,
28586,
12371,
28510,
12348,
28433,
12325,
28357,
12302,
28281,
12279,
28205,
12256,
28129,
12233,
28052,
12210,
27976,
12187,
27900,
12164,
27824,
12140,
27748,
12117,
27672,
12094,
27595,
12071,
27519,
12048,
27443,
12025,
27367,
12002,
27291,
11979,
27214,
11956,
27138,
11933,
27062,
11910,
26986,
11887,
26910,
11863,
26834,
11840,
26757,
11817,
26681,
11794,
26605,
11771,
26529,
11748,
26453,
11725,
26376,
11702,
26300,
11679,
26224,
11656,
26148,
11633,
26072,
11610,
25996,
11586,
25919,
11563,
25843,
11540,
25767,
11517,
25691,
11494,
25615,
11471,
25538,
11448,
25462,
11425,
25386,
11402,
25310,
11379,
25234,
11372,
25159,
11366,
25083,
11360,
25007,
11354,
24932,
11347,
24856,
11341,
24780,
11335,
24705,
11328,
24629,
11322,
24553,
11316,
24478,
11310,
24402,
11303,
24326,
11297,
24251,
11291,
24175,
11285,
24099,
11278,
24024,
11272,
23948,
11266,
23872,
11259,
23793,
11264,
23713,
11269,
23634,
11273,
23554,
11278,
23475,
11283,
23395,
11287,
23316,
11292,
23237,
11297,
23157,
11301,
23078,
11306,
22998,
11311,
22919,
11315,
22844,
11332,
22770,
11348,
22695,
11364,
22621,
11380,
22546,
11396,
22472,
11412,
22397,
11429,
22323,
11445,
22248,
11461,
22174,
11477,
22099,
11493,
22032,
11522,
21964,
11551,
21896,
11580,
21828,
11609,
21761,
11638,
21693,
11667,
21625,
11696,
21557,
11725,
21490,
11754,
21422,
11783,
21354,
11812,
21288,
11856,
21221,
11899,
21155,
11943,
21088,
11987,
21022,
12030,
20955,
12074,
20889,
12117,
20822,
12161,
20756,
12204,
20689,
12248,
20623,
12291,
20561,
12338,
20500,
12385,
20439,
12431,
20378,
12478,
20316,
12524,
20255,
12571,
20194,
12617,
20133,
12664,
20071,
12710,
20113,
12655,
20155,
12600,
20197,
12545,
20239,
12490,
20281,
12434,
20323,
12379,
20365,
12324,
20407,
12261,
20448,
12198,
20490,
12136,
20532,
12073,
20574,
12010,
20616,
11947,
20658,
11884,
20700,
11821,
20742,
11758,
20784,
11696,
20826,
11633,
20868,
11570,
20910,
11507,
20940,
11438,
20970,
11369,
21000,
11299,
21031,
11230,
21061,
11161,
21091,
11092,
21121,
11023,
21152,
10953,
21182,
10884,
21212,
10815,
21242,
10746,
21273,
10676,
21286,
10601,
21299,
10525,
21311,
10449,
21324,
10374,
21337,
10298,
21350,
10223,
21363,
10147,
21376,
10071,
21389,
9996,
21402,
9920,
21415,
9844,
21428,
9769,
21440,
9693,
21453,
9617,
21466,
9542,
21479,
9466,
21492,
9390,
21505,
9315,
21518,
9239,
21513,
9160,
21508,
9081,
21504,
9002,
21499,
8923,
21494,
8844,
21489,
8765,
21484,
8686,
21480,
8607,
21475,
8528,
21470,
8449,
21465,
8369,
21461,
8290,
21456,
8211,
21451,
8132,
21446,
8053,
21442,
7974,
21437,
7895,
21432,
7816,
21427,
7737,
21422,
7658,
21400,
7583,
21378,
7507,
21355,
7432,
21333,
7357,
21311,
7282,
21289,
7206,
21266,
7131,
21244,
7056,
21222,
6980,
21199,
6905,
21177,
6830,
21155,
6754,
21132,
6679,
21110,
6604,
21088,
6528,
21066,
6453,
21043,
6378,
21021,
6302,
20999,
6227,
20976,
6152,
20954,
6076,
20932,
6001,
20909,
5926,
20887,
5850,
20865,
5775,
20843,
5700,
20820,
5624,
20798,
5549,
20776,
5474,
20753,
5399,
20731,
5323,
20709,
5248,
20686,
5173,
20664,
5097,
20642,
5022,
20619,
4947,
20597,
4871,
20575,
4796,
20553,
4721,
20530,
4645,
20508,
4570,
20486,
4495,
20463,
4419,
20441,
4344,
20419,
4269,
20396,
4193,
20374,
4118,
20352,
4043,
20327,
3969,
20302,
3894,
20276,
3820,
20251,
3746,
20226,
3672,
20201,
3597,
20176,
3523,
20151,
3449,
20126,
3375,
20100,
3300,
20075,
3226,
20050,
3152,
20025,
3078,
20000,
3003,
19975,
2929,
19950,
2855,
19924,
2781,
19899,
2706,
19874,
2632,
19849,
2558,
19824,
2484,
19799,
2409,
19774,
2335,
19748,
2261,
19723,
2187,
19698,
2112,
19673,
2038,
19648,
1964,
19623,
1890,
19598,
1815,
19572,
1741,
19547,
1667,
19522,
1593,
19497,
1518,
19472,
1444,
19447,
1370,
19422,
1296,
19396,
1221,
19371,
1147,
19346,
1073,
19321,
999,
19296,
924,
19271,
850,
19246,
776,
19220,
702,
19195,
627,
19144,
571,
19093,
515,
19042,
458,
18990,
402,
18939,
346,
18888,
289,
18836,
233,
18785,
176,
18734,
120,
18656,
107,
18578,
93,
18500,
80,
18422,
67,
18345,
53,
18267,
40,
18189,
27,
18111,
13,
18033,
0,
17967,
13,
17901,
26,
17834,
39,
17768,
52,
17702,
65,
17636,
78,
17575,
124,
17514,
171,
17453,
217,
17392,
264,
17331,
310,
17284,
373,
17237,
436,
17190,
499,
17143,
561,
17096,
624,
17049,
687,
17003,
750,
16956,
813,
16909,
875,
16862,
938,
16815,
1001,
16768,
1064,
16722,
1127,
16675,
1189,
16628,
1252,
16581,
1315,
16534,
1378,
16487,
1440,
16440,
1503,
16394,
1566,
16347,
1629,
16300,
1692,
16253,
1754,
16206,
1817,
16159,
1880,
16113,
1943,
16066,
2006,
16019,
2068,
15972,
2131,
15925,
2194,
15878,
2257,
15832,
2320,
15785,
2382,
15738,
2445,
15691,
2508,
15644,
2571,
15597,
2633,
15550,
2696,
15504,
2759,
15457,
2822,
15410,
2885,
15363,
2947,
15316,
3010,
15269,
3073,
15223,
3136,
15176,
3199,
15129,
3261,
15082,
3324,
15038,
3390,
14993,
3456,
14949,
3522,
14904,
3589,
14860,
3655,
14816,
3721,
14771,
3787,
14727,
3853,
14682,
3919,
14638,
3985,
14594,
4051,
14549,
4118,
14505,
4184,
14460,
4250,
14416,
4316,
14372,
4382,
14327,
4448,
14283,
4514,
14238,
4580,
14194,
4647,
14150,
4713,
14105,
4779,
14061,
4845,
14016,
4911,
13972,
4977,
13928,
5043,
13883,
5109,
13839,
5176,
13794,
5242,
13750,
5308,
13706,
5374,
13661,
5440,
13617,
5506,
13572,
5572,
13528,
5638,
13483,
5705,
13439,
5771,
13395,
5837,
13350,
5903,
13306,
5969,
13261,
6035,
13217,
6101,
13173,
6167,
13128,
6234,
13084,
6300,
13039,
6366,
12995,
6432,
12951,
6498,
12923,
6571,
12896,
6645,
12868,
6718,
12841,
6791,
12813,
6864,
12786,
6938,
12759,
7011,
12731,
7084,
12704,
7157,
12676,
7230,
12649,
7304,
12621,
7377,
12594,
7450,
12566,
7523,
12539,
7597,
12512,
7670,
12484,
7743,
12457,
7816,
12429,
7890,
12402,
7963,
12396,
8041,
12390,
8120,
12384,
8198,
12378,
8277,
12372,
8355,
12366,
8433,
12361,
8512,
12355,
8590,
12349,
8669,
12343,
8747,
12337,
8826,
12331,
8904,
12325,
8983,
12319,
9061,
12313,
9139,
12308,
9218,
12302,
9296,
12296,
9375,
12290,
9453,
12302,
9531,
12314,
9609,
12325,
9687,
12337,
9765,
12349,
9843,
12361,
9921,
12373,
9999,
12384,
10077,
12396,
10155,
12408,
10233,
12420,
10311,
12432,
10389,
12444,
10466,
12455,
10544,
12467,
10622,
12479,
10700,
12491,
10778,
12518,
10853,
12545,
10928,
12573,
11003,
12600,
11078,
12627,
11153,
12655,
11228,
12682,
11303,
12709,
11378,
12661,
11362,
12622,
11309,
12582,
11256,
12543,
11204,
12503,
11151,
12464,
11098,
12415,
11037,
12365,
10976,
12316,
10915,
12267,
10854,
12217,
10793,
12168,
10732,
12119,
10671,
12069,
10610,
12020,
10549,
11971,
10488,
11921,
10427,
11864,
10375,
11807,
10323,
11749,
10271,
11692,
10219,
11635,
10167,
11578,
10116,
11520,
10064,
11463,
10012,
11406,
9960,
11349,
9908,
11291,
9856,
11227,
9814,
11163,
9773,
11099,
9731,
11035,
9689,
10971,
9647,
10907,
9605,
10843,
9564,
10779,
9522,
10714,
9480,
10650,
9438,
10586,
9396,
10516,
9365,
10447,
9334,
10377,
9303,
10307,
9273,
10237,
9242,
10167,
9211,
10097,
9180,
10028,
9149,
9958,
9118,
9888,
9087,
9818,
9056,
9746,
9035,
9673,
9014,
9601,
8992,
9528,
8971,
9456,
8950,
9383,
8929,
9311,
8907,
9238,
8886,
9166,
8865,
9093,
8844,
9021,
8822,
8943,
8811,
8865,
8800,
8787,
8789,
8709,
8778,
8631,
8767,
8553,
8756,
8475,
8745,
8397,
8734,
8319,
8723,
8241,
8712,
8163,
8701,
8085,
8690,
8007,
8689,
7929,
8687,
7851,
8686,
7772,
8684,
7694,
8683,
7616,
8681,
7538,
8680,
7460,
8678,
7382,
8676,
7304,
8675,
7225,
8673,
7147,
8672,
7069,
8670,
6991,
8669,
6913,
8667,
6835,
8666,
6756,
8664,
6678,
8663,
6600,
8661,
6522,
8660,
6444,
8658,
6366,
8657,
6288,
8655,
6209,
8653,
6131,
8652,
6053,
8650,
5975,
8649,
5897,
8647,
5819,
8646,
5740,
8644,
5662,
8643,
5584,
8641,
5506,
8640,
5428,
8638,
5350,
8637,
5272,
8635,
5193,
8634,
5115,
8632,
5037,
8631,
4959,
8629,
4881,
8627,
4803,
8626,
4724,
8624,
4646,
8623,
4568,
8621,
4490,
8620,
4412,
8618,
4333,
8620,
4254,
8621,
4175,
8623,
4097,
8625,
4018,
8626,
3939,
8628,
3860,
8629,
3781,
8631,
3702,
8632,
3623,
8634,
3545,
8636,
3466,
8637,
3387,
8639,
3308,
8640,
3229,
8642,
3150,
8643,
3072,
8645,
2993,
8646,
2914,
8648,
2835,
8650,
2756,
8651,
2677,
8653,
2599,
8654,
2520,
8656,
2441,
8657,
2362,
8659,
2283,
8661,
2204,
8662,
2126,
8664,
2047,
8665,
1968,
8667,
1889,
8668,
1810,
8670,
1731,
8672,
1652,
8673,
1574,
8675,
1495,
8676,
1416,
8678,
1337,
8679,
1258,
8681,
1179,
8683,
1101,
8684,
1022,
8686,
947,
8709,
873,
8732,
799,
8755,
725,
8779,
650,
8802,
576,
8825,
502,
8848,
457,
8902,
412,
8955,
367,
9008,
323,
9061,
278,
9114,
233,
9167,
204,
9240,
175,
9312,
146,
9384,
117,
9457,
87,
9529,
58,
9602,
29,
9674,
0,
9746,
15,
9817,
30,
9889,
46,
9960,
61,
10031,
76,
10102,
91,
10173,
107,
10244,
122,
10316,
167,
10380,
213,
10445,
258,
10509,
304,
10574,
349,
10638,
395,
10703,
440,
10767,
486,
10832,
531,
10896,
577,
10961,
622,
11025,
668,
11090,
713,
11154,
759,
11219,
804,
11283,
850,
11348,
895,
11412,
941,
11477,
986,
11541,
1032,
11606,
1077,
11670,
1123,
11735,
1168,
11799,
1214,
11864,
1259,
11928,
1305,
11993,
1350,
12057,
1396,
12122,
1441,
12186,
1487,
12251,
1532,
12315,
1578,
12380,
1623,
12444,
1669,
12509,
1714,
12573,
1760,
12638,
1805,
12702,
1851,
12767,
1896,
12831,
1942,
12896,
1987,
12960,
2033,
13025,
2078,
13089,
2124,
13154,
2169,
13218,
2217,
13281,
2264,
13344,
2311,
13406,
2359,
13469,
2406,
13531,
2454,
13594,
2501,
13657,
2549,
13719,
2596,
13782,
2643,
13844,
2691,
13907,
2738,
13970,
2786,
14032,
2833,
14095,
2881,
14157,
2928,
14220,
2976,
14283,
3023,
14345,
3070,
14408,
3118,
14470,
3165,
14533,
3213,
14596,
3260,
14658,
3308,
14721,
3355,
14783,
3403,
14846,
3450,
14909,
3497,
14971,
3545,
15034,
3592,
15096,
3640,
15159,
3687,
15222,
3735,
15284,
3787,
15344,
3840,
15403,
3892,
15463,
3945,
15523,
3997,
15582,
4050,
15642,
4102,
15702,
4155,
15761,
4207,
15821,
4260,
15881,
4312,
15940,
4365,
16000,
4417,
16060,
4470,
16119,
4522,
16179,
4575,
16239,
4627,
16298,
4680,
16358,
4732,
16418,
4785,
16477,
4837,
16537,
4890,
16597,
4951,
16646,
5012,
16695,
5073,
16744,
5134,
16794,
5195,
16843,
5256,
16892,
5317,
16942,
5378,
16991,
5439,
17040,
5500,
17089,
5561,
17139,
5622,
17188,
5684,
17237,
5745,
17287,
5806,
17336,
5867,
17385,
5936,
17418,
6004,
17451,
6073,
17484,
6142,
17517,
6211,
17550,
6280,
17583,
6348,
17616,
6417,
17649,
6486,
17682,
6555,
17715,
6624,
17747,
6692,
17780,
6761,
17813,
6830,
17846,
6899,
17879,
6968,
17898,
7038,
17917,
7108,
17935,
7177,
17954,
7247,
17973,
7317,
17992,
7386,
18010,
7456,
18029,
7526,
18048,
7605,
18055,
7684,
18063,
7763,
18070,
7842,
18077,
7921,
18085,
8000,
18092,
8079,
18099,
8158,
18107,
8237,
18114,
8316,
18122,
8396,
18129,
8469,
18133,
8543,
18137,
8617,
18140,
8690,
18144,
8764,
18148,
8838,
18152,
8912,
18156,
8985,
18159,
9059,
18163,
9133,
18167,
9206,
18171,
9280,
18175,
9354,
18178,
9280,
18199,
9206,
18220,
9132,
18241,
9058,
18262,
8984,
18282,
8910,
18303,
8836,
18324,
8762,
18353,
8688,
18383,
8614,
18412,
8541,
18441,
8467,
18471,
8393,
18500,
8319,
18529,
8246,
18559,
8172,
18588,
8098,
18617,
8024,
18647,
7950,
18676,
7877,
18705,
7803,
18735,
7739,
18779,
7674,
18823,
7610,
18868,
7546,
18912,
7482,
18956,
7418,
19000,
7353,
19045,
7289,
19089,
7225,
19133,
7161,
19178,
7096,
19222,
7032,
19266,
6968,
19311,
6904,
19355,
6852,
19411,
6800,
19467,
6747,
19524,
6695,
19580,
6643,
19636,
6591,
19692,
6539,
19748,
6487,
19805,
6435,
19861,
6383,
19917,
6331,
19973,
6279,
20030,
6226,
20086,
6174,
20142,
6122,
20198,
6080,
20266,
6037,
20333,
5995,
20401,
5952,
20468,
5910,
20536,
5867,
20604,
5825,
20671,
5782,
20739,
5740,
20806,
5697,
20874,
5655,
20941,
5612,
21009,
5570,
21076,
5527,
21144,
5485,
21212,
5442,
21279,
5415,
21354,
5388,
21428,
5361,
21503,
5334,
21578,
5306,
21652,
5279,
21727,
5252,
21802,
5225,
21876,
5198,
21951,
5171,
22026,
5143,
22100,
5116,
22175,
5089,
22249,
5062,
22324,
5035,
22399,
5008,
22473,
4980,
22548,
4953,
22623,
4926,
22697,
4899,
22772,
4872,
22847,
4844,
22921,
4817,
22996,
4790,
23071,
4763,
23145,
4736,
23220,
4709,
23295,
4681,
23369,
4654,
23444,
4627,
23518,
4600,
23593,
4573,
23668,
4545,
23742,
4518,
23817,
4491,
23892,
4464,
23966,
4437,
24041,
4410,
24116,
4382,
24190,
4355,
24265,
4328,
24340,
4301,
24414,
4274,
24489,
4247,
24564,
4219,
24638,
4192,
24713,
4165,
24787,
4138,
24862,
4111,
24937,
4088,
25013,
4065,
25089,
4042,
25165,
4019,
25241,
3996,
25317,
3972,
25393,
3949,
25469,
3926,
25545,
3903,
25621,
3880,
25697,
3857,
25774,
3834,
25850,
3811,
25926,
3788,
26002,
3765,
26078,
3742,
26154,
3719,
26230,
3696,
26306,
3673,
26382,
3650,
26458,
3627,
26534,
3604,
26610,
3581,
26686,
3558,
26763,
3535,
26839,
3512,
26915,
3489,
26991,
3466,
27067,
3443,
27143,
3420,
27219,
3397,
27295,
3374,
27371,
3351,
27447,
3328,
27523,
3305,
27599,
3282,
27675,
3259,
27752,
3236,
27828,
3213,
27904,
3190,
27980,
3167,
28056,
3144,
28132,
3121,
28208,
3098,
28284,
3075,
28360,
3052,
28436,
3029,
28512,
3028,
28590,
3028,
28668,
3027,
28745,
3027,
28823,
3026,
28900,
3053,
28962,
3079,
29024,
3105,
29085,
3132,
29147,
3158,
29208,
3214,
29264,
3269,
29319,
3325,
29374,
3381,
29430,
3436,
29485,
3492,
29540,
3548,
29596,
3603,
29651,
3673,
29672,
3743,
29693,
3812,
29714,
3882,
29735,
3952,
29756,
4022,
29777,
4091,
29798,
4161,
29819,
4237,
29796,
4312,
29773,
4388,
29750,
4463,
29727,
4539,
29704,
4614,
29681,
4690,
29658,
4766,
29635,
4841,
29612,
4917,
29590,
4992,
29567,
5068,
29544,
5144,
29521,
5219,
29498,
5295,
29475,
5370,
29452,
5446,
29429,
5521,
29406,
5597,
29383,
5673,
29360,
5748,
29337,
5824,
29314,
5899,
29292,
5975,
29269,
6051,
29246,
6126,
29223,
6202,
29200,
6277,
29177,
6353,
29154,
6429,
29131,
6504,
29108,
6580,
29085,
6655,
29062,
6731,
29039,
6806,
29016,
6882,
28993,
6958,
28971,
7033,
28948,
7109,
28925,
7184,
28902,
7260,
28879,
7336,
28856,
7411,
28833,
7487,
28810,
7562,
28787,
7638,
28764,
7712,
28738,
7786,
28711,
7860,
28685,
7934,
28658,
8009,
28631,
8083,
28605,
8157,
28578,
8231,
28552,
8305,
28525,
8379,
28499,
8454,
28472,
8528,
28446,
8602,
28419,
8676,
28392,
8750,
28366,
8824,
28339,
8899,
28313,
8973,
28286,
9047,
28260,
9121,
28233,
9195,
28207,
9269,
28180,
9344,
28154,
9418,
28127,
9492,
28100,
9566,
28074,
9640,
28047,
9714,
28021,
9789,
27994,
9863,
27968,
9937,
27941,
10011,
27915,
10085,
27888,
10159,
27861,
10233,
27835,
10308,
27808,
10382,
27782,
10456,
27755,
10530,
27729,
10604,
27702,
10678,
27676,
10753,
27649,
10827,
27622,
10901,
27596,
10975,
27569,
11049,
27543,
11123,
27516,
11198,
27490,
11272,
27463,
11346,
27437,
11420,
27410,
11487,
27371,
11553,
27333,
11619,
27294,
11686,
27256,
11752,
27217,
11819,
27179,
11885,
27140,
11952,
27101,
12018,
27063,
12085,
27024,
12151,
26986,
12218,
26947,
12284,
26908,
12351,
26870,
12409,
26819,
12467,
26769,
12526,
26718,
12584,
26668,
12643,
26617,
12701,
26567,
12760,
26516,
12818,
26465,
12876,
26415,
12935,
26364,
12993,
26314,
13052,
26263,
13110,
26213,
13169,
26162,
13218,
26102,
13267,
26042,
13316,
25982,
13366,
25921,
13415,
25861,
13464,
25801,
13513,
25741,
13562,
25681,
13612,
25620,
13661,
25560,
13710,
25500,
13759,
25440,
13808,
25380,
13858,
25320,
13907,
25259,
13937,
25190,
13968,
25120,
13998,
25051,
14029,
24981,
14059,
24912,
14090,
24842,
14120,
24773,
14151,
24704,
14181,
24634,
14212,
24565,
14242,
24495,
14273,
24426,
14304,
24356,
14334,
24287,
14365,
24217,
14395,
24148,
14420,
24072,
14445,
23996,
14470,
23920,
14495,
23844,
14520,
23768,
14545,
23692,
14570,
23616,
14595,
23540,
14620,
23464,
14645,
23389,
14647,
23465,
14650,
23542,
14653,
23618,
14656,
23695,
14659,
23771,
14662,
23848,
14665,
23924,
14668,
24001,
14671,
24077,
14674,
24154,
14677,
24231,
14679,
24307,
14682,
24384,
14688,
24459,
14694,
24535,
14700,
24611,
14706,
24687,
14712,
24762,
14717,
24838,
14723,
24914,
14729,
24989,
14735,
25065,
14741,
25141,
14747,
25217,
14753,
25292,
14772,
25362,
14792,
25432,
14811,
25502,
14831,
25571,
14851,
25641,
14870,
25711,
14890,
25780,
14909,
25850,
14929,
25920,
14966,
25989,
15002,
26058,
15039,
26127,
15076,
26196,
15113,
26265,
15149,
26333,
15186,
26402,
15223,
26471,
15260,
26540,
15296,
26609,
15333,
26678,
15370,
26747,
15407,
26816,
15443,
26885,
15480,
26954,
15517,
27023,
15554,
27092,
15604,
27152,
15654,
27213,
15704,
27273,
15754,
27333,
15803,
27394,
15853,
27454,
15903,
27515,
15953,
27575,
16003,
27636,
16053,
27696,
16103,
27756,
16153,
27817,
16203,
27877,
16253,
27938,
16303,
27998,
16353,
28058,
16403,
28119,
16453,
28179,
16515,
28228,
16578,
28277,
16641,
28325,
16703,
28374,
16766,
28423,
16828,
28472,
16891,
28520,
16954,
28569,
17016,
28618,
17079,
28666,
17141,
28715,
17204,
28764,
17267,
28813,
17329,
28861,
17392,
28910,
17454,
28959,
17517,
29008,
17580,
29056,
17642,
29105,
17705,
29154,
17767,
29203,
17830,
29251,
17892,
29300,
17955,
29349,
18018,
29398,
18080,
29446,
18143,
29495,
18205,
29544,
18268,
29592,
18331,
29641,
18393,
29690,
18456,
29739,
18518,
29787,
18581,
29836,
18644,
29885,
18706,
29934,
18769,
29982,
18831,
30031,
18894,
30080,
18957,
30129,
19019,
30177,
19082,
30226,
19144,
30275,
19207,
30323,
19269,
30372,
19332,
30421,
19397,
30467,
19461,
30513,
19526,
30560,
19591,
30606,
19655,
30652,
19720,
30698,
19785,
30744,
19849,
30791,
19914,
30837,
19979,
30883,
20043,
30929,
20108,
30976,
20173,
31022,
20237,
31068,
20302,
31114,
20367,
31160,
20431,
31207,
20496,
31253,
20561,
31299,
20625,
31345,
20690,
31392,
20755,
31438,
20819,
31484,
20884,
31530,
20949,
31576,
21014,
31623,
21078,
31669,
21143,
31715,
21208,
31761,
21272,
31808,
21337,
31854,
21402,
31900,
21466,
31946,
21531,
31993,
21596,
32039,
21660,
32085,
21725,
32131,
21790,
32177,
21854,
32224,
21919,
32270,
21984,
32316,
22048,
32362,
22113,
32409,
22178,
32455,
22242,
32501,
22307,
32547,
22372,
32593,
22446,
32615,
22521,
32637,
22596,
32659,
22670,
32681,
22745,
32703,
22819,
32724,
22894,
32746,
22969,
32768,
23044,
32747,
23119,
32725,
23194,
32704,
23269,
32682,
23344,
32661,
23419,
32639,
23494,
32618,
17730,
22519,
17678,
22463,
17626,
22408,
17574,
22352,
17522,
22297,
17470,
22242,
17417,
22186,
17365,
22131,
17313,
22075,
17261,
22020,
17209,
21964,
17156,
21909,
17104,
21854,
17052,
21798,
17000,
21743,
16964,
21675,
16928,
21606,
16891,
21538,
16855,
21470,
16819,
21402,
16783,
21334,
16747,
21266,
16710,
21198,
16674,
21130,
16638,
21061,
16602,
20993,
16565,
20925,
16529,
20857,
16493,
20789,
16457,
20721,
16421,
20653,
16401,
20580,
16381,
20508,
16361,
20435,
16341,
20363,
16321,
20290,
16301,
20218,
16280,
20145,
16260,
20073,
16240,
20000,
16220,
19928,
16200,
19855,
16180,
19783,
16160,
19710,
16140,
19638,
16120,
19565,
16119,
19491,
16118,
19417,
16117,
19343,
16117,
19269,
16116,
19195,
16115,
19121,
16137,
19056,
16159,
18991,
16182,
18926,
16204,
18861,
16227,
18796,
16284,
18759,
16341,
18722,
16398,
18685,
16456,
18648,
16513,
18611,
16586,
18627,
16660,
18643,
16734,
18659,
16807,
18675,
16881,
18690,
16940,
18732,
16999,
18775,
17058,
18817,
17117,
18859,
17176,
18901,
17235,
18943,
17294,
18985,
17347,
19043,
17399,
19101,
17452,
19159,
17504,
19217,
17557,
19275,
17610,
19333,
17662,
19391,
17715,
19449,
17755,
19518,
17795,
19587,
17835,
19656,
17874,
19725,
17914,
19794,
17954,
19863,
17994,
19932,
18034,
20001,
18074,
20070,
18114,
20139,
18154,
20208,
18193,
20277,
18233,
20346,
18273,
20415,
18313,
20484,
18353,
20553,
18393,
20622,
18433,
20691,
18457,
20767,
18482,
20842,
18507,
20918,
18532,
20994,
18556,
21070,
18581,
21146,
18606,
21221,
18631,
21297,
18655,
21373,
18665,
21446,
18674,
21520,
18683,
21593,
18692,
21666,
18701,
21740,
18710,
21813,
18719,
21886,
18729,
21960,
18738,
22033,
18731,
22107,
18724,
22180,
18717,
22254,
18710,
22327,
18703,
22400,
18672,
22455,
18640,
22510,
18609,
22564,
18578,
22619,
18510,
22648,
18442,
22677,
18375,
22706,
18307,
22736,
18239,
22765,
18175,
22734,
18112,
22703,
18048,
22672,
17985,
22642,
17921,
22611,
17858,
22580,
17794,
22549,
11333,
21658,
11281,
21608,
11230,
21559,
11178,
21510,
11126,
21460,
11119,
21395,
11112,
21330,
11105,
21265,
11098,
21200,
11091,
21135,
11119,
21066,
11147,
20998,
11174,
20929,
11202,
20860,
11230,
20792,
11257,
20723,
11285,
20655,
11313,
20586,
11340,
20517,
11368,
20449,
11396,
20380,
11423,
20312,
11451,
20243,
11500,
20182,
11549,
20120,
11598,
20059,
11648,
19998,
11697,
19937,
11746,
19876,
11795,
19814,
11845,
19753,
11894,
19692,
11943,
19631,
11992,
19570,
12041,
19508,
12091,
19447,
12140,
19386,
12189,
19325,
12238,
19264,
12300,
19217,
12361,
19171,
12422,
19125,
12484,
19079,
12545,
19033,
12607,
18986,
12668,
18940,
12729,
18894,
12791,
18848,
12852,
18802,
12913,
18756,
12975,
18709,
13036,
18663,
13097,
18617,
13159,
18571,
13220,
18525,
13281,
18478,
13349,
18451,
13416,
18423,
13484,
18395,
13551,
18367,
13619,
18339,
13686,
18311,
13754,
18284,
13821,
18256,
13900,
18249,
13980,
18243,
14059,
18236,
14138,
18229,
14217,
18223,
14280,
18256,
14343,
18289,
14405,
18321,
14468,
18354,
14494,
18422,
14519,
18490,
14545,
18558,
14571,
18626,
14562,
18703,
14552,
18780,
14543,
18858,
14534,
18935,
14524,
19012,
14496,
19080,
14467,
19148,
14439,
19216,
14411,
19284,
14382,
19352,
14354,
19421,
14326,
19489,
14278,
19551,
14230,
19613,
14182,
19676,
14134,
19738,
14086,
19801,
14038,
19863,
13990,
19925,
13943,
19988,
13895,
20050,
13847,
20112,
13799,
20175,
13751,
20237,
13703,
20300,
13655,
20362,
13608,
20424,
13560,
20487,
13512,
20549,
13464,
20612,
13405,
20663,
13346,
20714,
13287,
20765,
13228,
20816,
13169,
20867,
13109,
20918,
13050,
20969,
12991,
21020,
12932,
21071,
12873,
21122,
12807,
21163,
12741,
21203,
12675,
21244,
12609,
21285,
12543,
21325,
12477,
21366,
12411,
21406,
12344,
21447,
12278,
21488,
12211,
21511,
12145,
21535,
12078,
21559,
12011,
21582,
11944,
21606,
11877,
21630,
11810,
21653,
11743,
21677,
11675,
21674,
11607,
21670,
11538,
21667,
11470,
21664,
11401,
21661,
17819,
17378,
17752,
17344,
17685,
17310,
17617,
17276,
17550,
17242,
17482,
17208,
17437,
17157,
17392,
17105,
17347,
17054,
17302,
17003,
17291,
16926,
17280,
16850,
17269,
16774,
17296,
16714,
17323,
16654,
17350,
16594,
17376,
16534,
17436,
16487,
17496,
16440,
17556,
16393,
17616,
16346,
17676,
16299,
17736,
16253,
17796,
16206,
17856,
16159,
17916,
16112,
17976,
16065,
18046,
16040,
18117,
16015,
18187,
15990,
18258,
15965,
18328,
15940,
18398,
15915,
18469,
15891,
18539,
15866,
18610,
15841,
18680,
15816,
18751,
15791,
18821,
15766,
18891,
15741,
18962,
15716,
19032,
15691,
19108,
15685,
19183,
15679,
19258,
15674,
19333,
15668,
19409,
15662,
19484,
15656,
19559,
15650,
19634,
15644,
19710,
15639,
19785,
15633,
19860,
15627,
19935,
15621,
20010,
15615,
20086,
15610,
20161,
15604,
20236,
15598,
20311,
15592,
20387,
15586,
20463,
15600,
20539,
15614,
20615,
15629,
20692,
15643,
20768,
15657,
20844,
15671,
20920,
15685,
20996,
15699,
21073,
15713,
21149,
15727,
21225,
15741,
21301,
15755,
21378,
15770,
21454,
15784,
21503,
15842,
21553,
15901,
21602,
15960,
21652,
16019,
21701,
16077,
21751,
16136,
21737,
16208,
21723,
16279,
21710,
16351,
21696,
16422,
21682,
16494,
21669,
16565,
21604,
16612,
21540,
16658,
21476,
16704,
21411,
16750,
21347,
16797,
21283,
16843,
21218,
16889,
21154,
16936,
21090,
16982,
21025,
17028,
20950,
17052,
20874,
17076,
20798,
17100,
20722,
17123,
20646,
17147,
20570,
17171,
20494,
17195,
20419,
17219,
20343,
17242,
20267,
17266,
20191,
17290,
20115,
17314,
20039,
17338,
19964,
17361,
19885,
17371,
19807,
17380,
19729,
17389,
19651,
17398,
19573,
17407,
19495,
17417,
19417,
17426,
19339,
17435,
19261,
17444,
19182,
17454,
19104,
17463,
19026,
17472,
18948,
17481,
18870,
17490,
18792,
17500,
18717,
17490,
18642,
17481,
18567,
17472,
18493,
17462,
18418,
17453,
18343,
17443,
18268,
17434,
18193,
17425,
18119,
17415,
18044,
17406,
17969,
17397,
17894,
17387,
12353,
16461,
12281,
16428,
12209,
16395,
12137,
16362,
12065,
16329,
11993,
16296,
11921,
16263,
11849,
16231,
11777,
16198,
11705,
16165,
11633,
16132,
11561,
16099,
11489,
16066,
11428,
16024,
11366,
15981,
11304,
15939,
11242,
15896,
11180,
15854,
11118,
15812,
11057,
15769,
10995,
15727,
10933,
15685,
10871,
15642,
10809,
15600,
10748,
15558,
10696,
15504,
10644,
15450,
10592,
15396,
10540,
15343,
10488,
15289,
10436,
15235,
10384,
15181,
10332,
15127,
10280,
15074,
10228,
15020,
10200,
14951,
10172,
14882,
10144,
14813,
10117,
14744,
10089,
14675,
10061,
14606,
10033,
14537,
10058,
14467,
10083,
14397,
10108,
14328,
10133,
14258,
10201,
14219,
10270,
14180,
10339,
14141,
10407,
14101,
10484,
14103,
10560,
14105,
10637,
14106,
10714,
14108,
10791,
14110,
10867,
14111,
10944,
14113,
11021,
14114,
11097,
14116,
11174,
14118,
11251,
14119,
11327,
14121,
11400,
14147,
11472,
14172,
11545,
14198,
11618,
14224,
11690,
14250,
11763,
14275,
11835,
14301,
11908,
14327,
11981,
14352,
12053,
14378,
12126,
14404,
12198,
14430,
12271,
14455,
12343,
14481,
12416,
14507,
12489,
14532,
12553,
14576,
12618,
14619,
12682,
14663,
12747,
14706,
12812,
14750,
12876,
14794,
12941,
14837,
13005,
14881,
13070,
14924,
13135,
14968,
13199,
15011,
13264,
15055,
13328,
15098,
13393,
15142,
13458,
15185,
13522,
15229,
13587,
15272,
13633,
15334,
13680,
15395,
13727,
15457,
13774,
15518,
13820,
15580,
13867,
15641,
13914,
15703,
13960,
15764,
14007,
15825,
14054,
15887,
14101,
15948,
14147,
16010,
14156,
16081,
14166,
16152,
14175,
16223,
14184,
16294,
14156,
16347,
14128,
16401,
14100,
16454,
14072,
16508,
14010,
16542,
13947,
16575,
13885,
16608,
13823,
16642,
13747,
16651,
13672,
16659,
13596,
16668,
13521,
16677,
13446,
16685,
13368,
16669,
13290,
16653,
13211,
16637,
13133,
16621,
13055,
16605,
12977,
16589,
12899,
16573,
12821,
16557,
12743,
16541,
12665,
16525,
12587,
16509,
12509,
16493,
12431,
16477,
15635,
15392,
15604,
15330,
15573,
15267,
15542,
15204,
15512,
15141,
15481,
15079,
15450,
15016,
15419,
14953,
15406,
14883,
15393,
14813,
15379,
14742,
15366,
14672,
15353,
14602,
15340,
14532,
15326,
14462,
15313,
14391,
15300,
14321,
15304,
14242,
15308,
14163,
15313,
14084,
15317,
14005,
15321,
13926,
15325,
13846,
15330,
13767,
15334,
13688,
15338,
13609,
15343,
13530,
15347,
13451,
15351,
13372,
15355,
13293,
15360,
13214,
15364,
13135,
15368,
13056,
15373,
12976,
15377,
12897,
15381,
12818,
15408,
12747,
15434,
12675,
15461,
12604,
15488,
12533,
15514,
12461,
15541,
12390,
15568,
12319,
15594,
12247,
15621,
12176,
15647,
12104,
15674,
12033,
15701,
11962,
15727,
11890,
15754,
11819,
15781,
11747,
15807,
11676,
15834,
11605,
15876,
11546,
15919,
11488,
15961,
11429,
16003,
11371,
16046,
11312,
16088,
11254,
16131,
11196,
16189,
11158,
16247,
11121,
16305,
11084,
16364,
11047,
16422,
11009,
16498,
11020,
16574,
11030,
16650,
11040,
16726,
11050,
16772,
11100,
16819,
11149,
16865,
11198,
16912,
11247,
16959,
11296,
16976,
11374,
16993,
11451,
17010,
11528,
17027,
11605,
17044,
11683,
17061,
11760,
17078,
11837,
17095,
11915,
17112,
11992,
17130,
12069,
17147,
12146,
17164,
12224,
17181,
12301,
17198,
12378,
17194,
12453,
17189,
12527,
17185,
12602,
17181,
12676,
17176,
12751,
17172,
12826,
17168,
12900,
17163,
12975,
17159,
13049,
17155,
13124,
17150,
13198,
17146,
13273,
17142,
13347,
17137,
13422,
17133,
13497,
17112,
13574,
17091,
13651,
17069,
13728,
17048,
13805,
17027,
13882,
17006,
13959,
16985,
14036,
16964,
14113,
16942,
14191,
16921,
14268,
16900,
14345,
16879,
14422,
16858,
14499,
16820,
14565,
16781,
14630,
16743,
14696,
16705,
14762,
16667,
14827,
16629,
14893,
16591,
14959,
16553,
15024,
16515,
15090,
16477,
15155,
16438,
15221,
16378,
15272,
16317,
15323,
16256,
15375,
16196,
15426,
16132,
15444,
16069,
15462,
16005,
15480,
15941,
15498,
15880,
15477,
15819,
15456,
15757,
15435,
15696,
15413])


### This sine wave works ok

#length = 4930 / 2
#for idx in range(length):
#    rawdata.append(round(math.sin(idx / length * 2 * math.pi) * (dac_x_max // 2) + (dac_x_max // 2)))
#    rawdata.append(round(math.sin(idx / length * 2 * math.pi) * (dac_y_max // 2) + (dac_x_max // 2)))

### 200k (maybe 166.667k) seems to be practical limit
### 1M permissible but seems same as around 200k

### This prints 4930
print("rawdata length", len(rawdata))

bizarre_workaround = False
if bizarre_workaround:
    rawdata.append(0)
    rawdata.append(0)
    rawdata.append(0)

print("rawdata adjusted length", len(rawdata))

### Change this to True and everything is ok - very odd!
overwrite_values = False

if overwrite_values:
    for idx in range(len(rawdata)):
        rawdata[idx] = idx * 6
    
### Also does it at 200*1000
output_wave = audioio.RawSample(rawdata,
                                channel_count=2, sample_rate = 100 * 1000)

### This shifts very slowly around in a surprising way, the two samples
### are probably not the same length for playback even though they are!
dacs.play(output_wave, loop=True)
while True:
    pass