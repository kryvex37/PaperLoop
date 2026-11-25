from decimal import Decimal

# Environmental savings coefficients per 1,000 kg (1 metric ton) of recycled paper:
# Standard EPA / Environmental Paper Network benchmarks:
# - Trees saved: ~17 trees per ton (0.017 trees per kg)
# - Water saved: ~26,000 liters per ton (26.0 liters per kg)
# - Energy saved: ~4,000 kWh per ton (4.0 kWh per kg)
# - CO2 emissions avoided: ~1,500 kg CO2 equivalent per ton (1.5 kg CO2e per kg)
# - Landfill space conserved: ~3.0 cubic meters per ton (0.003 m³ per kg)

TREES_SAVED_PER_KG = Decimal("0.017")
WATER_LITERS_PER_KG = Decimal("26.0")
ENERGY_KWH_PER_KG = Decimal("4.0")
CO2_AVOIDED_KG_PER_KG = Decimal("1.5")
LANDFILL_M3_PER_KG = Decimal("0.003")


def calculate_impact_metrics(quantity_kg):
    """
    Compute environmental impact summary for a given paper weight in kg.
    """
    if not quantity_kg:
        weight = Decimal("0")
    elif not isinstance(quantity_kg, Decimal):
        weight = Decimal(str(quantity_kg))
    else:
        weight = quantity_kg

    if weight < 0:
        weight = Decimal("0")

    return {
        "quantity_kg": weight,
        "trees_saved": round(weight * TREES_SAVED_PER_KG, 2),
        "water_liters_saved": round(weight * WATER_LITERS_PER_KG, 1),
        "energy_kwh_saved": round(weight * ENERGY_KWH_PER_KG, 1),
        "co2_avoided_kg": round(weight * CO2_AVOIDED_KG_PER_KG, 1),
        "landfill_m3_saved": round(weight * LANDFILL_M3_PER_KG, 3),
    }
