# API Guide

Base URL: `http://localhost:8000/api/v1`. Interactive docs at `/docs` (Swagger) and `/redoc`.

Every error response has the same shape:

```json
{ "error": "not_found", "message": "Post not found", "details": null }
```

Validation errors additionally populate `details` with a list of `{"field": ..., "message": ...}`.

## Authentication flow

```
POST /auth/register          -> 201, sends a verification email in the background
POST /auth/login              -> 200, {access_token, token_type, expires_in} + sets refresh_token cookie
GET  /auth/me                    -> 200, current user (requires Authorization: Bearer <access_token>)
POST /auth/refresh              -> 200, rotates the refresh cookie, returns a new access token
POST /auth/logout               -> 200, blacklists the access token, revokes the refresh token
POST /auth/verify-email        -> 200, {token} from the verification email
POST /auth/resend-verification -> 200, {email}
POST /auth/password-reset/request  -> 200, {email}
POST /auth/password-reset/confirm  -> 200, {token, password}
```

Example login:

```bash
curl -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "TestPass123"}'
```

Example authenticated request:

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

Example refresh (cookie carries the refresh token automatically):

```bash
curl -b cookies.txt -c cookies.txt -X POST http://localhost:8000/api/v1/auth/refresh
```

## Posts

```
GET    /posts                 -> paginated list; query params below
GET    /posts/{slug}            -> single post by slug, increments view_count
POST   /posts                    -> create (auth required)
PATCH  /posts/{post_id}          -> update (author, editor, or admin)
DELETE /posts/{post_id}          -> soft delete (author, editor, or admin)
POST   /posts/{post_id}/like     -> toggle like (auth required)
```

`GET /posts` query parameters:

| Param | Type | Notes |
|---|---|---|
| `page`, `page_size` | int | 1-indexed; `page_size` capped at `MAX_PAGE_SIZE` (default 100) |
| `status` | `draft` \| `published` | Non-editor/admin callers are always forced to `published` unless they explicitly request otherwise |
| `category_id`, `tag_id`, `author_id` | UUID | Exact-match filters |
| `search` | string | Case-insensitive match against title, content, excerpt |
| `sort_by` | `created_at` \| `title` \| `view_count` | Default `created_at` |
| `sort_order` | `asc` \| `desc` | Default `desc` |

## Comments

```
GET    /posts/{post_id}/comments   -> paginated top-level comments, each with nested replies
POST   /posts/{post_id}/comments   -> create a comment or reply ({content, parent_id?})
PATCH  /comments/{comment_id}      -> edit (author or admin)
DELETE /comments/{comment_id}      -> soft delete (author, editor, or admin)
```

## Categories & Tags

```
GET    /categories | /tags               -> public, paginated
GET    /categories/{id}                    -> public
POST   /categories | /tags                -> editor or admin only
PATCH  /categories/{id}                    -> editor or admin only
DELETE /categories/{id} | /tags/{id}      -> editor or admin only
```

## Bookmarks

```
GET    /bookmarks             -> current user's bookmarks, paginated
POST   /bookmarks/{post_id}   -> add (409 if already bookmarked)
DELETE /bookmarks/{post_id}   -> remove (404 if not bookmarked)
```

## Users

```
GET    /users/{username}              -> public profile
PATCH  /users/me                       -> update full_name/bio
POST   /users/me/profile-image        -> multipart upload, JPEG/PNG/WebP up to MAX_UPLOAD_SIZE_MB
POST   /users/me/change-email          -> requires current_password
POST   /users/me/change-password      -> requires current_password, revokes all sessions
DELETE /users/me                          -> soft-delete own account
PATCH  /users/{user_id}/role           -> admin only
```

## Status codes used throughout

| Code | Meaning |
|---|---|
| 200 | Success |
| 201 | Resource created |
| 401 | Missing/invalid/expired/blacklisted token |
| 403 | Authenticated but not authorized for this action |
| 404 | Resource not found |
| 409 | Conflict (duplicate email/username/slug/bookmark/like) |
| 422 | Request validation failed |
| 429 | Rate limit exceeded |
| 500 | Unhandled server error |
