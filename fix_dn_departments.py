import sqlite3
import os

def fix_departments():
    db_path = 'instance/system.db'
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Checking for mismatched departments...")
        
        # Select DNs where their department doesn't match the linked Quotation's department
        query = """
        SELECT dn.delivery_id, q.department 
        FROM delivery_notes dn
        JOIN quotations q ON dn.quotation_id = q.quotation_id
        WHERE dn.department != q.department
        """
        cursor.execute(query)
        mismatches = cursor.fetchall()
        
        if not mismatches:
            print("No department mismatches found.")
        else:
            print(f"Found {len(mismatches)} mismatched delivery notes. Fixing...")
            for dn_id, correct_dept in mismatches:
                cursor.execute(
                    "UPDATE delivery_notes SET department = ? WHERE delivery_id = ?",
                    (correct_dept, dn_id)
                )
                print(f"Updated Delivery Note ID {dn_id} to department '{correct_dept}'")
            
            conn.commit()
            print("Successfully synchronized delivery note departments.")

    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_departments()
