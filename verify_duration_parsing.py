
import re

def parse_trip_duration(duration_str):
    if "당일" in duration_str or "Day Trip" in duration_str:
        return 1
    match = re.search(r'(\d+)\s*일', duration_str)
    if match:
        return int(match.group(1))
    match_en = re.search(r'(\d+)\s*Days', duration_str, re.IGNORECASE)
    if match_en:
        return int(match_en.group(1))
    if "1주일" in duration_str or "1 Week" in duration_str:
        return 7
    if "장기" in duration_str or "Long-term" in duration_str:
        return 14
    return 3

test_cases = [
    ("당일치기 (Day Trip)", 1),
    ("1박 2일 (1 Night 2 Days)", 2),
    ("2박 3일 (2 Nights 3 Days)", 3),
    ("3박 4일 (3 Nights 4 Days)", 4),
    ("1주일 이상 (1 Week+)", 7),
    ("장기 여행 (Long-term)", 14),
]

for s, expected in test_cases:
    result = parse_trip_duration(s)
    print(f"Input: {s} -> Result: {result} (Expected: {expected})")
    assert result == expected

print("All test cases passed!")
