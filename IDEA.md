## Background

* Take the work we already did on the ~/Developer/pta-module-gridseq to avoid rewriting the same things over and over again (but always check if we can improve something)

* Create a new repo on GitHub using, as always my personal profile (federico-pepe) as instructed by CLAUDE.md

## Idea

* The idea of this new BCA Sequencer is quite simple: it's still a MIDI sequencer but I want to have different Layouts that I can switch by using the "Layout" button on Push. When I switch layout I always want to have an OSD Feedback as Push normally does. The layout simply change the way the sequencer information are displayed on the screen and on the pads, they don't change the overall functionality.

* Start always with 4 tracks but let the user add new tracks by pressing +

* The scene launch button always control the speed/rate of the sequencer (from 1/4 the bottom one to 1/32t the top one)

* Let's dim lit the Repeat and Accent buttons by default. When Accent is pressed, it goes on: let use the full white LED color to display that is currently active. When Accent is on the default velocity of pads is 127. Press the Accent button again to turn it off (and dim the led).

* Same as above for the Repeat button, when Repeat is on, the Scene Launch button controls the numbers of repeats (1 to 8 from top to bottom). Same LED dynamic that I just described for the Accent button.

* If I press the "Scale" button I enter a menu that let me select the root key and the scale and an "in key on/off" mode that I'll explain later.

### Layout 1:
Divide the 64x64 grid into four 4x4 grids, each quadrant is the sequencer for a different track so top-left 4x4 is track 1, top-right 4x4 is track 2, bottom left 4x4 is track 3 , bottom right 4x4 is track 4. 

The color of the pads MUST always match the color of the track. When the sequencer is Playing, the pad should turn green to display the current playing step.

If I press Page <> I go back and forward 4 tracks (so it'll be track 5, 6, 7, 8 etc).

The sequencer should move forward by rows like this:
..x.
....
....
....

then 
....
x...
....
....

then
....
....
..x.
....

When I press a pad, I simply trigger one step on/off. The LED of that pad should turn white. Shift + pad should select the pad without changing the trigger on/off.

On the screen: divide the screen in 4 columns and display. Each column represent a track and should match the color of the corresponding track. When in "playing" mode I see the values that are triggered by the step sequencer (like C3, D3 etc...). When a pad is selected becuase I just triggered it or by pressing Shift+select I enter Edit mode for that pad and I can control 8 parameters using the encoder of the top of the screen (which should have a bit of friction as we did in the gridseq module). The 8 parameters are:

* Pitch
* Velocity
* Gate
* Probability
* Offset
* MIDI Channel

Since we'll always see 4 tracks at a time, draw the corners around the portion of the screen to highlight which tracks we're working on and maybe turn the color on that track white while we're working on it. The 8 controls parameters should be displayed as two rows of 4 controls.

### Layout 2
Grid still divided in four 4x4 quadrants but we only display two tracks: top left and bottom left are the two sequencers running as above, the quadrants on the right controls the pitch (like a 16 pitches mode).

If "In Key" is set to On we need to color the pad of the root note of the same color of the track. All other pads should be white and will set the note/pitch for the selected step/pad.

If "In Key" is set to Off, root note has the same color of the track, in scale notes are white, out of scale note pads are unlit.

We always start from the bottom left of the quadrant and go right and then up.

Example in C major, in Key mode on:
A4 B4 C5 D5
D4 E4 F4 G4
G3 A3 B3 C4
C3 D3 E3 F3

Example in C major with Key mode off:
C4 C#4 D4 D#4
G#3 A3 A#3 B3
E3 F3 F#3 G3
C3 C#3 D3 D#3

Of course we can use the Octave up/down button to move up/down with octaves. Please display an OSD with the range currently controlled when we do that so we know exactly where we are.