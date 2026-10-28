import os

# Tests run against a real Postgres (row locks, enums and Numeric behave as in production).
# Set here because pytest imports this package before conftest, i.e. before the app reads settings.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://takeaway:takeaway@localhost:5432/takeaway_test"
)
