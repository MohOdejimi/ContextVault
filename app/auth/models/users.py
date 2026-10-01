from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.database.base import Base


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] =  mapped_column(unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)