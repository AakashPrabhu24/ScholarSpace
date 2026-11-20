"""
Google OAuth 2.0 (Authorization Code) for sign-up / sign-in.

Paste this exact URL in Google Cloud Console → OAuth client → Authorized redirect URIs
(local dev, default Django port):

    http://127.0.0.1:8000/oauth/google/callback/

Also add if you open the site as localhost:

    http://localhost:8000/oauth/google/callback/

Production (HTTPS, your domain):

    https://YOUR_DOMAIN/oauth/google/callback/

Set environment variables GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET
(or define them in settings.py for local testing only).
"""
import secrets
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.shortcuts import redirect
from django.urls import reverse

User = get_user_model()

GOOGLE_AUTH_ENDPOINT = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_ENDPOINT = 'https://www.googleapis.com/oauth2/v3/userinfo'


def google_oauth_start(request):
    client_id = (getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', None) or '').strip()
    if not client_id:
        messages.error(
            request,
            'Google sign-in is not configured. Save your Google JSON as google_oauth_client_secret.json '
            'next to manage.py, or set GOOGLE_OAUTH_CLIENT_SECRETS_FILE / GOOGLE_OAUTH_CLIENT_ID.',
        )
        if request.GET.get('return_to', '').strip().lower() == 'login':
            return redirect('login')
        return redirect('register')

    state = secrets.token_urlsafe(32)
    request.session['google_oauth_state'] = state
    redirect_uri = request.build_absolute_uri(reverse('google_oauth_callback'))
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'online',
        'prompt': 'select_account',
    }
    return redirect(f'{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}')


def google_oauth_callback(request):
    if request.GET.get('error'):
        messages.error(request, 'Google sign-in was cancelled or failed.')
        return redirect('login')

    if request.session.get('google_oauth_state') != request.GET.get('state'):
        messages.error(request, 'Invalid sign-in session. Please try again.')
        return redirect('register')
    request.session.pop('google_oauth_state', None)

    code = request.GET.get('code')
    if not code:
        messages.error(request, 'Missing authorization code.')
        return redirect('register')

    redirect_uri = request.build_absolute_uri(reverse('google_oauth_callback'))
    token_resp = requests.post(
        GOOGLE_TOKEN_ENDPOINT,
        data={
            'code': code,
            'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
            'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        },
        headers={'Accept': 'application/json'},
        timeout=30,
    )
    if not token_resp.ok:
        messages.error(request, 'Could not verify Google sign-in.')
        return redirect('register')

    access_token = token_resp.json().get('access_token')
    if not access_token:
        messages.error(request, 'Invalid response from Google.')
        return redirect('register')

    userinfo_resp = requests.get(
        GOOGLE_USERINFO_ENDPOINT,
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=30,
    )
    if not userinfo_resp.ok:
        messages.error(request, 'Could not load your Google profile.')
        return redirect('register')

    info = userinfo_resp.json()
    email = (info.get('email') or '').strip().lower()
    if not email:
        messages.error(request, 'Google did not provide an email address.')
        return redirect('register')

    if not info.get('email_verified', True):
        messages.error(request, 'Please use a verified Google email address.')
        return redirect('register')

    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        local = email.split('@')[0].replace('.', '_').replace('+', '_')
        local = ''.join(c for c in local if c.isalnum() or c == '_') or 'user'
        username = local[:30]
        base = username
        n = 0
        while User.objects.filter(username=username).exists():
            n += 1
            username = f'{base}_{n}'[:150]

        user = User.objects.create_user(username=username, email=email)
        user.set_unusable_password()
        user.save()

    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    messages.success(request, f'Signed in as {user.get_username()}.')
    return redirect(settings.LOGIN_REDIRECT_URL)
