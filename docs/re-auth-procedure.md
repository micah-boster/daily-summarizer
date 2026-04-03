# Google OAuth Re-Authentication Procedure

## When This Is Needed

Re-authentication is required when:

- **Slack notification says "OAuth credentials unavailable or refresh failed"** -- the automated pipeline could not refresh the token and needs manual intervention.
- **Pipeline logs show `google.auth.exceptions.RefreshError`** -- the refresh token has been revoked or expired.
- **More than 7 days since last auth** -- if the Google Cloud app is still in "Testing" publishing status, refresh tokens expire after 7 days. Push the app to "In production" status (no review needed for <100 users) to avoid this.
- **Scopes changed** -- if you added new API scopes to the OAuth consent screen, existing tokens won't have the new scopes. Re-auth is required.

## Steps

1. **Delete the expired token:**
   ```bash
   rm .credentials/token.json
   ```

2. **Run the auth script:**
   ```bash
   cd "/Users/micah/Desktop/CODE/DAILY SUMMARIZER"
   uv run python -m src.auth.google_oauth
   ```

3. **Browser opens** -- sign in with the Google account that has Calendar and Gmail access.

4. **Grant permissions** -- approve Calendar (read-only) and Gmail (read-only) scopes.

5. **Verify the new token works:**
   ```bash
   uv run python -c "from src.auth.google_oauth import load_credentials; c = load_credentials(); print(f'Valid: {c is not None}, Expiry: {c.expiry if c else \"N/A\"}')"
   ```
   Expected output: `Valid: True, Expiry: <some future datetime>`

6. **Confirm refresh token exists:**
   ```bash
   uv run python -c "import json; t = json.load(open('.credentials/token.json')); print('refresh_token present:', 'refresh_token' in t)"
   ```
   Expected output: `refresh_token present: True`

## How to Check Current Token Status

Run this at any time to see if credentials are valid:

```bash
cd "/Users/micah/Desktop/CODE/DAILY SUMMARIZER"
uv run python -c "from src.auth.google_oauth import load_credentials; c = load_credentials(); print(f'Valid: {c is not None}, Expiry: {c.expiry if c else \"N/A\"}')"
```

## Troubleshooting

### No refresh_token in token.json after re-auth

**Cause:** Google only returns a refresh token on the first authorization unless `prompt='consent'` is used. The auth module (`src/auth/google_oauth.py`) already passes `prompt='consent'` and `access_type='offline'`, but if you used a different method to authenticate, this can happen.

**Fix:**
1. Delete the token: `rm .credentials/token.json`
2. Re-run auth: `uv run python -m src.auth.google_oauth`
3. The module forces `prompt='consent'` which ensures a refresh token is returned.

### "Access blocked" error in browser

**Cause:** Your Google account is not listed as a test user for the OAuth consent screen.

**Fix:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/) > APIs & Services > OAuth consent screen
2. Under "Test users", add your Google email address
3. Retry the auth flow

### 403 "Insufficient Permission" on API call

**Cause:** The OAuth token was granted with different scopes than what the code requests.

**Fix:**
1. Check the scopes in Google Cloud Console > OAuth consent screen -- both `calendar.readonly` and `gmail.readonly` should be listed
2. Delete the token: `rm .credentials/token.json`
3. Re-run auth to get a token with the correct scopes: `uv run python -m src.auth.google_oauth`

### RefreshError after exactly 7 days

**Cause:** The Google Cloud app is in "Testing" publishing status, which limits refresh token lifetime to 7 days.

**Fix (permanent):**
1. Go to [Google Cloud Console](https://console.cloud.google.com/) > APIs & Services > OAuth consent screen
2. Click "Publish App" to move from Testing to In Production
3. For personal-use apps with fewer than 100 users, no Google verification review is required
4. Re-auth once after publishing: delete token.json and run `uv run python -m src.auth.google_oauth`

This eliminates the 7-day expiry. Refresh tokens for "In production" apps expire after 6 months of inactivity, and daily pipeline usage keeps them active.
