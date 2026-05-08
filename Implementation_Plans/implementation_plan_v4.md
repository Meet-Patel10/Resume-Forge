# PostgreSQL Integration Plan

Migrate from SQLite to PostgreSQL. The app already uses Flask-SQLAlchemy, so this is a clean swap — SQLAlchemy handles dialect differences automatically.

## What Exists Today

| Component | Status |
|-----------|--------|
| Flask-SQLAlchemy ORM | ✅ Already set up |
| `DATABASE_URL` env var | ✅ Already reads from [.env](file:///Users/meetpatel/Resume_Builder_Application/.env) (defaults to SQLite) |
| Models | ✅ [MasterResume](file:///Users/meetpatel/Resume_Builder_Application/app/models/master_resume.py#6-111), [Bullet](file:///Users/meetpatel/Resume_Builder_Application/app/models/bullet.py#5-57), [Application](file:///Users/meetpatel/Resume_Builder_Application/app/models/application.py#6-66), [AnalysisHistory](file:///Users/meetpatel/Resume_Builder_Application/app/models/analysis.py#6-49) |
| User model | ❌ Does not exist |
| Resume versioning | ❌ Not implemented |

## Proposed Changes

### Dependencies

#### [MODIFY] [requirements.txt](file:///Users/meetpatel/Resume_Builder_Application/requirements.txt)
- Add `psycopg2-binary` (PostgreSQL adapter for Python)

---

### Environment Config

#### [MODIFY] [.env](file:///Users/meetpatel/Resume_Builder_Application/.env)
- Replace `DATABASE_URL=sqlite:///resumeforge.db` with PostgreSQL URL:
  ```
  DATABASE_URL=postgresql://username:password@localhost:5432/resumeforge
  ```

#### [MODIFY] [.env.example](file:///Users/meetpatel/Resume_Builder_Application/.env.example)
- Add PostgreSQL example URL and individual credential vars

---

### New Models

#### [NEW] [user.py](file:///Users/meetpatel/Resume_Builder_Application/app/models/user.py)
New `User` model:
- [id](file:///Users/meetpatel/Resume_Builder_Application/app/static/js/app.js#14-18), `username`, `email`, `password_hash`, `created_at`, `updated_at`
- Relationships: `master_resumes`, [applications](file:///Users/meetpatel/Resume_Builder_Application/app/routes/applications.py#8-13)

#### [NEW] [resume_version.py](file:///Users/meetpatel/Resume_Builder_Application/app/models/resume_version.py)
New `ResumeVersion` model for tracking modified resumes:
- [id](file:///Users/meetpatel/Resume_Builder_Application/app/static/js/app.js#14-18), `application_id`, `version_number`, `resume_json`, `resume_latex`, [ats_score](file:///Users/meetpatel/Resume_Builder_Application/app/routes/tailor.py#401-414), `created_at`
- Links to [Application](file:///Users/meetpatel/Resume_Builder_Application/app/models/application.py#6-66) — each tailoring run creates a new version

---

### Updated Models

#### [MODIFY] [master_resume.py](file:///Users/meetpatel/Resume_Builder_Application/app/models/master_resume.py)
- Add `user_id` FK → `users.id`
- Change JSON text fields to PostgreSQL [JSON](file:///Users/meetpatel/Resume_Builder_Application/app/templates/master_resume.html#230-241) type (native, queryable)

#### [MODIFY] [application.py](file:///Users/meetpatel/Resume_Builder_Application/app/models/application.py)
- Add `user_id` FK → `users.id`
- Add `versions` relationship → `ResumeVersion`
- Change JSON text fields to PostgreSQL [JSON](file:///Users/meetpatel/Resume_Builder_Application/app/templates/master_resume.html#230-241) type

#### [MODIFY] [analysis.py](file:///Users/meetpatel/Resume_Builder_Application/app/models/analysis.py)
- Change JSON text fields to PostgreSQL [JSON](file:///Users/meetpatel/Resume_Builder_Application/app/templates/master_resume.html#230-241) type

---

### Updated Routes & App Factory

#### [MODIFY] [__init__.py](file:///Users/meetpatel/Resume_Builder_Application/app/__init__.py)
- Import new `User` and `ResumeVersion` models in [create_app](file:///Users/meetpatel/Resume_Builder_Application/app/__init__.py#10-42)

#### [MODIFY] [models/__init__.py](file:///Users/meetpatel/Resume_Builder_Application/app/models/__init__.py)
- Export `User` and `ResumeVersion`

#### [MODIFY] [tailor.py](file:///Users/meetpatel/Resume_Builder_Application/app/routes/tailor.py)
- After tailoring, save a `ResumeVersion` record with version number

---

## User Review Required

> [!IMPORTANT]
> **PostgreSQL must be installed and running locally.** Do you already have PostgreSQL installed? If not, you'll need to install it via `brew install postgresql@16` and start the service.

> [!IMPORTANT]
> **Database credentials:** What username/password/database name do you want for local development? Default plan: `resumeforge` for all three.

## Verification Plan

### Automated Tests
```bash
pip install psycopg2-binary
python run.py  # Should connect to PostgreSQL and create all tables
```

### Manual Verification
- Save a master resume → verify it persists in PostgreSQL
- Tailor a resume → verify a `ResumeVersion` record is created
- Check `psql -d resumeforge -c "SELECT * FROM users;"` shows data
