# Materra — Database Schema Notes
**Version:** MVP 1.3  **Date:** 2026-06-03

---

## Tables Overview

### 1. `accounts_user`
Custom user model (`AUTH_USER_MODEL = 'accounts.User'`). Extends `AbstractBaseUser` + `PermissionsMixin`.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default=uuid4 |
| `email` | VARCHAR | UNIQUE, USERNAME_FIELD |
| `full_name` | VARCHAR(255) | blank=True |
| `password` | VARCHAR | hashed by Django |
| `last_login` | DATETIME | from AbstractBaseUser |
| `is_active` | BOOL | default=True |
| `is_staff` | BOOL | default=False |
| `is_superuser` | BOOL | from PermissionsMixin |
| `created_at` | DATETIME | auto_now_add |

**Admin:** `UserAdmin` — list by email, full_name, is_staff, is_active, created_at.

---

### 2. `analyses_wasteclass`
Reference/lookup table. 14 rows seeded via data migration. Never written at runtime.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default=uuid4 |
| `code` | VARCHAR(50) | UNIQUE (e.g. `'concrete'`, `'metal'`) |
| `label_uk` | VARCHAR(100) | Ukrainian label |
| `label_en` | VARCHAR(100) | English label |
| `recycling_method` | TEXT | blank=True |
| `ecological_score` | INT | 1–10, nullable |
| `is_hazardous` | BOOL | default=False |
| `created_at` | DATETIME | auto_now_add |

**Admin:** `WasteClassAdmin` — list by code, label_uk, label_en, eco_score, is_hazardous.

---

### 3. `analyses_analysis`
Core job table. One row per submitted image. Lifecycle: PENDING → PROCESSING → DONE | FAILED | REVIEW_NEEDED.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default=uuid4 |
| `user_id` | UUID | FK → `accounts_user.id`, null=True, SET_NULL |
| `status` | VARCHAR(20) | choices: pending/processing/done/failed/review_needed |
| `image_filename` | VARCHAR(255) | blank=True |
| `image_size_bytes` | INT | nullable |
| `predictions` | JSON | nullable — `[{class, confidence, label_uk}, …]` |
| `top_class` | VARCHAR(100) | blank=True — stores `WasteClass.code` as plain string |
| `top_confidence` | FLOAT | nullable |
| `model_version` | VARCHAR(50) | blank=True |
| `inference_time_ms` | INT | nullable |
| `needs_human_review` | BOOL | default=False |
| `notes` | TEXT | blank=True |
| `created_at` | DATETIME | auto_now_add |
| `updated_at` | DATETIME | auto_now |

**Indexes:** `idx_analyses_user` (user_id), `idx_analyses_status` (status), `idx_analyses_created_at` (-created_at).  
**Admin:** `AnalysisAdmin` — AI Results fieldset is collapsible; all result columns are read-only.

---

### 4. `analyses_analysisimage`
Binary image store. Separate table so list queries on `analyses_analysis` never load blob bytes.

| Column | Type | Constraints |
|---|---|---|
| `analysis_id` | UUID | PK + FK → `analyses_analysis.id`, CASCADE |
| `image_data` | BLOB | raw bytes (up to 10 MB) |
| `content_type` | VARCHAR(50) | e.g. `'image/jpeg'` |
| `created_at` | DATETIME | auto_now_add |

No admin registration (accessed only via `GET /api/v1/analyses/{uuid}/image/`).

---

### 5. `reports_labeltranslation`
Translation cache for raw ImageNet class names. Auto-populated on first encounter via MyMemory API.

| Column | Type | Constraints |
|---|---|---|
| `id` | INT | PK, auto-increment |
| `raw_label_en` | VARCHAR(200) | UNIQUE (e.g. `'steel arch bridge'`) |
| `translated_uk` | VARCHAR(200) | Ukrainian translation |
| `is_manual` | BOOL | default=False — prevents API overwrite |
| `created_at` | DATETIME | auto_now_add |
| `updated_at` | DATETIME | auto_now |

**Admin:** `LabelTranslationAdmin` — `translated_uk` and `is_manual` are inline-editable in list view.

---

### Django Built-in Tables (auto-created)

| Table | Purpose |
|---|---|
| `auth_group` | Permission groups |
| `auth_permission` | Granular permissions per ContentType |
| `auth_group_permissions` | Junction: group ↔ permission |
| `accounts_user_groups` | Junction: user ↔ group (M2M via PermissionsMixin) |
| `accounts_user_user_permissions` | Junction: user ↔ permission (M2M) |
| `django_content_type` | ContentType framework |
| `django_session` | Session-based authentication cookies |
| `django_admin_log` | Admin action audit log |
| `django_migrations` | Migration history |

---

## Relationships

```
accounts_user ──────────────────────────── analyses_analysis
    1                  FK (null=True, SET_NULL)       N
                       (one user → many analyses)

analyses_analysis ──────────────────────── analyses_analysisimage
    1              OneToOne (PK+CASCADE)           1
                   (each analysis has one image blob)

analyses_analysis.top_class ──► analyses_wasteclass.code
    [logical only — no DB FK, stored as VARCHAR]

accounts_user ◄────────────────────────── auth_group
    M                     M2M (accounts_user_groups)
accounts_user ◄────────────────────────── auth_permission
    M                M2M (accounts_user_user_permissions)

reports_labeltranslation
    [standalone — no FK relationships]
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Images in DB (`BinaryField`) | No filesystem / MEDIA_ROOT dependency; simplifies Docker volumes |
| `AnalysisImage` separate table | List queries on `analyses_analysis` never hit blob bytes |
| `top_class` as VARCHAR (not FK) | `WasteClass` may not exist in DB for every slug; unknown/review path uses `'unknown'` which is a sentinel, not a true class. Keeps inference code decoupled from DB lookups at classification time |
| UUID PKs everywhere (app tables) | Avoids sequential ID enumeration in REST API; UUIDs are safe to expose in URLs |
| `user_id` nullable (SET_NULL) | Allows anonymous API uploads; preserves analysis record if account deleted |
| Session auth (no JWT) | MVP simplicity — JWT migration planned via `djangorestframework-simplejwt` |
| `is_manual` flag on translations | Allows admin corrections without risk of API overwrite during next cache miss |

---

## DB Indexes

| Index name | Table | Column(s) | Type |
|---|---|---|---|
| `idx_analyses_user` | analyses_analysis | user_id | BTree |
| `idx_analyses_status` | analyses_analysis | status | BTree |
| `idx_analyses_created_at` | analyses_analysis | -created_at (DESC) | BTree |
| (implicit) | accounts_user | email | UNIQUE |
| (implicit) | analyses_wasteclass | code | UNIQUE |
| (implicit) | reports_labeltranslation | raw_label_en | UNIQUE |
| (implicit) | analyses_analysisimage | analysis_id | PK |
