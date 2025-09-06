# BUG-001: OAuth Login Button Redirects to Non-Functional JSON Page

## Summary
The LOGIN button in the user interface redirects users to a page displaying JSON output instead of properly redirecting to Google OAuth authorization.

## Environment
- **Application**: User Interface (port 8000)
- **Environment**: Development
- **Date Reported**: 2025-09-05
- **Severity**: High (blocks authentication flow)

## Steps to Reproduce
1. Navigate to http://localhost:8000
2. Click the "LOGIN" button in the top-right panel controls
3. Observe the result

## Expected Behavior
- User should be redirected to Google OAuth authorization page
- User should be able to complete OAuth flow and return authenticated

## Actual Behavior
- Browser navigates to `/auth/oauth/login/google` endpoint
- Page displays JSON response in browser:
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=590582288440-r7u8hcvt1sk86vp8ic9ds7pq6ufd4369.apps.googleusercontent.com&redirect_uri=https%3A%2F%2Flocalhost%3A8000%2Fauth%2Fcallback&scope=openid+email+profile&response_type=code&state=2gssgK1ob-IRQrXAVAcDR1vL3vm35g1vT4eIKzEZdv4&access_type=offline&prompt=consent",
  "state": "included_in_url"
}
```

## Root Cause Analysis
The OAuth login endpoint (`/auth/oauth/login/google`) is returning a JSON response with the authorization URL instead of performing a proper HTTP redirect (302/307 status code).

## Technical Details
- **Endpoint**: `/auth/oauth/login/google`  
- **Current Response**: 200 OK with JSON body
- **Expected Response**: 302/307 Redirect to Google OAuth URL
- **Impact**: Breaks OAuth authentication flow completely

## Affected Components
- `src_common/oauth_endpoints.py` - OAuth login endpoint implementation
- User interface authentication flow
- Google OAuth integration

## Fix Required
The OAuth login endpoint should return an HTTP redirect response instead of JSON:

```python
# Current (broken):
return {"authorization_url": auth_url, "state": "included_in_url"}

# Should be (fixed):
from fastapi.responses import RedirectResponse
return RedirectResponse(url=auth_url, status_code=302)
```

## Priority
**High** - This completely blocks user authentication and login functionality.

## Related Files
- `templates/user/main.html` (line 175-177) - Login button JavaScript
- `src_common/oauth_endpoints.py` - OAuth endpoint implementation
- `src_common/oauth_service.py` - OAuth service layer

## Testing Notes
After fix, verify:
1. Login button properly redirects to Google OAuth
2. OAuth callback flow completes successfully  
3. User returns to application authenticated
4. JWT token is properly stored and verified