from flask import session

def apply_dept_filter(query, model):
    """
    Applies a department filter to a query based on the active session context
    and user permissions.
    """
    role = session.get('role')
    dept_context = session.get('department_context')
    
    # 1. If we are explicitly in a department (e.g., Construction Dashboard)
    if dept_context:
        # In Inventory model, we may need to check 'category' if 'department' isn't used
        # but my migration script added 'department' to Inventory.
        return query.filter(model.department == dept_context)
    
    # 2. If we are in a global module (e.g., global Client Directory)
    # Check if the user has global oversight permissions
    if role in ['Administrator', 'Director', 'HR Manager', 'Accountant']:
        return query # No filter applied, they see everything
    
    # 3. Default fallback for restricted users without a department context
    # They should only see Borehole Drilling or nothing.
    return query.filter(model.department == 'Borehole Drilling')

def get_current_dept():
    """
    Returns the current active department context, defaulting to Borehole Drilling.
    """
    return session.get('department_context', 'Borehole Drilling')
