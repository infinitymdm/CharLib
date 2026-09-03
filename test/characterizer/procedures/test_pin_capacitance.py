from aiida import load_profile
from aiida.engine import run
from aiida.orm import Dict, Float, SinglefileData, Str, load_code

from charlib.characterizer.port import Direction, Role, Trigger
from charlib.characterizer.procedures import QuantityData, ureg
from charlib.characterizer.procedures.pin_capacitance.frequency_sweep import PinCapacitanceImpedanceDividerProcedure


def test_pin_cap_impedance_divider():
    """Test the PinCapacitanceImpedanceDividerProcedure workchain with a known-capacitance example"""
    load_profile()
    spice_code = load_code(label="ngspice@localhost")
    test_circuit = SinglefileData.from_string(
        """
        .subckt rc_circuit IN VGND OUT
        R0 IN OUT 10
        C0 IN VGND 100p
        .ends"""
    )
    test_model = SinglefileData.from_string("* model with no content")

    inputs = {
        "cell": {
            "name": Str("rc_circuit"),
            "netlist": test_circuit,
            "functions": Dict(
                dict={
                    "OUT": "IN",
                }
            ),
            "ports": Dict(
                dict={
                    "OUT": {
                        "role": Role.LOGIC,
                        "direction": Direction.OUT,
                        "trigger": Trigger.LEVEL,
                    },
                    "IN": {
                        "role": Role.LOGIC,
                        "direction": Direction.IN,
                        "trigger": Trigger.LEVEL,
                    },
                }
            ),
        },
        "settings": {
            "model": {
                "file": test_model,
            },
            "simulation": {"engine": spice_code, "temperature": QuantityData(ureg.Quantity(25, ureg.degC))},
            "units": {
                "time": Str("s"),
                "voltage": Str("V"),
                "current": Str("mA"),
                "resistance": Str("ohm"),
                "capacitance": Str("pF"),
                "power": Str("nW"),
                "energy": Str("J"),
            },
            "logic_thresholds": {
                "high": Float(0.8),
                "low": Float(0.2),
                "rise": Float(0.5),
                "fall": Float(0.5),
            },
            "named_nodes": {
                "power": {
                    "name": Str("VDD"),
                    "voltage": QuantityData(3 * ureg.volt),
                },
                "ground": {
                    "name": Str("VGND"),
                    "voltage": QuantityData(0 * ureg.volt),
                },
                "nwell": {
                    "name": Str("VNW"),
                    "voltage": QuantityData(3 * ureg.volt),
                },
                "pwell": {
                    "name": Str("VPW"),
                    "voltage": QuantityData(0 * ureg.volt),
                },
            },
        },
        "parameters": {
            "in_cap": {
                "frequency": {
                    "min": QuantityData(10 * ureg.Hz),
                    "max": QuantityData(1e9 * ureg.Hz),
                },
                "voltage": QuantityData(2 * ureg.volt),
                "resistance": {
                    "series": QuantityData(1e3 * ureg.ohm),
                    "shunt": QuantityData(1e10 * ureg.ohm),
                },
            },
        },
    }
    results = run(PinCapacitanceImpedanceDividerProcedure, **inputs)
