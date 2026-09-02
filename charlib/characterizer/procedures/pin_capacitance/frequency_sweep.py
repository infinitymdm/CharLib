import logging

from aiida.common.extendeddicts import AttributeDict
from aiida.engine import ToContext, calcfunction
from aiida.orm import Dict, Float, FolderData, List, SinglefileData
from aiida_spice.utils.include_paths import get_include_paths

from charlib.characterizer.port import Direction, Role
from charlib.characterizer.procedures import CharacterizationProcedure, QuantityData, utils

logger = logging.getLogger(__name__)


class PinCapacitanceFrequencySweepProcedure(CharacterizationProcedure):
    """Measure input capacitance for each input pin using an ac sweep.

    Treat the cell as a grounded capacitor with fixed capacitance. Perform an ac sweep with fixed current amplitude,
    then evaluate capacitance as d/ds(i(s)/v(s)).
    """

    @classmethod
    def define(cls, spec):
        super().define(spec)

        # Procedure-specific inputs
        spec.input("parameters.in_cap.frequency.min", valid_type=QuantityData, help="Minimum sweep frequency")
        spec.input("parameters.in_cap.frequency.max", valid_type=QuantityData, help="Maximum sweep frequency")
        spec.input(
            "parameters.in_cap.current",
            valid_type=QuantityData,
            help="Constant amplitude for the input current waveform",
        )
        spec.input("parameters.in_cap.shunt_resistance", valid_type=QuantityData, help="Shunt resistance for all nodes")

        spec.outline(cls.prepare_netlists, cls.run_spice_simulations, cls.calculate_capacitance, cls.write_liberty)

    def prepare_netlists(self):
        """Construct spice netlists for downstream simulation"""
        model_lib = self.inputs.settings.model.lib if "lib" in self.inputs.settings.model else None
        includes = utils.setup_netlist_includes(self.inputs.cell.netlist, self.inputs.settings.model.file, model_lib)
        supplies = utils.setup_netlist_supplies(self.inputs.settings.named_nodes)
        ordered_pins = utils.read_pins_in_netlist_order(self.inputs.cell.name, self.inputs.cell.netlist)
        self.ctx.netlists = prepare_pin_capacitance_netlists(
            self.inputs.cell,
            self.inputs.settings.named_nodes,
            self.inputs.parameters.in_cap.current,
            includes,
            supplies,
            ordered_pins,
        )

    def run_spice_simulations(self):
        """Run all spice simulations"""
        includes, analyses, options = prepare_spice_input_nodes(
            next(iter(self.ctx.netlists.values())), self.inputs.parameters, self.inputs.settings.simulation.temperature
        )
        simulation_nodes = {}
        for pin, netlist in self.ctx.netlists.items():
            builder = self.inputs.settings.simulation.engine.get_builder()
            builder.netlist = netlist
            builder.includes = includes
            builder.analyses = analyses
            builder.options = options
            builder.metadata.options.resources = {"num_machines": 1, "num_mpiprocs_per_machine": 1}
            simulation_nodes[pin] = self.submit(builder)
        return ToContext(**simulation_nodes)

    def calculate_capacitance(self):
        """Compute capacitance from simulation results"""
        pass  # TODO

    def write_liberty(self):
        """Create a liberty cell group with capacitance for each input pin"""
        pass  # TODO


@calcfunction
def prepare_pin_capacitance_netlists(  # noqa: PLR0913 PLR0917
    cell: AttributeDict,
    named_nodes: AttributeDict,
    current: QuantityData,
    includes: List,
    supplies: List,
    ordered_pins: List,
) -> SinglefileData:
    """Set up netlists for measuring each input pin's capacitance with an AC frequency sweep"""
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
    for target_name in input_ports:
        netlist = [f".title {cell.name.value}__{target_name}__in_cap__frequency_sweep"]
        netlist.extend(includes.get_list())
        netlist.extend(supplies.get_list())
        netlist.append(f"Istimulus 0 {target_name} DC 0 AC {current.quantity:~}")
        netlist.append(f"Xdut {*subcircuit_connections} {cell.name.value}")
        # FIXME: Query the database for this node before creating a new one
        netlists[target_name] = SinglefileData.from_string("\n".join(netlist))

    return netlists


@calcfunction
def prepare_spice_input_nodes(netlist: SinglefileData, parameters: AttributeDict, temperature: Float):
    """Prepare input nodes for spice calculations"""
    includes = FolderData()
    with netlist.as_path() as netlist_path:
        for include_file in get_include_paths(netlist_path):
            includes.put_object_from_file(include_file, path=include_file.name)

    analyses = List(list=[".ac dec 100 {parameters.in_cap.frequency.min:~} {parameters.in_cap.frequency.max:~}"])

    options = Dict(
        dict={
            "temp": temperature,
            "rshunt": parameters.in_cap.shunt_resistance.quantity.to("ohms").magnitude,
        }
    )

    return includes, analyses, options
