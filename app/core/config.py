from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Online Cinema"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str
    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    WEB_PORT: int = 8000
    REDIS_PORT: int = 6379
    MINIO_PORT: int = 9000
    MINIO_CONSOLE_PORT: int = 9001

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: int
    DATABASE_URL: str

    REDIS_URL: str

    STORAGE_ENDPOINT_URL: str
    STORAGE_ACCESS_KEY: str
    STORAGE_SECRET_KEY: str
    STORAGE_BUCKET_NAME: str

    API_V1_PREFIX: str = "/api/v1"

    BASE_URL: str = "http://127.0.0.1:8000"
    EMAIL_HOST: str = "mailhog"
    EMAIL_PORT: int = 1025
    EMAIL_HOST_USER: str = "testing@mail.com"
    EMAIL_HOST_PASSWORD: str = "test_password"
    EMAIL_USE_TLS: bool = False

    EMAIL_TEMPLATE_DIR: str = "app/notifications/templates"
    ACTIVATION_EMAIL_TEMPLATE_NAME: str = "activation_request.html"
    ACTIVATION_COMPLETE_EMAIL_TEMPLATE_NAME: str = "activation_complete.html"
    PASSWORD_EMAIL_TEMPLATE_NAME: str = "password_reset_request.html"
    PASSWORD_COMPLETE_EMAIL_TEMPLATE_NAME: str = "password_reset_complete.html"

    SUPERUSER_EMAIL: str
    SUPERUSER_PASSWORD: str


settings = Settings()
