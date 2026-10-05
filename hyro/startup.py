from alembic import command
from alembic.config import Config
from sqlalchemy import text, select

from hyro.config import settings
from hyro.db import SessionLocal, engine
from hyro.models import Team, User


def migrate_and_seed():
    config = Config("alembic.ini")
    # Session-level lock survives Alembic's transaction boundaries.
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(67925017)"))
        connection.commit()
        try:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            connection.commit()
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(67925017)"))
            connection.commit()
    with SessionLocal.begin() as session:
        user = session.scalar(select(User).where(User.email == settings.seed_user_email))
        if user is None:
            team = Team(name="Development team")
            session.add(team)
            session.flush()
            session.add(User(team_id=team.id, email=settings.seed_user_email, name="Development recruiter"))
