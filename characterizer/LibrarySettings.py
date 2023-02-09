from pathlib import Path
from shutil import which
from characterizer.UnitsSettings import UnitsSettings

class NamedNode:
    def __init__(self, name, voltage = 0):
        self._name = name
        self._voltage = voltage

    def __str__(self) -> str:
        return f'name = {self.name}, voltage = {self.voltage}' # TODO Make this a bit nicer

    def __repr__(self) -> str:
        return f'NamedNode({self.name}, {self.voltage})'

    @property
    def name(self) -> str:
        return self._name
    
    @name.setter
    def name(self, name: str):
        self._name = name

    @property
    def voltage(self) -> float:
        return self._voltage
    
    @voltage.setter
    def voltage(self, voltage: float):
        self._voltage = voltage

    def normalized_voltage(self, units_settings: UnitsSettings) -> float:
        """Returns the voltage after converting from global units to V"""
        return self.voltage * units_settings.voltage.magnitude


def str_to_bool(value: str) -> bool:
    if value.lower() in ['true', 't', '1']:
        return True
    elif value.lower() in ['false', 'f', '0']:
        return False
    else:
        raise ValueError(f'Unable to convert "{value}" to bool.')


class LibrarySettings:
    def __init__(self):
        # Key Library settings
        self._lib_name = "unnamed_lib"
        self._dotlib_name = None
        self._verilog_name = None
        self._cell_name_suffix = ""
        self._cell_name_prefix = ""
        self.units = UnitsSettings()

        # Simulator Settings
        self._simulator = Path(which('ngspice'))
        self._work_dir = Path('work')
        self.vdd = NamedNode('VDD')
        self.vss = NamedNode('VSS')
        self.pwell = NamedNode('VPW')
        self.nwell = NamedNode('VNW')
        self._process = None
        self._temperature = 25
        self._logic_threshold_low = 0.2
        self._logic_threshold_high = 0.8
        self._logic_high_to_low_threshold = 0.5
        self._logic_low_to_high_threshold = 0.5
        self._energy_meas_low_threshold = 0.01
        self._energy_meas_high_threshold = 0.99
        self._energy_meas_time_extent = 10
        self._operating_conditions = None
        self._delay_model = "table_lookup"

        # Behavioral settings
        self._run_sim = True
        self._use_multithreaded = True
        self._is_exported = False # whether the library settings have been exported
        self._suppress_msg = False
        self._suppress_sim_msg = False
        self._suppress_debug_msg = False

    def __str__(self) -> str:
        lines = []
        lines.append(f'Library name:         {self.lib_name}')
        lines.append(f'.lib name:            {self.dotlib_name}')
        lines.append(f'.v name:              {self.verilog_name}')
        lines.append(f'Cell suffix:          {self.cell_name_suffix}')
        lines.append(f'Cell prefix:          {self.cell_name_prefix}')
        lines.append(f'Units: ')
        for line in str(self.units).split('\n'):
            lines.append(f'    {line}')
        lines.append(f'Simulator:            {str(self.simulator)}')
        lines.append(f'Work directory:       {str(self.work_dir)}')
        lines.append(f'Process:              {self.process}')
        lines.append(f'Temperature:          {str(self.temperature)}')
        lines.append(f'vdd:                  {str(self.vdd)} {str(self.units.voltage)}')
        lines.append(f'vss:                  {str(self.vss)} {str(self.units.voltage)}')
        lines.append(f'pwell:                {str(self.pwell)} {str(self.units.voltage)}')
        lines.append(f'nwell:                {str(self.nwell)} {str(self.units.voltage)}')
        lines.append(f'Logic Thresholds:')
        lines.append(f'    Low:              {str(self.logic_threshold_low_voltage())} {str(self.units.voltage)}')
        lines.append(f'    High:             {str(self.logic_threshold_high_voltage())} {str(self.units.voltage)}')
        lines.append(f'    High to Low:      {str(self.logic_high_to_low_threshold_voltage())} {str(self.units.voltage)}')
        lines.append(f'    Low to High:      {str(self.logic_low_to_high_threshold_voltage())} {str(self.units.voltage)}')
        lines.append(f'Energy Measurement Thresholds:')
        lines.append(f'    Low:              {str(self.energy_meas_low_threshold_voltage())} {str(self.units.voltage)}')
        lines.append(f'    High:             {str(self.energy_meas_high_threshold_voltage())} {str(self.units.voltage)}')
        lines.append(f'Operating conditions: {self.operating_conditions}')
        lines.append(f'Delay model:          {self.delay_model}')
        return '\n'.join(lines)

    @property
    def work_dir(self) -> Path:
        return self._work_dir

    @work_dir.setter
    def work_dir(self, value):
        if value is not None:
            if isinstance(value, Path):
                self._work_dir = value 
            elif isinstance(value, str):
                self._work_dir = Path(value)
            else:
                raise TypeError(f'Invalid type for work_dir: {type(value)}')
        else:
            raise ValueError(f'Invalid value for work_dir: {value}')

    @property
    def simulator(self) -> Path:
        return self._simulator

    @simulator.setter
    def simulator(self, value):
        if value is not None:
            if isinstance(value, Path):
                if not value.is_file():
                    raise ValueError(f'Invalid value for simulator: {value} is not a file')
                self._simulator = value
            elif isinstance(value, str):
                if not Path(value).is_file():
                    raise ValueError(f'Invalid value for simulator: {value} is not a file')
                self._simulator = Path(value)
            else:
                raise TypeError(f'Invalid type for simulator: {type(value)}')
        else:
            raise ValueError(f'Invalid value for simulator: {value}')

    @property
    def lib_name(self) -> str:
        return self._lib_name

    @lib_name.setter
    def lib_name(self, value: str):
        if value is not None and len(value) > 0:
            self._lib_name = value
        else:
            raise ValueError(f'Invalid value for lib_name: {value}')

    @property
    def dotlib_name(self) -> str:
        if self._dotlib_name is None:
            return self.lib_name + '.lib'
        else:
            return self._dotlib_name

    @dotlib_name.setter
    def dotlib_name(self, value: str):
        if value is not None and len(value) > 0:
            self._dotlib_name = value
        else:
            raise ValueError(f'Invalid value for dotlib_name: {value}')

    @property
    def verilog_name(self) -> str:
        if self._verilog_name is None:
            return self.lib_name + '.v'
        else:
            return self._verilog_name

    @verilog_name.setter
    def verilog_name(self, value: str):
        if value is not None and len(value) > 0:
            self._verilog_name = value
        else:
            raise ValueError(f'Invalid value for verilog_name: {value}')

    @property
    def cell_name_suffix(self) -> str:
        return self._cell_name_suffix

    @cell_name_suffix.setter
    def cell_name_suffix(self, value: str):
        if value is not None and len(value) > 0:
            self._cell_name_suffix = value
        else:
            raise ValueError(f'Invalid value for cell_name_suffix: {value}')

    @property
    def cell_name_prefix(self) -> str:
        return self._cell_name_prefix

    @cell_name_prefix.setter
    def cell_name_prefix(self, value: str):
        if value is not None and len(value) > 0:
            self._cell_name_prefix = value
        else:
            raise ValueError(f'Invalid value for cell_name_suffix: {value}')

    @property
    def process(self) -> str:
        return self._process

    @process.setter
    def process(self, value: str):
        if value is not None and len(value) > 0:
            self._process = value
        else:
            raise ValueError(f'Invalid value for process: {value}')

    @property
    def temperature(self) -> float:
        return self._temperature

    @temperature.setter
    def temperature(self, value: float):
        if value is not None:
            self._temperature = value
        else:
            raise ValueError(f'Invalid value for temperature: {value}')

    @property
    def logic_threshold_high(self) -> float:
        return self._logic_threshold_high

    @logic_threshold_high.setter
    def logic_threshold_high(self, value: float):
        if value is not None and 0 < value < 1:
            self._logic_threshold_high = value
        else:
            raise ValueError(f'Invalid value for logic_threshold_high: {value}')

    def logic_threshold_high_voltage(self) -> float:
        return self.logic_threshold_high * self.vdd.normalized_voltage(self.units)

    @property
    def logic_threshold_low(self) -> float:
        return self._logic_threshold_low

    @logic_threshold_low.setter
    def logic_threshold_low(self, value: float):
        if value is not None and 0 < value < 1:
            self._logic_threshold_low = value
        else:
            raise ValueError(f'Invalid value for logic_threshold_high: {value}')

    def logic_threshold_low_voltage(self) -> float:
        return self.logic_threshold_low * self.vdd.normalized_voltage(self.units)

    @property
    def logic_high_to_low_threshold(self) -> float:
        return self._logic_high_to_low_threshold

    @logic_high_to_low_threshold.setter
    def logic_high_to_low_threshold(self, value: float):
        if value is not None and 0 < value < 1:
            self._logic_high_to_low_threshold = value
        else:
            raise ValueError(f'Invalid value for logic_high_to_low_threshold: {value}')

    def logic_high_to_low_threshold_voltage(self) -> float:
        return self.logic_high_to_low_threshold * self.vdd.normalized_voltage(self.units)

    @property
    def logic_low_to_high_threshold(self) -> float:
        return self._logic_low_to_high_threshold

    @logic_low_to_high_threshold.setter
    def logic_low_to_high_threshold(self, value: float):
        if value is not None and 0 < value < 1:
            self._logic_low_to_high_threshold = value
        else:
            raise ValueError(f'Invalid value for logic_low_to_high_threshold: {value}')

    def logic_low_to_high_threshold_voltage(self) -> float:
        return self.logic_low_to_high_threshold * self.vdd.normalized_voltage(self.units)

    @property
    def energy_meas_low_threshold(self) -> float:
        return self._energy_meas_low_threshold

    @energy_meas_low_threshold.setter
    def energy_meas_low_threshold(self, value: float):
        if value is not None and 0 < value < 1:
            self._energy_meas_low_threshold = value
        else:
            raise ValueError(f'Invalid value for energy_meas_low_threshold: {value}')

    def energy_meas_low_threshold_voltage(self) -> float:
        return self.energy_meas_low_threshold * self.vdd.normalized_voltage(self.units)

    @property
    def energy_meas_high_threshold(self) -> float:
        return self._energy_meas_high_threshold
    
    @energy_meas_high_threshold.setter
    def energy_meas_high_threshold(self, value: float):
        if value is not None and 0 < value < 1:
            self._energy_meas_high_threshold = value
        else:
            raise ValueError(f'Invalid value for energy_meas_high_threshold: {value}')

    def energy_meas_high_threshold_voltage(self) -> float:
        return self.energy_meas_high_threshold * self.vdd.normalized_voltage(self.units)

    @property
    def energy_meas_time_extent(self) -> float:
        return self._energy_meas_time_extent

    @energy_meas_time_extent.setter
    def energy_meas_time_extent(self, value: float):
        if value is not None and value > 0:
            self._energy_meas_time_extent = value
        else:
            raise ValueError(f'Invalid value for energy_meas_time_extent: {value}')

    @property
    def operating_conditions(self) -> str:
        return self._operating_conditions

    @operating_conditions.setter
    def operating_conditions(self, value: str):
        if value is not None and len(value) > 0:
            self._operating_conditions = value
        else:
            raise ValueError(f'Invalid value for operating_conditions: {value}')

    @property
    def delay_model(self) -> str:
        return self._delay_model
    
    @delay_model.setter
    def delay_model(self, value: str):
        if value is not None and len(value) > 0:
            self._delay_model = value
        else:
            raise ValueError(f'Invalid value for delay_model: {value}')

    @property
    def run_sim(self) -> bool:
        return self._run_sim

    @run_sim.setter
    def run_sim(self, value):
        if value is not None:
            if isinstance(value, str):
                self._run_sim = str_to_bool(value)
            elif isinstance(value, bool):
                self._run_sim = value
            else:
                raise TypeError(f'Invalid type for run_sim: {type(value)}')
        else:
            raise ValueError(f'Invalid value for run_sim: {value}')

    @property
    def mt_sim(self) -> bool:
        return self._use_multithreaded

    @mt_sim.setter
    def mt_sim(self, value):
        if value is not None:
            if isinstance(value, str):
                self._use_multithreaded = str_to_bool(value)
            elif isinstance(value, bool):
                self._use_multithreaded = value
            else:
                raise TypeError(f'Invalid type for mt_sim: {type(value)}')
        else:
            raise ValueError(f'Invalid value for mt_sim: {value}')
    
    @property
    def is_exported(self) -> bool:
        return self._is_exported

    def set_exported(self):
        self._is_exported = True

    @property
    def suppress_message(self) -> bool:
        return self._suppress_msg
    
    @suppress_message.setter
    def suppress_message(self, value: str):
        self._suppress_msg = str_to_bool(value)

    @property
    def suppress_sim_message(self) -> bool:
        return self._suppress_sim_msg

    @suppress_sim_message.setter
    def suppress_sim_message(self, value: str):
        self._suppress_sim_msg = str_to_bool(value)
    
    @property
    def suppress_debug_message(self) -> bool:
        return self._suppress_debug_msg

    @suppress_debug_message.setter
    def suppress_debug_message(self, value: str):
        self._suppress_debug_msg = str_to_bool(value)