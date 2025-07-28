def calculate_tariff(vehicle_info):
    """
    Calculates the tariff based on the vehicle information.
    """
    base_tariff = 10.0  # Base tariff in INR

    # Adjust tariff based on vehicle type
    vehicle_type = vehicle_info.get('vehicle_type', 'N/A').lower()
    if 'truck' in vehicle_type:
        base_tariff *= 2.0
    elif 'bus' in vehicle_type:
        base_tariff *= 1.8
    elif 'car' in vehicle_type:
        base_tariff *= 1.2

    # Adjust tariff based on fuel type
    fuel_type = vehicle_info.get('fuel_type', 'N/A').lower()
    if 'electric' in fuel_type:
        base_tariff *= 0.8  # 20% discount for electric vehicles
    elif 'diesel' in fuel_type:
        base_tariff *= 1.1 # 10% surcharge for diesel vehicles

    return round(base_tariff, 2)
