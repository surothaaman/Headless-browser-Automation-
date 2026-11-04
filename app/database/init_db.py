
from app.database.connection import Base, engine
from app.database.models import Order


def init_database():
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")


if __name__ == "__main__":
    init_database()
