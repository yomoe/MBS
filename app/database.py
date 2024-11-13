import logging
from dataclasses import dataclass

from environs import Env
from sqlalchemy.engine.url import URL
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


@dataclass
class DbConfig:
    """
    Database configuration class.
    This class holds the settings for the database, such as host, password, port, etc.
    """

    driver: str
    db_backend: str
    host: str
    password: str
    user: str
    database: str
    port: int

    # For SQLAlchemy / Alembic
    def construct_sqlalchemy_url(self, driver=None) -> str:
        driver = driver or self.driver
        uri = URL.create(
            drivername=f"{self.db_backend}+{driver}",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
        )
        return uri.render_as_string(
            hide_password=False)  # hide_password=False обязательный параметр, иначе будет скрыт пароль и подключиться к базе не получится.

    @staticmethod
    def from_env(env: Env = None) -> 'DbConfig':
        """
        Creates the DbConfig object from environment variables.
        """
        if env is None:
            env = Env()
            env.read_env()

        driver = env.str("DB_DRIVER", "asyncpg")
        db_backend = env.str("DB_BACKEND", "postgresql")
        host = env.str("DB_HOST", "localhost")
        password = env.str("DB_PASSWORD", "postgres")
        user = env.str("DB_USER", "postgres")
        database = env.str("DB_NAME", "postgres")
        port = env.int("DB_PORT", 5432)

        return DbConfig(
            host=host,
            password=password,
            user=user,
            database=database,
            port=port,
            driver=driver,
            db_backend=db_backend,
        )


# Создание объекта DbConfig из переменных окружения
db_config = DbConfig.from_env()

# Получение строки подключения
SQLALCHEMY_DATABASE_URL = db_config.construct_sqlalchemy_url()

# Создание асинхронного движка SQLAlchemy
try:
    engine = create_async_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
    # Создание фабрики асинхронных сессий
    async_session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        autoflush=False,
        expire_on_commit=False,
        autocommit=False,
    )

except Exception as e:
    logger.error(f"Не удалось создать движок базы данных: {e}")
    raise


# Создание базового класса моделей
class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
