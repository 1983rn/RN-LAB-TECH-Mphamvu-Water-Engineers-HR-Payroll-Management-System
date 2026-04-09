import sqlite3

def find_lulanga_and_quotations():
    try:
        conn = sqlite3.connect('instance/system.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT client_id, client_name FROM clients WHERE client_name LIKE '%Lulanga%'")
        clients = cursor.fetchall()
        
        with open('tmp/lulanga_debug.txt', 'w') as f:
            f.write(f"Clients matching Lulanga: {clients}\n")
            
            for cid, name in clients:
                f.write(f"\nQuotations for {name} (ID: {cid}):\n")
                cursor.execute("SELECT quotation_id, reference_number FROM quotations WHERE client_id = ?", (cid,))
                quotations = cursor.fetchall()
                for qid, ref in quotations:
                    f.write(f"  Quotation ID: {qid}, Ref: {ref}\n")
                    cursor.execute("SELECT id, project_type, unit, quantity, unit_rate, total FROM quotation_items WHERE quotation_id = ? ORDER BY id", (qid,))
                    items = cursor.fetchall()
                    for iid, ptype, unit, qty, rate, itotal in items:
                        f.write(f"    - ID: {iid}, Type: {ptype}, Unit: {unit}, Qty: {qty}, Rate: {rate}, Total: {itotal}\n")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    find_lulanga_and_quotations()
