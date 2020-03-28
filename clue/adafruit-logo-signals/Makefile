PNGTOPLOTWAV=./pngtoplotwav.py

all: adafruit-spinning-logo-plot-2chan.wav

adafruit-logo.gif:
	wget https://cdn-learn.adafruit.com/guides/images/000/000/603/medium500/Logo.gif
	mv Logo.gif $@

### clone magic in convert is to preserve existing size
frames: adafruit-logo.gif
	mkdir $@ ; for frame in {00..4} ; \
	do \
	  convert $< -page +11-10 -background black -flatten \
                  \( +clone -background black -rotate $$(echo $${frame}/5*72 | bc -l) \) \
                  -gravity center -compose Src -composite \
                  -resize 500x500 -threshold 50% $@/adafruit-logo.spinning.frame.$${frame}.png ; \
	done

### Dependencies are not strictly correct
adafruit-spinning-logo-plot-2chan.wav: frames
	$(PNGTOPLOTWAV) -f 1.5 -o $@ frames/adafruit-logo.spinning.frame.*.png

