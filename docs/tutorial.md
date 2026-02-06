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
More recently the FOSSi Foundation has put together some impressive tools to make it easier than
ever to download and use these open source PDKs.

Let's walk through the process of downloading a PDK using the FOSSi Foundation's `ciel` tool.
For starters, you'll need to be on a macOS or Linux system and have a recent version of Python
installed. There are plenty of guides on how to set Python up; just make sure you have version 3.8
or newer and PIP.

Ok. Step one is to open up a terminal. And let's start by checking what version of Python I have
installed. Looks like I've got 3.12, which is plenty new enough for this.

Next let's get `ciel` installed. Following the instructions on `ciel`'s GitHub, let's run

`python3 -m pip install --user --upgrade --no-cache-dir ciel`

Ok, looks like that was successful. So next we can use `ciel` to install some PDKs and take a look
at their files. Let's start with Global Foundries' 180 nanometer PDK, "GF180MCU". I'm first going
to use `ciel`'s `ls-remote` command to check what versions are available.

`ciel ls-remote --pdk-family gf180mcu`

In the output here I can see that the latest version isn't too old, released the day after
Christmas last year. Let's install that version. First I'll copy that commit hash, then we can run

`ciel enable --pdk-family gf180mcu 54435919abffb937387ec956209f9cf5fd2dfbee`

Looks like that was successful as well. Now where did it put all those files it just downloaded?
Well `ciel` by default puts pdks under a folder called ".ciel" in your user home directory. So
let's navigate there and take a look. I'll use the `cd` command without any arguments to get home,
then navigate down into the ".ciel" folder. Using `ls -l` we can see that there are a couple of
folders here now: gf180mcu A through D. According to
[Tim Edwards](http://www.opencircuitdesign.com/analog_flow/), a fellow who definitely knows a thing
or two in this field, each of these folders is a different variant of the PDK. A has 3 metal
layers, B has four, C has five, and D has five but also a thicker top metal layer. For now let's
look at the gf180mcuD folder.




Here's where we run into our first question: how do we know which folder we want? Well, in order to
use CharLib, there are three things we need:
+ SPICE models describing how the transistors work in this manufacturing process.
+ SPICE models of the standard cells we're trying to characterize.
+ A YAML configuration file that points to those spice files and tells CharLib about the cells.

So the primary thing we're looking for here is SPICE files. The easiest way to find those is
probably to search for them, so let's try that. First, let's try searching for files with the
".spice" extension. Using the `find` command I can see that we have several files
