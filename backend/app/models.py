from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Recipe(Base):

    __tablename__ = "recipes"

    id = Column(Integer, primary_key = True, index = True)

    name = Column(String)

    ingredients = Column(Text)

    cuisine = Column(String)

    instructions = Column(Text)

