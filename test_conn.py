from db_utils import get_db_connection
print("Attempting to get connection...")
try:
    conn = get_db_connection()
    print(f"Connection result: {conn}")
except Exception as e:
    print(f"Connection failed with error: {e}")
