import PySpice

from charlib.characterizer import utils
from charlib.characterizer.procedures import register, ProcedureFailedException
from charlib.liberty import liberty
from charlib.liberty.library import LookupTable

@register
def metastability_binary_search(cell, config, settings):
    """Find the minimum setup & hold time such that the cell can still register data."""
    for variation in config.variations('data_slews', 'clock_slew'):
        for path in cell.paths():
            yield (naive_binary_search_setup_hold_constraint, cell, config, settings, variation, path)

def naive_binary_search_setup_hold_constraint(cell, config, settings, variation, path):
    """Given a particular path through the cell, find the worst-case minimum setup & hold time.

    This method tests all nonmasking conditions which produce the state transition indicated in
    the `path` tuple with the given slew rate and capacitive load, then returns data for the
    worst-case (i.e. largest) setup & hold times.

    Setup time is the minimum amount of time that a data input must be set before the trigger to
    avoid metastability. For example, in a noninverting D-flip-flop clocked on the rising edge, the
    setup time is the minimum amount of time between an edge in the data input signal and the
    rising edge of the clock such that the device eventually registers the data input to the
    noninverting output.

    Similarly, hold time is the minimium amount of time that a data input must remain set *after*
    the trigger in order to avoid metastability. To use the same D-flip-flop example as before,
    this is the minimum time between the rising clock edge and an edge in the data input such that
    the device eventually registers the input.

    :param cell: A Cell object to test.
    :param config: A CellTestConfig object containing cell-specific test configuration details.
    :param settings: A CharacterizationSettings object containing library-wide configuration
                     details.
    :param variation: A dict containing test parameters for this configuration variation, such
                      as slew rates and constraint search bounds.
    :param path: A list in the format [input_port, input_transition, output_port,
                 output_transtition] describing the path under test in the cell.
    """
    [input_port, _, output_port, _] = path
    data_slew = variation['data_slew'] * settings.units.time
    clock_slew = variation['clock_slew'] * settings.units.time
    load = 1e-3 * settings.units.capacitance # Use a small capacitance to
    vdd = settings.primary_power.voltage * settings.units.voltage
    vss = settings.primary_ground.voltage * settings.units.voltage

    # Compute minimum setup & hold constraint for all nonmasking conditions
    analyses = []
    measurement_names = set()
    for state_map in cell.nonmasking_conditions_for_path(*path):
        # Build the test circuit
        circuit = utils.init_circuit('seq_setup_hold_search', cell.netlist, config.models)
        circuit.V('dd', 'vdd', circuit.gnd, vdd)
        circuit.V('ss', 'vss', circuit.gnd, vss)

        # Initialize device under test and wire up ports
        # TODO:
        # Clear any existing state
        # Trigger the desired state change
        print(state_map)

    return cell.liberty # TODO



def find_recovery_constraint(cell, config, settings, variation, path):
    """Find the minimum time a control pin must be active before the trigger.

    This is analagous to setup time for an asynchronous control pin.

    For example, for a rising-edge DFF with an asynchronous reset, recovery time is the minimum
    time the reset signal must be active before the rising clock edge in order to reset the device
    state."""
    pass # TODO

def find_removal_constraint(cell, config, settings, variation, path):
    """Find the mimimum time a control pin must remain active after the trigger.

    This is analagous to hold time for an asynchronous control pin.

    For example, for a rising-edge DFF with an asynchronous reset, removal time is the minimum time
    that the reset signal must remain active after the rising clock edge in order to reset the
    device state."""
    pass # TODO

def binary_search_setup_hold_constraint(cell_settings, charlib_settings, data_pin, trigger_pin, state_pin):
    """Find the minimum time the data pin must be set preceding and following the trigger.

    The minimum time the data pin must be set before the trigger is the setup time. The minimum
    time the data pin must be set after the trigger is the hold time.

    This method measures both constraints using a binary search algorithm. Each delay is bisected
    repeatedly until the device fails to change state during simulation until minima are found for
    both constraints."""
    pass # TODO
