
all: Evillaugh.wav Wilhelm_Scream.wav \
     PistolRicochet.wav

### https://learn.adafruit.com/circuitpython-made-easy-on-circuit-playground-express/play-file
### 22050 is maximum - remix is making this mono
%.wav: %.ogg
	sox $< -c 1 -b 8 $@ rate 16000 # remix 1,2

### From https://en.wikipedia.org/wiki/File:Evillaugh.ogg
Evillaugh.ogg:
	wget 'https://upload.wikimedia.org/wikipedia/commons/8/84/Evillaugh.ogg'

### From https://en.wikipedia.org/wiki/File:Wilhelm_Scream.ogg
Wilhelm_Scream.ogg:
	wget 'https://upload.wikimedia.org/wikipedia/commons/d/d9/Wilhelm_Scream.ogg'

213925__diboz__pistol-riccochet.ogg:
	@echo Login and download this from https://freesound.org/people/Diboz/sounds/213925/

PistolRicochet.ogg: 213925__diboz__pistol-riccochet.ogg
	ln -s $< $@

PistolRicochet.wav: PistolRicochet.ogg
	sox --norm $< -c 1 -b 8 $@ rate 16000 # remix 1,2 and normalize audio (makes this one louder)

Evillaugh.wav: Evillaugh.ogg
Wilhelm_Scream.wav: Wilhelm_Scream.ogg
PistolRicochet.wav: 213925__diboz__pistol-riccochet.ogg


