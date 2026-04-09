import re
import os

def fix_checkboxes(filename):
    if not os.path.exists(filename):
        print(f"File {filename} not found.")
        return
    
    with open(filename, 'r') as f:
        content = f.read()
    
    # regex to find project-type-checkbox with name="project_type"
    updated_content = re.sub(
        r'(<input class="form-check-input project-type-checkbox" type="checkbox")\s+name="project_type"',
        r'\1',
        content
    )
    
    if content != updated_content:
        with open(filename, 'w') as f:
            f.write(updated_content)
        print(f"Updated {filename}")
    else:
        print(f"No changes needed for {filename}")

if __name__ == '__main__':
    fix_checkboxes('templates/quotations/create.html')
    fix_checkboxes('templates/quotations/edit.html')
