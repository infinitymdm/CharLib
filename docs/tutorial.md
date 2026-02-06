## CharLib Tutorial

This document is designed to guide you through the process of using CharLib for the first time.

Over the course of this tutorial, we will:
+ Discuss what CharLib is (and what it isn't).
+ Look at a few open source PDKs and how they are structured.
+ Download a PDK and locate the SPICE models corresponding to each standard cell.
+ Install ngspice and CharLib.
+ Set up a YAML file to configure CharLib for the downloaded standard cells.
+ Use CharLib to characterize the cells, producing a Liberty file with NLDM timing results.

### What is CharLib?

CharLib is a program designed to measure the electrical properties of standard cells, the building
blocks of digital circuits.

When a chip designer is getting ready to manufacture an integrated circuit, he or she generally
likes to have an estimate of how well it will work. How much power will it use? How fast will it
be able to run? These are the questions that characterization helps to answer. If I know how fast
all the building blocks are and how much power they use, it's not too hard to calculate those
specs for a larger chip design made up of those blocks.

So by measuring the timing and power properties of standard cells, I can easily extrapolate and
figure out the properties of a big, complicated chip. This is what CharLib does. You give it a
bunch of standard cells, and it measures their properties by simulating them in a bunch of
different situations.

> Now you might (justifiably) ask: _Why not just simulate a whole big chip design?_ The answer to
that question is twofold. First of all, simulating a large, complicated circuit is much slower than
simulating many small, simple circuits. It's a lot quicker to have all the standard cells
pre-characterized, then use those measurements to give an estimate of the larger circuit's
properties. We can do this pretty accurately these days, especially with advanced characterization
formats such as ECSM and CCSM. Secondly, most large chips *do* get simulated, but only near the
very end of development. It's far too computationally expensive to simulate a large chip after
every single revision, but doing the simulation on a completed (or nearly completed) design can
get you a few percentage points better accuracy for your power and timing estimates.

### Where do I get standard cells?

Standard cells are usually distributed as part of a Process Design Kit, or PDK. Historically, you
would talk to a semiconductor foundry about manufacturing a chip, and they would provide you with
the PDK. This is still more or less true, but there are also several open source PDKs which are
publicly available. Google - Tim "mithro" Ansell in particular - deserves a lot of credit for
sponsoring these efforts (even though they've recently stepped away from open source silicon).

Let's take a look at a couple of open source PDKs. We're not going to cover everything that's in a
PDK, but we will go over some of the general concepts.

#### Global Foundries 180nm PDK

We'll begin with the GF180MCU PDK. This is an open source PDK, so all of its files are publicly
available [here on GitHub](https://github.com/google/gf180mcu-pdk).

Now from the files listed on the github page, I already know I'm probably only interested in the
"libraries" folder. Most of these files aren't going to be relevant to what we're doing here, and
I can generally tell that by the file extension. For instance these ".rst" files are mostly going
to be documentation on how to contribute to this repository, or maybe if I'm lucky they'll contain
some info on where to find things, but right now I can guess that the standard cell library is most
likely in the "libraries" folder. Let's start there.

Here I see some more interesting names. The first "gf180" bit is the same for all of these, so we
can ignore that; we're interested in what distinguishes these folders.
- The first one ends in "sram". I can guess that this is going to contain memory blocks.
- The second one ends in "io". That's probably going to contain layouts for bond pads and pins --
    stuff for interfacing with the real world. That will be really important later on when I want
    to make an actual chip, but that's not what we're looking for right now.
- The third folder ends in "pr" which is a shorthand for "primitives". This is going to contain
    stuff like transistor models, rules for how resistors and capacitors work, and other "basic"
    electronic elements. I'll need some stuff from here. We'll come back to this later.
- The fourth and fifth folders each start with "sc" (short for "standard cells") and then some
    extra gobbledygook. Those extra letters and numbers tell us two things:
    - How many "tracks", or layers of metal, the cells are allowed to use. For example the 7t
        library is going to have 7 tracks of metal, and the 9t library will have 9. Generally the
        less tracks, the cheaper the manufacturing will be, but that's not at all universal.
    - What voltage the cells are designed for. Both of these show "5v0", so I know they're built
        for 5.0 volts. If they said something like "1v8", I'd know we were looking at a 1.8V
        library instead. Hopefully that's pretty straightforward.

For now, let's see what's in the 7-track standard cell library. Clicking through, we see a link to
a submodule -- a different GitHub repository used to track the 7-track cells independently from the
rest of the PDK. This is pretty typical for these open source PDKs, so we just follow that link.

Here we have the 7-track standard cell library, and once again I can guess where I want to go from
the folder names. Most likely what I'm after is going to be under "cells", though there's a chance
it could be under "models". "tech" probably contains information on how these cells are physically
laid out.

While we're here, I also want to point out the "liberty" folder. This contains several Liberty
files, each of which contains characterization information for these standard cells under a
particular set of operating conditions and manufacturing tolerances, or "corners". So for example
these "tt" files each assume that all the transistors in each cell are "typical" average-speed
transistors for this manufacturing process; not any faster or slower than the average transistor.
Likewise the "ff" and "ss" files have details for fast & power-hungry transistors or slow but
reliable transistors. The "25C", "40C", and "125C" bit refers to the operating temperature, and
number "v" number bit refers to the supply voltage used. This is in the same format as we talked
about before, with the "v" taking the place of the decimal. Look at how wildly different some of
these numbers are! That tells you that this is a very flexible standard cell library, that can
work (albeit probably not very quickly) even under very low voltages compared to the "standard"
5.0V that the library was designed around.

Now these liberty files are exactly what CharLib is designed to produce. That's where it fits into
the chip design process: the idea is that cell designers such as foundries can use CharLib to
characterize their cells, then provide those liberty files to others who want to use those cells in
a design.

Ok, but back to the cells. That's what we're here for. Let's go back up one folder and switch to
the "cells" directory.

In this directory we have a bunch of folders that each correspond to some type of gate or device.
Stuff like full adders, half adders, AND gates with various numbers of inputs, et cetera. Scrolling
down I can see we've got quite a few different types of cells. Let's take a look at what
information we get for each cell by looking at a 2-input AND gate as an example.

Ok, there are a bunch of different types of files in here. In particular though, I want to point
out three different files:

> At this point this part of the script falls apart because there aren't spice files in the repo.
Pivot to using ciel and put less focus on PDK structure.

#### Skywater 130nm
