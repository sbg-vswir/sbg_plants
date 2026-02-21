# admin_users.py
import boto3
import json
import os
from app.auth import get_claims, require_admin, respond, handle_error

cognito = boto3.client('cognito-idp', region_name=os.environ['AWS_REGION'])
POOL_ID = os.environ['COGNITO_USER_POOL_ID']

def handler(event, context):
    try:
        claims = get_claims(event)
        require_admin(claims)

        # HTTP API v2 uses requestContext.http.method instead of httpMethod
        method = event.get('requestContext', {}).get('http', {}).get('method')
        path_params = event.get('pathParameters') or {}
        username = path_params.get('username')
        group = path_params.get('group')
        body = json.loads(event.get('body') or '{}')

        if method == 'GET' and not username:
            return list_users()
        if method == 'POST' and not username:
            return create_user(body)
        if method == 'DELETE' and username and not group:
            return delete_user(username)
        if method == 'POST' and username and not group:
            return add_to_group(username, body)
        if method == 'DELETE' and username and group:
            return remove_from_group(username, group)

        return respond(404, {'message': 'Route not found'})

    except Exception as err:
        return handle_error(err)


def list_users():
    response = cognito.list_users(UserPoolId=POOL_ID, Limit=60)
    users = []

    for user in response.get('Users', []):
        username = user['Username']
        groups_response = cognito.admin_list_groups_for_user(
            UserPoolId=POOL_ID,
            Username=username
        )
        attrs = {a['Name']: a['Value'] for a in user.get('Attributes', [])}
        users.append({
            'username': username,
            'email': attrs.get('email', ''),
            'status': user.get('UserStatus'),
            'enabled': user.get('Enabled'),
            'createdAt': user.get('UserCreateDate'),
            'groups': [g['GroupName'] for g in groups_response.get('Groups', [])]
        })

    return respond(200, users)


def create_user(body):
    username = body.get('username')
    email = body.get('email')
    temporary_password = body.get('temporaryPassword')
    groups = body.get('groups', [])

    if not all([username, email, temporary_password]):
        raise ValueError('username, email, and temporaryPassword are required')

    cognito.admin_create_user(
        UserPoolId=POOL_ID,
        Username=username,
        TemporaryPassword=temporary_password,
        MessageAction='SUPPRESS',
        UserAttributes=[
            {'Name': 'email', 'Value': email},
            {'Name': 'email_verified', 'Value': 'true'},
        ]
    )

    for group in groups:
        cognito.admin_add_user_to_group(
            UserPoolId=POOL_ID,
            Username=username,
            GroupName=group
        )

    return respond(201, {'success': True})


def delete_user(username):
    cognito.admin_delete_user(
        UserPoolId=POOL_ID,
        Username=username
    )
    return respond(200, {'success': True})


def add_to_group(username, body):
    group = body.get('group')
    if not group:
        raise ValueError('group is required')

    cognito.admin_add_user_to_group(
        UserPoolId=POOL_ID,
        Username=username,
        GroupName=group
    )
    return respond(200, {'success': True})


def remove_from_group(username, group):
    cognito.admin_remove_user_from_group(
        UserPoolId=POOL_ID,
        Username=username,
        GroupName=group
    )
    return respond(200, {'success': True})