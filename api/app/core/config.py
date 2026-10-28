from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULTS = {
    "jwt_secret_key": "insecure-dev-secret-change-me-in-production",
    "first_admin_password": "admin1234",
    "demo_customer_password": "customer1234",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["local", "production"] = "local"
    project_name: str = "Takeaway API"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://takeaway:takeaway@localhost:5432/takeaway"

    jwt_secret_key: str = INSECURE_DEFAULTS["jwt_secret_key"]
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    first_admin_email: str = "admin@takeaway.dev"
    first_admin_password: str = INSECURE_DEFAULTS["first_admin_password"]
    max_orders_per_customer: int = 10  # cancelled orders don't count
    seed_demo_data: bool = True  # demo restaurants + a demo customer
    demo_customer_email: str = "customer@takeaway.dev"
    demo_customer_password: str = INSECURE_DEFAULTS["demo_customer_password"]

    # Passwordless login as any account, for the local demo's account switcher. Off unless
    # explicitly enabled (docker-compose does), and refused in production.
    demo_logins: bool = False

    @model_validator(mode="after")
    def _no_insecure_defaults_in_production(self) -> "Settings":
        insecure = [k for k, v in INSECURE_DEFAULTS.items() if getattr(self, k) == v]
        if not self.seed_demo_data:  # the demo customer isn't created then
            insecure = [k for k in insecure if k != "demo_customer_password"]
        if self.environment == "production" and insecure:
            raise ValueError(f"Set secure values for {insecure} in production")
        if self.environment == "production" and self.demo_logins:
            raise ValueError("DEMO_LOGINS must be off in production")
        return self


settings = Settings()
