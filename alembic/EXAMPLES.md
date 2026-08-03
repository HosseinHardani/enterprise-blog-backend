# Alembic Migration Examples

This project ships one real migration (`0001_initial.py`) that creates the full
schema matching the current ORM models. The snippets below are **reference
patterns** for future migrations -- copy the relevant one into a new revision
generated with:

```bash
alembic revision -m "add reading_time to posts"
```

## 1. Adding a new column safely

Add nullable first (or with a server_default) so existing rows never fail the
migration, then backfill/tighten in a later migration if you need NOT NULL.

```python
def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column("reading_time_minutes", sa.Integer(), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("posts", "reading_time_minutes")
```

## 2. Renaming a column without downtime

A naive `ALTER TABLE ... RENAME COLUMN` breaks any code still deployed with
the old column name. The safe sequence across three deploys is:

```python
# Migration A: add the new column, dual-write in application code
def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(150), nullable=True))
    op.execute("UPDATE users SET display_name = full_name")

# Migration B (later deploy, once all instances write both columns):
def upgrade() -> None:
    op.alter_column("users", "display_name", nullable=False)

# Migration C (final deploy, once no code reads full_name anymore):
def upgrade() -> None:
    op.drop_column("users", "full_name")
```

## 3. Updating schema safely with a batch of changes

Group related DDL in one transaction-safe migration, and always pair
`upgrade()` with a working `downgrade()`:

```python
def upgrade() -> None:
    op.add_column("posts", sa.Column("reading_time_minutes", sa.Integer(), nullable=True))
    op.create_index("ix_posts_reading_time", "posts", ["reading_time_minutes"])
    op.create_check_constraint(
        "ck_posts_reading_time_positive", "posts", "reading_time_minutes >= 0"
    )

def downgrade() -> None:
    op.drop_constraint("ck_posts_reading_time_positive", "posts", type_="check")
    op.drop_index("ix_posts_reading_time", table_name="posts")
    op.drop_column("posts", "reading_time_minutes")
```

## Common commands

```bash
alembic upgrade head          # apply all pending migrations
alembic downgrade -1          # roll back the last migration
alembic revision --autogenerate -m "message"   # generate from model diffs
alembic history --verbose
alembic current
```
