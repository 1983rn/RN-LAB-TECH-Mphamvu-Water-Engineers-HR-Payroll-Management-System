import sqlite3

def dump_lulanga_items():
    try:
        conn = sqlite3.connect('instance/system.db')
        cursor = conn.cursor()
        
        # Check items for quotation ID 1
        cursor.execute("SELECT id, project_type, unit, quantity, unit_rate, total FROM quotation_items WHERE quotation_id = 1 ORDER BY id")
        items = cursor.fetchall()
        
        with open('tmp/lulanga_items.txt', 'w') as f:
            for iid, ptype, unit, qty, rate, itotal in items:
                f.write(f"ID: {iid}, Type: {ptype}, Unit: {unit}, Qty: {qty}, Rate: {rate}, Total: {itotal}\n")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    dump_lulanga_items()
