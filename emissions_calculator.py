
# emissions_calculator.py

def calculate_total_emissions(co2_per_unit: float, quantity: float) -> float:
    """
    Regner ut totale utslipp basert på CO2 per enhet og antall.
    """
    return co2_per_unit * quantity
