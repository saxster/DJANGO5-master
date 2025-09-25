# User Authentication with Email Verification - EARS Documentation

## Feature Overview

The user authentication system provides secure login for both mobile app and web interface with mandatory email verification for YOUTILITY5. It handles credential validation, user type checking (Mobile/Web/Both), email verification flow, session management, and role-based redirections.

## Scope

- User credential validation (mobile and web)
- Email verification process for ALL new/unverified users
- User type restrictions (Mobile, Web, Both) with access control
- Session creation and management for both platforms
- Role-based post-login redirections
- Device management and IMEI validation (mobile specific)
- Multi-device login prevention (mobile specific)

## Backend Flow Analysis

### Key Components

1. **Authentication Service** - `apps/peoples/services.py:8-63`
2. **SignIn View** - `apps/peoples/views.py:49-135`  
3. **Mobile Auth** - `apps/service/auth.py:45-109`
4. **Email Verification** - `apps/service/queries/bt_queries.py:send_email_verification_link`
5. **People Model** - `apps/peoples/models.py` (with `isverified` field)

### Technical Flow

**Universal Flow (Mobile & Web):**
```
1. User submits credentials → Credential validation
2. Check user exists in database → User type validation
3. Check userfor field matches platform (Mobile/Web/Both)
4. Check isverified=True (REQUIRED for all users)
5. If isverified=False → Return verification prompt
6. User clicks "Verify Me" → send_email_verification_link GraphQL call
7. System sends verification email → User clicks email link  
8. isverified flag set to True → User retries login
9. Authentication proceeds → Session creation → Role-based redirect
```

**Mobile-Specific Additional Checks:**
```
- Device ID validation and IMEI checking
- Multi-device login prevention
- Valid IP address restrictions (if configured)
```

## EARS Requirements

### Ubiquitous Requirements

**R1**: The system shall maintain a user authentication database with loginid, password, and isverified fields.

**R2**: The system shall support user types: Mobile, Web, and Both stored in people_extras.userfor field.

**R3**: The system shall log all authentication attempts for audit purposes.

**R4**: The system shall integrate with django_email_verification package for email verification functionality.

### Event-Driven Requirements

**R5**: When any user submits login credentials (mobile or web), the system shall validate the loginid exists in the database.

**R6**: When loginid validation succeeds, the system shall check if the user's userfor field matches the login platform (Mobile/Web/Both).

**R7**: When user type validation succeeds, the system shall verify the isverified flag is True.

**R8**: When isverified flag is False, the system shall return "user is not verified" message with verification option.

**R9**: When user clicks "Verify Me" button, the system shall call send_email_verification_link GraphQL query.

**R10**: When send_email_verification_link is called, the system shall validate clientcode and loginid exist in database.

**R11**: When validation succeeds, the system shall send verification email using django_email_verification.send_email().

**R12**: When user clicks verification link in email, the system shall set isverified flag to True.

**R13**: When verified user submits valid credentials, the system shall authenticate using Django's authenticate() method.

**R14**: When authentication succeeds, the system shall create user session with timezone offset.

**R15**: When session creation succeeds, the system shall redirect user based on their assigned site and role.

### State-Driven Requirements

**R16**: While user credentials are being validated, the system shall prevent duplicate login attempts from the same device.

**R17**: While user session is active, the system shall maintain user context including client, site, and role information.

**R18**: While user account has isverified=False, the system shall block login attempts regardless of correct credentials.

**R19**: While verification email is being sent, the system shall prevent duplicate verification email requests.

**R20**: While user session verification is pending, the system shall display appropriate UI state on mobile app.

### Complex Requirements

**R21**: While system is processing login, when loginid is not found, the system shall return "user Not Found" error.

**R22**: While user exists in database, when userfor field doesn't match login platform (e.g., "Web" only user on mobile), the system shall return platform-specific authorization error.

**R23**: While credentials are valid, when isverified=False (regardless of platform), the system shall return authentication failure with verification prompt.

**R24**: While user exists in database, when send_email_verification_link is called with valid clientcode and loginid, the system shall generate and send verification email.

**R25**: While authentication is being processed, when user.client.enable=True AND user.enable=True AND user.isverified=True, the system shall grant access and create session.

**R26**: While verification link is clicked, when link is valid and not expired, the system shall update user.isverified to True and redirect to success page.

