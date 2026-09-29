import os
import sys
import shutil
import traceback
from pathlib import Path


def get_bundle_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(getattr(sys, '_MEIPASS', Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def ensure_runtime_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.exists() and not destination.exists():
        shutil.copy2(source, destination)


def main() -> int:
    bundle_root = get_bundle_root()
    runtime_root = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else bundle_root

    bundled_db = bundle_root / 'db.sqlite3'
    runtime_db = runtime_root / 'db.sqlite3'
    ensure_runtime_file(bundled_db, runtime_db)

    env = os.environ.copy()
    env.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    env.setdefault('KNOT_DB_PATH', str(runtime_db))
    env.setdefault('KNOT_MEDIA_ROOT', str(runtime_root / 'media'))
    env.setdefault('KNOT_STATIC_ROOT', str(runtime_root / 'staticfiles'))

    from django.core.management import execute_from_command_line

    os.environ.update(env)
    sys.path.insert(0, str(bundle_root))
    sys.argv = [
        'manage.py',
        'runserver',
        '127.0.0.1:8000',
        '--noreload',
    ]

    try:
        execute_from_command_line(sys.argv)
        return 0
    except Exception:
        error_log = runtime_root / 'knot-launcher-error.log'
        error_log.write_text(traceback.format_exc(), encoding='utf-8')
        if getattr(sys, 'frozen', False):
            print(f"Startup failed. See: {error_log}")
            try:
                input('Press Enter to close...')
            except EOFError:
                pass
        raise


if __name__ == '__main__':
    raise SystemExit(main())