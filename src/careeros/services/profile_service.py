from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from careeros.db.models.profile import Profile
from careeros.db.models.user import User
from careeros.schemas.profile import ProfileCreateRequest


def create_profile(session: Session, payload: ProfileCreateRequest) -> Profile:
    user = User(
        email=payload.email,
        display_name=payload.display_name,
        timezone=payload.timezone,
    )
    profile = Profile(
        user=user,
        headline=payload.headline,
        summary=payload.summary,
        target_roles=payload.target_roles,
        target_locations=payload.target_locations,
        work_preferences=payload.work_preferences,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return get_profile(session=session, profile_id=profile.id) or profile


def get_profile(session: Session, profile_id: UUID) -> Profile | None:
    statement = (
        select(Profile)
        .options(joinedload(Profile.user))
        .where(Profile.id == profile_id)
    )
    return session.scalar(statement)

