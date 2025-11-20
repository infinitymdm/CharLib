import PySpice
import matplotlib.pyplot as plt
from numpy import average

from charlib.characterizer import utils
from charlib.characterizer.procedures import register, ProcedureFailedException
from charlib.liberty import liberty
from charlib.liberty.library import LookupTable

@register
def sequential_worst_case(cell, config, settings):
    """Measure worst-case sequential transient and propagation delays"""
    for variation in config.variations('data_slews', 'loads', 'clock_slew'):
        for path in cell.paths():
            print(path)
            pass # TODO: yield a tuple (function, args, max)

@register
def sequential_average(cell, config, settings):
    """Measure sequential transient and propagation delays using a uniform average"""
    for variation in config.variations('data_slews', 'loads', 'clock_slew'):
        for path in cell.paths():
            print(path)
            pass # TODO: yield a tuple (function, args, average)

def measure_clock_to_q_delays(cell_settings, charlib_settings, data_pin, trigger_pin, state_pin):
    """Measure the delay between trigger activation and state change.

    For clock-edge-triggered devices, this is commonly called the clock-to-Q or C2Q delay. This
    value depends on the transition time of both the data pin and the trigger pin."""
