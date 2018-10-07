
all: Evillaugh.wav Wilhelm_Scream.wav

### https://learn.adafruit.com/circuitpython-made-easy-on-circuit-playground-express/play-file
### 22050 is maximum - remix is making this mon
%.wav: %.ogg
	sox $< $@ rate 16000 # remix 1,2

### From https://en.wikipedia.org/wiki/File:Evillaugh.ogg
Evillaugh.ogg:
	wget 'https://upload.wikimedia.org/wikipedia/commons/8/84/Evillaugh.ogg'

### From https://en.wikipedia.org/wiki/File:Wilhelm_Scream.ogg
Wilhelm_Scream.ogg:
	wget 'https://upload.wikimedia.org/wikipedia/commons/d/d9/Wilhelm_Scream.ogg'


Evillaugh.wav: Evillaugh.ogg
Wilhelm_Scream.wav: Wilhelm_Scream.ogg



