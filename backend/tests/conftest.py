"""公共测试 fixtures。"""

import pytest

from app.core.database import Base, SessionLocal, engine
from app.models.farm import Farm


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前重建表并播种默认农场。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(Farm(id=1, name="默认农场"))
    db.commit()
    db.close()
    yield
