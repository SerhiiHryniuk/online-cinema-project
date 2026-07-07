from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Online Cinema"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    SECRET_KEY: str = Field(default=...)
    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    WEB_PORT: int = 8000
    REDIS_PORT: int = 6379
    MINIO_PORT: int = 9000
    MINIO_CONSOLE_PORT: int = 9001

    POSTGRES_USER: str = Field(default=...)
    POSTGRES_PASSWORD: str = Field(default=...)
    POSTGRES_DB: str = Field(default=...)
    POSTGRES_PORT: int = Field(default=...)
    DATABASE_URL: str = Field(default=...)

    REDIS_URL: str = Field(default=...)

    STORAGE_ENDPOINT_URL: str = Field(default=...)
    STORAGE_PUBLIC_URL: str = Field(default=...)
    STORAGE_ACCESS_KEY: str = Field(default=...)
    STORAGE_SECRET_KEY: str = Field(default=...)
    STORAGE_BUCKET_NAME: str = Field(default=...)

    API_V1_PREFIX: str = "/api/v1"

    BASE_URL: str = "http://127.0.0.1:8000"
    STRIPE_SECRET_KEY: str
    STRIPE_PUBLISHABLE_KEY: str
    STRIPE_WEBHOOK_SECRET: str
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
    PAYMENT_SUCCESS_EMAIL_TEMPLATE_NAME: str = "payment_success.html"

    SUPERUSER_EMAIL: str = Field(default=...)
    SUPERUSER_PASSWORD: str = Field(default=...)


settings = Settings()
