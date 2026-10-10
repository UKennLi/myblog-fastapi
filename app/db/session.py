from sqlalchemy import create_engine, URL
from sqlalchemy.orm import sessionmaker


def make_database(settings):
    url = URL.create("mysql+pymysql", username=settings.db_user,
                     password=settings.db_password.get_secret_value(), host=settings.db_host,
                     port=settings.db_port, database=settings.db_name, query={"charset": "utf8mb4"})
    engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800,
                           pool_size=settings.db_pool_size, max_overflow=settings.db_max_overflow,
                           connect_args={"connect_timeout": 10, "read_timeout": 30, "write_timeout": 30},
                           hide_parameters=True)
    return engine, sessionmaker(engine, expire_on_commit=False)
