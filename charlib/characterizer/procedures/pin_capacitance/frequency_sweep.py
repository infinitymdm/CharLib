import logging

import numpy as np
from aiida.common.extendeddicts import AttributeDict
from aiida.engine import calcfunction
from aiida.orm import ArrayData, Dict, List, SinglefileData, Str

from charlib.characterizer.port import Direction, Role
from charlib.characterizer.procedures import CharacterizationProcedure, QuantityData, ureg, utils

logger = logging.getLogger(__name__)


class PinCapacitanceImpedanceDividerProcedure(CharacterizationProcedure):
    """Measure input capacitance for each input from the capacitive reactance.

    Treat the cell as a grounded capacitor with fixed capacitance. Add a series resistor to the target pin, then apply
    an AC voltage waveform. Compute the capacitance from an impedance divider with the series resistor.
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

        spec.outline(cls.prepare_netlists, cls.run_spice_simulations, cls.write_liberty)

    def prepare_netlists(self):
        """Construct spice netlists for downstream simulation"""
        model_lib = self.inputs.settings.model.lib if "lib" in self.inputs.settings.model else None
        includes = utils.setup_netlist_includes(self.inputs.cell.netlist, self.inputs.settings.model.file, model_lib)
        supplies = utils.setup_netlist_supplies(named_nodes=self.inputs.settings.named_nodes)
        ordered_pins = utils.read_pins_in_netlist_order(self.inputs.cell.name, self.inputs.cell.netlist)
        self.ctx.netlists = prepare_pin_capacitance_netlists(
            cell=self.inputs.cell,
            named_nodes=self.inputs.settings.named_nodes,
            parameters=self.inputs.parameters.in_cap,
            includes=includes,
            supplies=supplies,
            ordered_pins=ordered_pins,
        )

    def run_spice_simulations(self):
        """Run all spice simulations"""
        # Includes, analyses, and options are the same for all netlists, just get these once
        includes = utils.read_includes_from_netlist(next(iter(self.ctx.netlists.values())))
        analyses = prepare_analyses(parameters=self.inputs.parameters.in_cap)
        options = prepare_options(self.inputs.settings.simulation.temperature, self.inputs.parameters.resistance.shunt)
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
def prepare_pin_capacitance_netlists(  # noqa: PLR0913 PLR0917
    cell: AttributeDict,
    named_nodes: AttributeDict,
    parameters: AttributeDict,
    includes: List,
    supplies: List,
    ordered_pins: List,
) -> SinglefileData:
    """Set up netlists for measuring each input pin's capacitance"""
    ports = cell.ports.get_dict()

    # Prepare for subcircuit wire-up, which does not vary with target pin
    subcircuit_connections = []
    for pin_name in ordered_pins.get_list():
        if pin_name not in ports:
            logger.warning(f'Port "{pin_name}" not found in port listing for cell {cell.name.value}')
            continue
        match ports[pin_name].get("role", None):
            case Role.POWER:
                subcircuit_connections.append(named_nodes.power.name.value)
            case Role.GROUND:
                subcircuit_connections.append(named_nodes.ground.name.value)
            case Role.NWELL:
                subcircuit_connections.append(named_nodes.nwell.name.value)
            case Role.PWELL:
                subcircuit_connections.append(named_nodes.pwell.name.value)
            case _:
                subcircuit_connections.append(pin_name)

    # Produce netlists targeting each input pin
    input_ports = [k for k, v in ports.items() if v.get("direction", None) == Direction.IN]
    netlists = {}
    vstimulus_amplitude = parameters.voltage.quantity.to("volts").magnitude
    rseries_resistance = parameters.resistance.series.quantity.to("ohms").magnitude
    for target_name in input_ports:
        netlist = [f".title {cell.name.value}__port_{target_name}__in_cap__frequency_sweep"]
        netlist.extend(includes.get_list())
        netlist.extend(supplies.get_list())
        netlist.append(f"Vstimulus 0 vstimulus DC 0 AC {vstimulus_amplitude}")
        netlist.append(f"Rseries vstimulus vtest {rseries_resistance}")
        netlist.append(f"Valias vtest {target_name} 0")  # 0VDC source for node aliasing
        netlist.append(f"Xdut {' '.join(subcircuit_connections)} {cell.name.value}")
        # FIXME: Query the database for this node before creating a new one
        netlists[target_name] = SinglefileData.from_string("\n".join(netlist))

    return netlists


@calcfunction
def prepare_analyses(parameters: AttributeDict) -> List:
    min_frequency = parameters.frequency.min.quantity.to("Hz").magnitude
    max_frequency = parameters.frequency.max.quantity.to("Hz").magnitude
    return List(list=[f".ac dec 10 {min_frequency} {max_frequency}"])


@calcfunction
def prepare_options(temperature: QuantityData, shunt_resistance) -> Dict:
    return Dict(
        dict={
            "temp": temperature.quantity.to("degC").magnitude,
            "rshunt": shunt_resistance.quantity.to("ohms").magnitude,
        }
    )


@calcfunction
def calculate_capacitance(parameters: AttributeDict, trace_data: ArrayData, unit: Str):
    """Compute the capacitance from the capacitive reactance"""
    vstim = trace_data.get_array("vstimulus") * ureg("volts")
    vtest = trace_data.get_array("vtest") * ureg("volts")
    frequency = trace_data.get_array("frequency") * ureg("Hertz")
    r_series = parameters.resistance.series.quantity
    impedance = r_series * vtest / (vstim - vtest)
    capacitive_reactance = -np.imag(impedance)
    capacitance = 1 / (2 * np.pi * frequency * capacitive_reactance)
    return QuantityData(capacitance.to(unit.value))
