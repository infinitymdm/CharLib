import logging

import numpy as np
from aiida.common.extendeddicts import AttributeDict
from aiida.engine import calcfunction
from aiida.orm import ArrayData, Dict, List, SinglefileData, Str
from aiida_spice.calculations import parse_includes

from charlib.characterizer.characterizer import unit_registry
from charlib.characterizer.port import Direction
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
        ordered_pins = utils.read_pins_in_netlist_order(self.inputs.cell.name, self.inputs.cell.netlist)
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
        analyses = prepare_analyses(parameters=self.inputs.parameters.in_cap)
        options = prepare_options(self.inputs.settings.simulation.temperature, self.inputs.parameters.resistance.shunt)

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
        for pin, results in self.ctx.spice_results.items():
            capacitance = calculate_capacitance(
                parameters=self.inputs.parameters.in_cap,
                trace_data=results.trace_data,
                unit=self.inputs.settings.units.capacitance,
            )
            self.logger.warning(f"C: {capacitance.quantity:~}")
        # FIXME: Actually write a liberty group
        self.out("liberty", self.inputs.cell.netlist)


@calcfunction
def create_stimulus_netlists(
    netlist_header: List, ports: Dict, stimulus_voltage: QuantityData, series_resistance: QuantityData
) -> SinglefileData:
    """For each input pin, set up a netlist with AC input stimulus and a known real impedance on the input pin"""
    input_pins = [k for k, v in ports.get_dict().items() if v.get("direction", None) == Direction.IN]
    netlists = {}
    vstimulus = stimulus_voltage.quantity.to("volts").magnitude
    rseries = series_resistance.quantity.to("ohms").magnitude
    for target_pin in input_pins:
        netlist = [f".title {target_pin} input capacitance impedance divider"]
        netlist.extend(netlist_header.get_list())
        netlist.append(utils.voltage_supply("stimulus", f"DC 0 AC {vstimulus}"))
        netlist.append(utils.resistor("series", rseries, "test", "stimulus"))
        netlist.append(utils.voltage_supply("alias", 0, "test", target_pin))  # 0VDC source for node aliasing
        netlists[target_pin] = SinglefileData.from_string("\n".join(netlist))
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
def calculate_capacitance(parameters: AttributeDict, trace_data: ArrayData, unit: Str):
    """Compute the capacitance from the capacitive reactance"""
    vstim = trace_data.get_array("stimulus") * unit_registry("volts")
    vtest = trace_data.get_array("test") * unit_registry("volts")
    frequency = trace_data.get_array("frequency") * unit_registry("Hz")
    r_series = parameters.resistance.series.quantity
    impedance = r_series * vtest / (vstim - vtest)
    capacitive_reactance = -np.imag(impedance)
    capacitance = 1 / (2 * np.pi * frequency * capacitive_reactance)
    return QuantityData(capacitance.to(unit.value))
