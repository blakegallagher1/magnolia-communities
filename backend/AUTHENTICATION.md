# Authentication & Authorization Guide

## Overview

The GallagherMHP platform implements JWT (JSON Web Token) based authentication with role-based access control (RBAC).

## User Roles

Three roles are defined:

- **Admin** (`admin`): Full system access, can manage users
- **Analyst** (`analyst`): Can create/edit deals, parcels, financial models
- **Read-Only** (`read_only`): View-only access to data

## Authentication Flow

### 1. Login

```bash
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "secure_password"
}
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### 2. Use Access Token

Include the access token in the `Authorization` header:

```bash
GET /api/v1/crm/deals
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

### 3. Refresh Token

When the access token expires (30 minutes), use the refresh token to obtain new tokens:

```bash
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

## Protecting Endpoints

### Basic Authentication

To require authentication on any endpoint, add the `get_current_user` dependency:

```python
from fastapi import Depends
from app.core.security import get_current_user

@router.get("/protected")
async def protected_endpoint(
    current_user: dict = Depends(get_current_user)
):
    # current_user contains: {"username": "...", "role": "..."}
    return {"message": f"Hello {current_user['username']}"}
```

### Role-Based Access Control

To restrict access by role, use the `require_role` dependency factory:

```python
from fastapi import Depends
from app.core.security import require_role, UserRole

# Admin only
@router.post("/admin/users")
async def create_user(
    user_data: UserCreate,
    current_user: dict = Depends(require_role(UserRole.ADMIN))
):
    # Only admins can reach this code
    ...

# Admin or Analyst
@router.post("/deals")
async def create_deal(
    deal_data: DealCreate,
    current_user: dict = Depends(require_role(UserRole.ADMIN, UserRole.ANALYST))
):
    # Admins and Analysts can create deals
    ...

# Any authenticated user (read-only included)
@router.get("/deals")
async def list_deals(
    current_user: dict = Depends(require_role(UserRole.ADMIN, UserRole.ANALYST, UserRole.READONLY))
):
    # All roles can view deals
    ...
```

### Optional Authentication

For endpoints that work with or without authentication:

```python
from typing import Optional
from fastapi import Depends
from app.core.security import get_current_user

@router.get("/public-or-private")
async def flexible_endpoint(
    current_user: Optional[dict] = Depends(get_current_user)
):
    if current_user:
        return {"message": f"Authenticated as {current_user['username']}"}
    else:
        return {"message": "Public access"}
```

## Creating the First Admin User

After running migrations, create an admin user using the Python script:

```python
import asyncio
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.auth import User

async def create_admin():
    async with AsyncSessionLocal() as db:
        admin = User(
            username="admin",
            email="admin@gallagher-mhp.com",
            hashed_password=hash_password("change_me_immediately"),
            full_name="System Administrator",
            role="admin",
            is_active=True
        )
        db.add(admin)
        await db.commit()
        print(f"Admin user created: {admin.username}")

if __name__ == "__main__":
    asyncio.run(create_admin())
```

Or via the API (requires temporary bypass or manual database insert):

```bash
# After creating first admin via script, subsequent users can be created via API
POST /api/v1/auth/users
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "username": "analyst1",
  "email": "analyst1@gallagher-mhp.com",
  "password": "secure_password",
  "full_name": "John Analyst",
  "role": "analyst"
}
```

## User Management Endpoints

### Get Current User Info

```bash
GET /api/v1/auth/me
Authorization: Bearer <token>
```

### List All Users (Admin Only)

```bash
GET /api/v1/auth/users
Authorization: Bearer <admin_token>
```

### Update User (Admin Only)

```bash
PATCH /api/v1/auth/users/{username}
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "role": "analyst",
  "is_active": true
}
```

### Delete User (Admin Only)

```bash
DELETE /api/v1/auth/users/{username}
Authorization: Bearer <admin_token>
```

## Token Expiration

- **Access tokens**: 30 minutes
- **Refresh tokens**: 7 days

Configure in `app/core/security.py`:
```python
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
```

## Security Best Practices

1. **Never commit passwords** to version control
2. **Use strong secrets** - Generate `SECRET_KEY` with:
   ```bash
   openssl rand -hex 32
   ```
3. **Enable HTTPS** in production - JWT tokens should never be sent over HTTP
4. **Rotate secrets regularly** - Plan for secret rotation every 90 days
5. **Monitor failed login attempts** - Implement rate limiting on login endpoint
6. **Use refresh tokens wisely** - Store securely, ideally in httpOnly cookies
7. **Implement logout** - Consider token blacklisting for immediate revocation

## Testing

Run authentication tests:

```bash
cd backend
pytest tests/test_auth.py -v
```

## Rollout Strategy

To minimize disruption, roll out authentication incrementally:

1. ✅ Deploy authentication infrastructure (this PR)
2. Add authentication to admin endpoints (/auth/users/*)
3. Add authentication to write endpoints (POST/PATCH/DELETE)
4. Add authentication to read endpoints (GET)
5. Enforce authentication on all endpoints except health checks

## Troubleshooting

### "Invalid authentication credentials"
- Token may be expired - use refresh token
- Token may be malformed - check Authorization header format: `Bearer <token>`
- SECRET_KEY mismatch - ensure same key across all instances

### "Insufficient permissions"
- User role doesn't match required role
- Check user role with `GET /api/v1/auth/me`
- Admin can update roles with `PATCH /api/v1/auth/users/{username}`

### "User not found or inactive"
- User account may be deactivated
- Admin can reactivate with `PATCH /api/v1/auth/users/{username}` and `{"is_active": true}`

## Migration Guide

After deploying this feature:

1. Run database migration:
   ```bash
   alembic upgrade head
   ```

2. Create first admin user (see script above)

3. Test authentication:
   ```bash
   # Login
   curl -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"change_me_immediately"}'
   
   # Use token
   curl http://localhost:8000/api/v1/auth/me \
     -H "Authorization: Bearer <access_token>"
   ```

4. Incrementally add authentication to endpoints

## API Documentation

After deployment, full API documentation is available at:
- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

The "Authorize" button in Swagger UI allows testing authenticated endpoints interactively.

