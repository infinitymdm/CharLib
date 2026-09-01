from charlib.characterizer.port import Direction, Role
from charlib.characterizer.procedures import CharacterizationProcedure, QuantityData


class PinCapacitanceFrequencySweepProcedure(CharacterizationProcedure):
    """Measure input capacitance for each input pin using an ac sweep.

    Treat the cell as a grounded capacitor with fixed capacitance. Perform an ac sweep with fixed current amplitude, then evaluate capacitance as d/ds(i(s)/v(s))
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

        spec.outline(cls.build_netlists, cls.run_spice_simulations, cls.calculate_capacitance, cls.write_liberty)

    def build_netlists(self):
        """Construct spice netlists for downstream simulation"""
        ports = self.inputs.cell.ports.get_dict()

        subcircuit_connections = []
        for pin_name in self.get_subckt_line().split()[2:]:
            if pin_name not in ports:
                self.logger.warning(f'"{pin_name}" does not appear in ports for cell {self.inputs.cell.name}')
                continue
            match ports[pin_name].get("role", None):
                case Role.POWER:
                    subcircuit_connections.append(self.inputs.settings.named_nodes.power.name.value)
                case Role.GROUND:
                    subcircuit_connections.append(self.inputs.settings.named_nodes.ground.name.value)
                case Role.NWELL:
                    subcircuit_connections.append(self.inputs.settings.named_nodes.nwell.name.value)
                case Role.PWELL:
                    subcircuit_connections.append(self.inputs.settings.named_nodes.pwell.name.value)
                case _:
                    subcircuit_connections.append(f"v{pin_name}")

        input_pins = [p for p in ports if p.get("direction", None) == Direction.IN]
        for pin in input_pins:
            netlist = [f".title {self.inputs.cell.name.value}__{pin}__in_cap__frequency_sweep"]
            netlist = self.setup_supplies(netlist)
            netlist.append(f"Istimulus 0 v{pin} DC 0 AC {self.inputs.parameters.in_cap.current}")
            netlist.append(f"Xdut {*subcircuit_connections} {self.inputs.cell.name}")

            # TODO: Write to file

    def run_spice_simulations(self):
        """Run all spice simulations"""
        pass  # TODO

    def calculate_capacitance(self):
        """Compute capacitance from simulation results"""
        pass  # TODO

    def write_liberty(self):
        """Create a liberty cell group with capacitance for each input pin"""
        pass  # TODO
