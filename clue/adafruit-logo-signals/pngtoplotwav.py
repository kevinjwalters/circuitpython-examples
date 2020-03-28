#!/usr/bin/python3


import getopt
import sys
import array
import struct

import imageio
import wave

### globals
debug = 0
verbose = False
movie_file = False
output = "twochanplot.wav"
fps = 1
threshold = 128

max_dac_v = 3.3
### 16 bit wav files always use signed representation for data
offtopscreen = 32767      ### 3.30V
syncvalue    = -32768     ### 0.00V
### image from 3.00V to 0.30V
topvalue     = round(3.30 / max_dac_v * 65535) - 32768
bottomvalue  = round(0.00 / max_dac_v * 65535) - 32768


def usage(exit_code):
    print("pngtowav: [-f fps] [-h] [-m] [-o outputfilename] [-v]",
          file=sys.stderr)
    if exit_code is not None:
        sys.exit(exit_code)

def main(cmdlineargs):
    global debug, fps, movie_file, output
    global threshold, verbose

    try:
        opts, args = getopt.getopt(cmdlineargs,
                                   "f:hmo:rs:v", ["help", "output="])
    except getopt.GetoptError as err:
        print(err,
              file=sys.stderr)
        usage(2)
    for opt, arg in opts:
        if opt == "-f":
            fps = float(arg)
        elif opt in ("-h", "--help"):
            usage(0)
        elif opt == "-m":
             movie_file = True
        elif opt in ("-o", "--output"):
            output = arg
        elif opt == "-v":
            verbose = True
        else:
            print("BAD OPTION",
                  file=sys.stderr)
            sys.exit(2)

    raw_output = array.array("h", [])
    raw_output = array.array("h", [])

    ### Reach each frame, either
    ### many single image filenames in args or
    ### one or more video (animated gifs) (needs -m on command line)
    screenyrange = topvalue - bottomvalue
    for arg in args:
        if verbose: print("PROCESSING", arg)
        if movie_file:
            images = imageio.mimread(arg)
        else:
            images = [imageio.imread(arg)]

        for img in images:
            img_height, img_width = img.shape
            x_nopixels = img_height // 2
            if verbose: print("W,H", img_width, img_height)
            for x_col in range(img_width):
                top = None
                bottom = None
                for y_t in range(img_height):
                    if img[x_col, y_t] > threshold:
                        top = y_t
                        break
                if top is not None:
                    for y_b in range(img_height - 1, y_t - 1, -1):
                        if img[x_col, y_b] > threshold:
                            bottom = y_b
                            break
                ### If not found then use the default value
                if top is None and bottom is None:
                    top = x_nopixels
                    bottom = x_nopixels
                if verbose: print("Adding top/bottom at pixels: ", top, bottom)
                ch1_val = round(topvalue - bottom / (img_height - 1) * screenyrange)
                ch2_val = round(topvalue - top / (img_height - 1) * screenyrange)
                if verbose: print("Channel values: ", ch1_val, ch2_val)
                raw_output.append(ch1_val)
                raw_output.append(ch2_val)

    ### Write wav file
    wav_filename = output
    wav_file = wave.open(wav_filename, "w")
    nchannels = 2
    sampwidth = 2
    framerate = round(img_width * fps)
    nframes = len(raw_output)
    comptype = "NONE"
    compname = "not compressed"
    if verbose: print("Writing wav file", wav_filename,
                      "with", nchannels,
                      "channel(s) at rate", framerate,
                      "with", nframes, "samples")
    wav_file.setparams((nchannels, sampwidth, framerate, nframes,
                       comptype, compname))
    wav_file.writeframes(raw_output)
    wav_file.close()


if __name__ == "__main__":
    main(sys.argv[1:])
