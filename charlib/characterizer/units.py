from pint import UnitRegistry


class UnitsSettings:
    def __init__(self, **kwargs) -> None:
        ureg = UnitRegistry()
        self.time = ureg.parse_units(kwargs.get("time", "ns"))
        self.voltage = ureg.parse_units(kwargs.get("voltage", "V"))
        self.current = ureg.parse_units(kwargs.get("current", "uA"))
        self.resistance = ureg.parse_units(kwargs.get("pulling_resistance", "Ω"))
        self.capacitance = ureg.parse_units(kwargs.get("capacitive_load", "pF"))
        self.power = ureg.parse_units(kwargs.get("leakage_power", "nW"))
        self.energy = ureg.parse_units(kwargs.get("energy", "fJ"))
