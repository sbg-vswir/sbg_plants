# utils/auth.py
import json
import os

ALLOWED_ADMIN_GROUPS = {'admins', 'superadmins'}

def get_claims(event):
    claims = (
        event.get('requestContext', {})
             .get('authorizer', {})
             .get('jwt', {})
             .get('claims')
    )
  
    if not claims:
        raise PermissionError('No auth claims found')
    return claims

def require_admin(claims):
    raw = claims.get('cognito:groups', '')
    # API Gateway passes groups as '[group1 group2 group3]' — strip brackets and split on spaces
    cleaned = raw.strip('[]')
    user_groups = set(g.strip() for g in cleaned.split()) if cleaned else set()
    if not user_groups & ALLOWED_ADMIN_GROUPS:
        raise PermissionError('Insufficient permissions')
    return user_groups

def respond(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': os.environ.get('FRONTEND_URL', '*'),
            'Access-Control-Allow-Headers': 'Authorization,Content-Type',
        },
        'body': json.dumps(body, default=str)  # default=str handles datetime serialization
    }

def handle_error(err):
    print(f'Error: {err}')
    if isinstance(err, PermissionError):
        return respond(403, {'message': str(err)})
    if isinstance(err, ValueError):
        return respond(400, {'message': str(err)})
    return respond(500, {'message': str(err)})