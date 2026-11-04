import os
from pathlib import Path

from dotenv import load_dotenv

# The settings file (W26-R51): .env.local in this folder; ENV_FILE (an environment variable of the process) names another, for example .env.staging.
# A value already in the real environment (Render's dashboard, the shell) wins over the file.
load_dotenv(Path(__file__).resolve().parent / (os.environ.get("ENV_FILE", "").strip() or ".env.local"))

from app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(port=5000)
