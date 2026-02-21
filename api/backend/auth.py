SUPER_ADMIN_GROUPS = {'super admin'}

def require_super_admin(claims):
    raw = claims.get('cognito:groups', '')
    user_groups = set(g.strip() for g in raw.split(',')) if raw else set()
    if not user_groups & SUPER_ADMIN_GROUPS:
        raise PermissionError('Insufficient permissions')
    return user_groups

from app.auth import get_claims, require_admin, handle_error

def lambda_handler(event, context):
    try:
        claims = get_claims(event)
        require_admin(claims)  # admin + super admin only
        
        # ... rest of your existing code unchanged ...

    except Exception as err:
        return handle_error(err)
    
from app.auth import get_claims, require_super_admin, handle_error

def lambda_handler(event, context):
    try:
        claims = get_claims(event)
        require_super_admin(claims)  # super admin only

        # ... existing code ...

    except Exception as err:
        return handle_error(err)