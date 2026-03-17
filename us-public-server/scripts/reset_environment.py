"""Utility script to reset the local backend state for full-flow testing."""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import settings
from database.init_db import init_database
TEST_OUTPUT_DIR = ROOT / "test" / "output"


def wipe_path(path: Path):
    if path.is_file() or path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def clean_directory(path: Path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def reset_database():
    db_path = Path(settings.DATABASE_PATH)
    if db_path.exists():
        db_path.unlink()
    init_database(str(db_path))


def reset_storage():
    for key, fallback in (
        ("html_path", "storage/html"),
        ("json_path", "storage/json"),
        ("images_path", "storage/images"),
        ("reports_path", "storage/reports"),
    ):
        clean_directory(ROOT / settings.STORAGE_CONFIG.get(key, fallback))


def reset_test_output():
    if TEST_OUTPUT_DIR.exists():
        shutil.rmtree(TEST_OUTPUT_DIR)
    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Reset local backend state")
    parser.add_argument("--skip-db", action="store_true", help="Do not recreate the database")
    parser.add_argument("--skip-storage", action="store_true", help="Do not wipe storage directories")
    parser.add_argument("--skip-test-output", action="store_true", help="Do not clear test/output")
    args = parser.parse_args()

    if not args.skip_db:
        reset_database()
        print("✅ Database reset complete")
    if not args.skip_storage:
        reset_storage()
        print("✅ Storage directory reset complete")
    if not args.skip_test_output:
        reset_test_output()
        print("✅ test/output cleared")

    print("🎯 Environment reset finished")


if __name__ == "__main__":
    main()
