import sys
sys.path.append('.')
from utils import calculate_expert_fare

def test_fare(dist, dur, name, is_rush=False):
    # Mocking datetime to force rush hour if needed
    # (Actually calculate_expert_fare uses datetime.now(), so we just print current state)
    meter, fares, rush, hell, tip = calculate_expert_fare(dist, dur, origin_txt="Noble Revolve 1", dest_txt="Khaosan Road")
    print(f"--- Test: {name} ({dist}km, {dur}min) ---")
    print(f"Rush Hour: {rush}, Hell Zone: {hell}")
    print(f"Base Meter: {meter} THB")
    print(f"Grab: {fares['grab_taxi']['price']} THB")
    print(f"Bolt: {fares['bolt']['price']} THB")
    print("-" * 30)

# Noble Revolve 1 -> Khaosan (approx 10km, 40min)
test_fare(10, 40, "Noble-Khaosan (Traffic)")
# Short distance (3km, 10min)
test_fare(3, 10, "Short Trip")
