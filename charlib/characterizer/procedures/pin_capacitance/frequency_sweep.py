from charlib.characterizer import utils
from charlib.characterizer.cell import Port
from charlib.characterizer.procedures import Procedure
from charlib.characterizer.procedures.aggregates import SelectMean
from charlib.liberty import liberty
import numpy as np
import PySpice
from PySpice.Unit import *

class InputCapacitanceFrequencySweep(Procedure):
    """Measure input pin capacitance by performing an AC frequency sweep"""

    @classmethod
    def variation_params(cls) -> list:
        return ['loads']

    @classmethod
    def runtime_params(cls) -> list:
        return [
            'in_cap_start_frequency',
            'in_cap_end_frequency',
            'in_cap_shunt_resistance',
            'in_cap_current_amplitude',
            'in_cap_selection_criterion',
        ]

    @classmethod
    def measurements(cls):
        cell_grp = liberty.Group('cell', 'unknown')
        pin_grp = liberty.Group('pin', 'unknown')
        pin_grp.add_attribute('capacitance')
        cell_grp.add_group(pin_grp)
        return cell_grp

    @classmethod
    def check_target(cls, cell, config) -> bool:
        has_inputs = bool(cell.inputs)
        has_params = all(p in config.parameters for p in cls.runtime_params())
        return has_inputs and has_params

    @classmethod
    def generate(cls, cell, config, settings):
        """Build digraphs for measuring the input capacitance of each pin"""
        # Each pin's digraph should have 2 topological layers:
        # 1. Measure capacitance for each variation
        # 2. Use some criterion to determine the input capacitance result

        for target_pin in cell.filter_pins(direction=['input']):
            def liberty_callback(result):
                add_attr_to_liberty_pin_group(cell.name, target_pin.name, 'capacitance', result)
            for variation in config.variations(cls.variation_params() + cls.runtime_params()):
                in_cap_procedure = cls(cell, target_pin, **variation)
            select_procedure = SelectMean(liberty_callback, ) # TODO: How do I map inputs to the results?


    def __init__(self, cell, target_pin, **kwargs)
        # Store target cell name
        self._target_cell_name = cell.name

        # Store variation params
        self._variation = {
            'target_cell': cell.name
            'target_pin': target_pin.name
        }
        param_keys = self.variation_params() + self.runtime_params()
        self._variation |= {k: kwargs.get(k) for k in param_keys}

        # Store liberty skeleton
        cell_group = cell.liberty
        pin_group = liberty.Group('pin', target_pin.name)
        pin_group.add_attribute('capacitance')
        cell_group.add_group(pin_group)
        self._liberty = cell_group

    def simulate(self, cell, settings):
        """Use an AC frequency sweep to measure the capacitance of the target pin.

        Treat the cell as a grounded capacitor. Perform an AC sweep with a fixed current amplitude,
        then evaluate capacitance as d/ds(i(s)/v(s)).
        """
        v_supply = settings.primary_power.voltage * settings.units.voltage
        v_ground = settings.primary_ground.voltage * settings.units.voltage

        i_in = self.variation['in_cap_current_amplitude'] * settings.units.current

        circuit = utils.init_circuit(self.__name__, cell.netlist, config.models,
                                     settings.named_nodes, settings.units)
        circuit.I('input', circuit.gnd, 'input', f'DC 0 AC {PySpice.Spice.unit.str_spice(i_in)}')


def add_attr_to_liberty_pin_group(cell_name, pin_name, attr_name, value):
    # TODO
