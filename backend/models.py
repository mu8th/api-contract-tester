"""SQLAlchemy ORM for API Contract Tester."""

from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker


Base = declarative_base()


engine = create_engine("sqlite:///profiles.db")
Session = sessionmaker(bind=engine)


class Spec(Base):
    """OpenAPI specification stored in database."""

    __tablename__ = "specs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(256), nullable=False)
    version = Column(String(32), nullable=False)
    content = Column(Text, nullable=False)
    uploaded_at = Column(DateTime, nullable=False)


class Test(Base):
    """Contract enforcement test record."""

    __tablename__ = "tests"

    id: Column[int] = Column(Integer, primary_key=True, autoincrement=True)
    spec_id: Column[int] = Column(Integer, nullable=False)
    endpoint: Column[str] = Column(String(256), nullable=False)
    status: Column[bool] = Column(Boolean, nullable=False)
    severity_score: Column[float] = Column(Float, nullable=True)


class Result(Base):
    """Test result with schema drift details."""

    __tablename__ = "results"

    id: Column[int] = Column(Integer, primary_key=True, autoincrement=True)
    test_id: Column[int] = Column(Integer, nullable=False)
    field_name: Column[str] = Column(String(256), nullable=False)
    expected_type: Column[str] = Column(String(32), nullable=False)
    actual_type: Column[str] = Column(String(32), nullable=False)
    breaking_change: Column[bool] = Column(Boolean, nullable=False)