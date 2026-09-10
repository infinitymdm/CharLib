import io
import logging
import pickle

import numpy as np
from aiida.engine import calcfunction
from aiida.orm import ArrayData, Dict, List, SinglefileData, Str
from aiida_spice.calculations import parse_includes

from charlib import liberty
from charlib.characterizer.characterizer import unit_registry
from charlib.characterizer.port import Role
from charlib.characterizer.procedures import CharacterizationProcedure, utils
from charlib.characterizer.procedures.utils import QuantityData

logger = logging.getLogger(__name__)


class PinCapacitanceImpedanceDividerProcedure(CharacterizationProcedure):
    """Measure input capacitance for each input from the capacitive reactance.

    Treat the cell as a grounded capacitor with fixed capacitance. Add a series resistor to the target pin, then apply
    an AC voltage waveform. Compute the capacitance by impedance division with the known resistor.
    """

    @classmethod
    def define(cls, spec):
        super().define(spec)

        # Procedure-specific inputs
        spec.input(
            "parameters.in_cap.frequency.min",
            valid_type=QuantityData,
            help="Input AC voltage waveform minimum frequency",
        )
        spec.input(
            "parameters.in_cap.frequency.max",
            valid_type=QuantityData,
            help="Input AC voltage waveform maximum frequency",
        )
        spec.input(
            "parameters.in_cap.voltage",
            valid_type=QuantityData,
            help="Input AC voltage waveform amplitude",
        )
        spec.input(
            "parameters.in_cap.resistance.series",
            valid_type=QuantityData,
            help="Resistance placed in series with each pin during impedance measurement",
        )
        spec.input(
            "parameters.in_cap.resistance.shunt",
            valid_type=QuantityData,
            help="Shunt resistance applied to all circuit nodes",
        )

        spec.outline(
            cls.setup_initial_netlist, cls.prepare_simulation_netlists, cls.run_spice_simulations, cls.write_liberty
        )

    def prepare_simulation_netlists(self):
        """Construct spice netlists for downstream simulation"""
        ordered_pins = utils.read_pins_in_netlist_order(self.inputs.cell.name, self.inputs.cell.netlist.path)
        named_nodes = self.inputs.settings.named_nodes
        subckt_connections = utils.create_generic_subcircuit_connections(
            self.inputs.cell.ports,
            ordered_pins,
            power=named_nodes.power.name,
            ground=named_nodes.ground.name,
            nwell=named_nodes.nwell.name,
            pwell=named_nodes.pwell.name,
        )
        subcircuit = utils.create_generic_subcircuit(self.inputs.cell.name, subckt_connections)
        common_netlist = utils.combine_lists(self.ctx.initial_netlist, subcircuit)
        self.ctx.netlists = create_stimulus_netlists(
            netlist_header=common_netlist,
            ports=self.inputs.cell.ports,
            stimulus_voltage=self.inputs.parameters.in_cap.voltage,
            series_resistance=self.inputs.parameters.in_cap.resistance.series,
        )

    def run_spice_simulations(self):
        """Run all spice simulations"""
        # Includes, analyses, and options are the same for all netlists, just get these once
        includes = parse_includes(next(iter(self.ctx.netlists.values())))
        analyses = prepare_analyses(
            self.inputs.parameters.in_cap.frequency.min, self.inputs.parameters.in_cap.frequency.max
        )
        options = prepare_options(
            self.inputs.settings.simulation.temperature, self.inputs.parameters.in_cap.resistance.shunt
        )

        # Submit a simulation job for each netlist
        for pin, netlist in self.ctx.netlists.items():
            builder = self.inputs.settings.simulation.engine.get_builder()
            builder.netlist = netlist
            builder.includes = includes
            builder.analyses = analyses
            builder.options = options
            builder.metadata.options.resources = {"num_machines": 1, "num_mpiprocs_per_machine": 1}
            key = f"spice_results.{pin}"
            future = self.submit(builder)
            self.to_context(**{key: future})

    def write_liberty(self):
        """Create a liberty cell group with capacitance for each input pin"""
        capacitances = {}
        for pin, sim_node in self.ctx.spice_results.items():
            capacitances[pin] = calculate_capacitance(
                self.inputs.parameters.in_cap.resistance.series,
                sim_node.outputs.trace_data,
                self.inputs.settings.units.capacitance,
            )
        libfile = create_liberty_group(self.inputs.cell.name, **capacitances)
        self.out("liberty", libfile)


@calcfunction
def create_stimulus_netlists(
    netlist_header: List, ports: Dict, stimulus_voltage: QuantityData, series_resistance: QuantityData
) -> SinglefileData:
    """For each non-power pin, set up a netlist with AC input stimulus and a known real impedance on the pin"""
    target_pins = []
    for name, port in ports.get_dict().items():
        if port.get("role", None) in [Role.POWER, Role.GROUND, Role.PWELL, Role.NWELL]:
            continue
        target_pins.append(name)
    netlists = {}
    vstimulus = stimulus_voltage.quantity.to("volts").magnitude
    rseries = series_resistance.quantity.to("ohms").magnitude
    for target_pin in target_pins:
        netlist = [f".title {target_pin} input capacitance impedance divider"]
        netlist.extend(netlist_header.get_list())
        netlist.append(utils.voltage_supply("stimulus", f"DC 0 AC {vstimulus}"))
        netlist.append(utils.resistor("series", rseries, "test", "stimulus"))
        netlist.append(utils.voltage_supply("alias", 0, "test", target_pin))  # 0VDC source for node aliasing
        netlists[target_pin] = SinglefileData.from_string("\n".join(netlist), filename=f"netlist_{target_pin}.spice")
    return netlists


@calcfunction
def prepare_analyses(min_frequency: QuantityData, max_frequency: QuantityData) -> List:
    fmin = min_frequency.quantity.to("Hz").magnitude
    fmax = max_frequency.quantity.to("Hz").magnitude
    return List(list=[f".ac dec 10 {fmin} {fmax}"])


@calcfunction
def prepare_options(temperature: QuantityData, shunt_resistance: QuantityData) -> Dict:
    return Dict(
        dict={
            "temp": temperature.quantity.to("degC").magnitude,
            "rshunt": shunt_resistance.quantity.to("ohms").magnitude,
        }
    )


@calcfunction
def calculate_capacitance(series_resistance: QuantityData, trace_data: ArrayData, unit: Str):
    vstim = trace_data.get_array("v_stimulus") * unit_registry("volts")
    vtest = trace_data.get_array("v_test") * unit_registry("volts")
    frequency = trace_data.get_array("frequency") * unit_registry("Hz")
    r_series = series_resistance.quantity
    impedance = r_series * vtest / (vstim - vtest)
    capacitive_reactance = -np.imag(impedance.magnitude) * impedance.units
    capacitance = 1 / (2 * np.pi * frequency * capacitive_reactance)
    capacitance = np.mean(capacitance.real.astype(float))  # FIXME: pass to aggregator instead
    return QuantityData(capacitance.to(unit.value))


@calcfunction
def create_liberty_group(cell_name: Str, **capacitances: QuantityData) -> SinglefileData:
    cell_group = liberty.Group("cell", cell_name.value)
    for pin, capacitance in capacitances.items():
        pin_group = liberty.Group("pin", pin)
        pin_group.add_attribute("capacitance", capacitance.quantity.magnitude)
        cell_group.add_group(pin_group)
    with io.BytesIO() as stream:
        pickle.dump(cell_group, stream)
        stream.seek(0)  # Reset to start of stream
        return SinglefileData(file=stream, filename=f"{cell_name.value}_pin_cap_frequency_sweep.lib")