**R27**: While session is being created, when timezone offset is provided, the system shall store it in session data for proper time handling.

**R28**: While user has valid session, when bu_id is 1 or None, the system shall redirect to no-site page.

**R29**: While user login is successful, when sitecode is in specific operational codes (SPSOPS, SPSHR, etc.), the system shall redirect to role-specific dashboards.

## Error Handling Requirements

**R30**: When verification email fails to send, the system shall return appropriate error message to mobile app.

**R31**: When verification link is expired or invalid, the system shall display error and offer to resend verification email.

**R32**: When user attempts to verify with invalid clientcode/loginid combination, the system shall return validation error.

**R33**: When authentication fails due to invalid credentials, the system shall log the attempt and return "Incorrect Username or Password" message.

**R34**: When user attempts login on multiple devices, the system shall return "Cannot login on multiple devices" error.

**R35**: When device is not registered in valid IMEI list, the system shall return "Device Not Registered" error.

## API/GraphQL Queries

### Authentication
- **Endpoint**: GraphQL `authenticate_user`
- **Location**: `apps/service/auth.py:91-109`
- **Input**: loginid, password, deviceid, clientcode
- **Output**: Authentication status, user context, error messages

### Email Verification
- **Endpoint**: GraphQL `send_email_verification_link`  
- **Location**: `apps/service/queries/bt_queries.py`
- **Input**: clientcode, loginid
- **Output**: BasicOutput with success/failure status

### Web Login
- **Endpoint**: POST `/peoples/signin/`
- **Location**: `apps/peoples/views.py:49-135`
- **Input**: username, password, timezone
- **Output**: Redirect to appropriate dashboard or error form

## Database Dependencies

### People Model
- **File**: `apps/peoples/models.py`
- **Key Fields**:
  - `loginid` - Username for authentication
  - `password` - Encrypted password
  - `isverified` - Email verification status
  - `enable` - Account active status
  - `deviceid` - Currently registered device
  - `client` - Associated client/organization
  - `bu` - Business unit/site assignment

### PeopleExtras JSON Field
- **userfor** - User type: "Mobile", "Web", or "Both"
- **validimei** - List of allowed device IMEIs
- **validip** - List of allowed IP addresses

## Session Management

### Session Data
- **ctzoffset** - Client timezone offset
- **bu_id** - Business unit ID
- **client_id** - Client organization ID  
- **sitecode** - Site-specific code for routing
- **wizard_data** - Onboarding wizard state

### Redirect Logic
- `bu_id` in [1, None] → `/people/no-site/`
- `sitecode` == "SPSOPS" → `reports:generateattendance`
- `sitecode` == "SPSHR" → `employee_creation:employee_creation`  
- `sitecode` == "SPSOPERATION" → `reports:generate_declaration_form`
- Default → `onboarding:rp_dashboard` or wizard completion

## Security Considerations

1. **Password encryption** using Django's built-in authentication
2. **Device validation** via IMEI checking
3. **IP restriction** support for additional security
4. **Multi-device prevention** to avoid concurrent sessions
5. **Email verification** to ensure valid email addresses
6. **Session timeout** and proper logout handling
7. **Audit logging** for all authentication attempts

## Test Scenarios

### Successful Login Flow
1. New user registers → isverified=False
2. Login attempt → Returns verification prompt
3. Click "Verify Me" → Email sent successfully  
4. Click email link → isverified=True
5. Login again → Authentication succeeds
6. Session created → Redirected to dashboard

### Error Scenarios
1. **Invalid credentials** → Error message displayed
2. **Unverified user** → Verification prompt shown
3. **Web-only user on mobile** → Access denied
4. **Multiple device login** → Device conflict error
5. **Unregistered device** → IMEI validation failure
6. **No site assignment** → No-site page redirect

## Related Features

- **User Registration** - Initial account creation
- **Password Reset** - Credential recovery flow
- **Session Management** - Active session handling  
- **Role-Based Access** - Permission management
- **Device Management** - IMEI and device tracking

---

**Technical References**:
- Authentication Service: `apps/peoples/services.py:8-63`
- Mobile Auth Handler: `apps/service/auth.py:45-109`  
- Email Verification: `apps/service/queries/bt_queries.py:send_email_verification_link`
- People Model: `apps/peoples/models.py:isverified`
- SignIn View: `apps/peoples/views.py:49-135`