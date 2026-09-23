import io
import pickle

from aiida.engine import calcfunction
from aiida.orm import Dict, List, SinglefileData, Str
from aiida_spice.utils import parse_includes

from charlib import liberty
from charlib.characterizer.characterizer import unit_registry
from charlib.characterizer.port import Role
from charlib.characterizer.procedures import CharacterizationProcedure, utils
from charlib.characterizer.procedures.utils import QuantityData


class PinCapacitanceChargeIntegrationProcedure(CharacterizationProcedure):
    """Measure input capacitance for each input by integrating charge with respect to time.

    Treat the cell as a grounded capacitor with fixed capacitance. With all non-target pins in a high-impedance state,
    apply a rise or fall voltage waveform with the specified slew time. Each edge can be integrated to produce values
    for rise_capacitance and fall_capacitance liberty attributes respectively.

    This procedure is modified from the charge_integration procedure originally contributed by GitHub user
    e-dworkin.
    """

    @classmethod
    def define(cls, spec):
        super().define(spec)

        # Procedure-specific inputs
        spec.input(
            "parameters.in_cap.resistance.shunt",
            valid_type=QuantityData,
            help="Shunt resistance applied to all circuit nodes",
        )
        spec.input(
            "parameters.in_cap.time.slew",
            valid_type=QuantityData,
            help="The amount of time the input voltage waveform should take to slew from low to high and vice versa",
        )
        spec.input(
            "parameters.in_cap.voltage.min",
            valid_type=QuantityData,
            help="The minimum input voltage",
        )
        spec.input(
            "parameters.in_cap.voltage.max",
            valid_type=QuantityData,
            help="The maximum input voltage",
        )

    def build_netlists(self):
        self.setup_initial_netlist()
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
            slew_time=self.inputs.parameters.in_cap.time.slew,
            min_voltage=self.inputs.parameters.in_cap.voltage.min,
            max_voltage=self.inputs.parameters.in_cap.voltage.max,
        )

    def run_simulations(self):
        includes = parse_includes(next(iter(self.ctx.netlists.values())))
        analyses = prepare_analyses(self.inputs.parameters.in_cap.time.slew)
        options = prepare_options(self.inputs.simulation.temperature, self.inputs.parameters.in_cap.resistance.shunt)

        for pin_direction, netlist in self.ctx.netlists.items():
            builder = self.inputs.settings.simulation.engine.get_builder()
            builder.netlist = netlist
            builder.includes = includes
            builder.analyses = analyses
            builder.options = options
            builder.metadata.options.resources = {"num_machines": 1, "num_mpiprocs_per_machine": 1}
            key = f"spice_results.{pin_direction}"
            future = self.submit(builder)
            self.to_context(**{key: future})

    def write_liberty(self):
        capacitances = {}
        for pin, sim_node in self.ctx.spice_results.items():
            capacitances[pin + ".rise"] = calculate_capacitance(
                sim_node.rise.outputs.measurements,
                self.inputs.parameters.in_cap.voltage.max,
                self.inputs.settings.units.capacitance,
            )
            capacitances[pin + ".fall"] = calculate_capacitance(
                sim_node.fall.outputs.measurements,
                self.inputs.parameters.in_cap.voltage.max,
                self.inputs.settings.units.capacitance,
            )
        libfile = create_liberty_pin_cap_group(self.inputs.cell.name, **capacitances)
        self.out("liberty", libfile)


@calcfunction
def create_stimulus_netlists(
    netlist_header: List, ports: Dict, slew_time: QuantityData, min_voltage: QuantityData, max_voltage: QuantityData
) -> SinglefileData:
    """For each non-power pin, set up a netlist with an input PWL voltage ramping from min_voltage to max_voltage"""
    netlists = {}
    vmin = min_voltage.quantity.to("volts").magnitude
    vmax = max_voltage.quantity.to("volts").magnitude
    tslew = slew_time.quantity.to("seconds").magnitude
    for target_pin, port in ports.get_dict().items():
        if port.get("role", None) in [Role.POWER, Role.GROUND, Role.PWELL, Role.NWELL]:
            continue
        for direction, (v0, v1) in {"rise": (vmin, vmax), "fall": (vmax, vmin)}.items():
            netlist = [f".title {target_pin} input capacitance voltage ramp ({direction})"]
            netlist.extend(netlist_header.get_list())
            netlist.append(utils.voltage_supply("stimulus", f"PWL(0 {v0} {tslew} {v1})"), target_pin)
            netlists[target_pin + "." + direction] = SinglefileData.from_string(
                "\n".join(netlist), filename=f"netlist_{target_pin}_{direction}.spice"
            )
    return netlists


@calcfunction
def prepare_analyses(slew_time: QuantityData) -> List:
    tslew = slew_time.quantity.to("seconds").magnitude
    return List(
        list=[
            f".tran 0 {tslew}",
            f".meas tran qtest INTEG i(vstimulus) from=0 to={tslew}",
        ]
    )


@calcfunction
def prepare_options(temperature: QuantityData, shunt_resistance: QuantityData) -> Dict:
    return Dict(
        dict={
            "temp": temperature.quantity.to("degC").magnitude,
            "rshunt": shunt_resistance.quantity.to("ohms").magnitude,
        }
    )


@calcfunction
def calculate_capacitance(measurements: Dict, max_voltage: QuantityData, unit: Str) -> QuantityData:
    vmax = max_voltage.quantity
    qtest = measurements.get_dict().get("qtest", float("nan")) * unit_registry("coulombs")
    capacitance = qtest / vmax
    return QuantityData(capacitance.to(unit.value))


@calcfunction
def create_liberty_pin_cap_group(cell_name: Str, **capacitances: QuantityData) -> SinglefileData:
    cell_group = liberty.Group("cell", cell_name.value)
    for pin_direction, capacitance in capacitances.items():
        pin, direction = pin_direction.split(".")
        pin_group = liberty.Group("pin", pin)
        pin_group.add_attribute(f"{direction}_capacitance", capacitance.quantity.magnitude)
        cell_group.add_group(pin_group)
    with io.BytesIO() as stream:
        pickle.dump(cell_group, stream)
        stream.seek(0)  # Reset to start of stream
        return SinglefileData(file=stream, filename=f"{cell_name.value}_pin_cap_frequency_sweep.lib")
