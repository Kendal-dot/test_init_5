from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    debug: bool = False

    # Storage
    storage_dir: Path = Path("/app/storage")
    uploads_dir: Path = Path("/app/storage/uploads")
    exports_dir: Path | None = None  # Härleds från storage_dir om inte satt
    models_cache_dir: Path = Path("/app/storage/models_cache")

    # Database – stöd för SQLite och Postgres via samma variabel
    database_url: str = "sqlite+aiosqlite:////app/storage/db/transcriber.db"

    # Transcription
    transcription_model: str = "KBLab/kb-whisper-small"
    vad_backend: Literal["silero", "pyannote"] = "silero"
    hf_token: str = ""
    diarization_enabled: bool = False
    max_speakers: int = 0
    min_speakers: int = 1

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Job queue
    max_concurrent_jobs: int = 1

    @property
    def resolved_exports_dir(self) -> Path:
        """Exports-katalog – härleds från storage_dir om inte explicit satt."""
        if self.exports_dir is not None:
            return self.exports_dir
        return Path(self.storage_dir) / "exports"

    def ensure_dirs(self) -> None:
        """Skapa nödvändiga lagringskataloger om de saknas."""
        for d in [self.storage_dir, self.uploads_dir, self.resolved_exports_dir, self.models_cache_dir]:
            Path(d).mkdir(parents=True, exist_ok=True)
        # Skapa db-katalog baserat på SQLite-sökväg
        if "sqlite" in self.database_url:
            db_path = self.database_url.split("///")[-1]
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
