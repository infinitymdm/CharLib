from charlib.config.syntax import ConfigFile


def make_config(**cell_settings):
    cell = {
        "netlist": "dff.sp",
        "models": [],
        "functions": ["Q <= D"],
        "data_slews": [0.1],
    }
    cell.update(cell_settings)
    return ConfigFile.validate({"cells": {"DFF": cell}})


def test_metastability_constraint_growth_threshold_default():
    config = make_config()

    assert config["cells"]["DFF"]["metastability_constraint_growth_threshold"] == 0.2


def test_metastability_constraint_growth_threshold_override():
    config = make_config(metastability_constraint_growth_threshold=0.35)

    assert config["cells"]["DFF"]["metastability_constraint_growth_threshold"] == 0.35
