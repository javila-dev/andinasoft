import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Delete files older than N hours in MEDIA_ROOT/tmp."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Delete files older than this number of hours (default: 24).",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        if hours < 0:
            self.stderr.write(self.style.ERROR("--hours must be >= 0"))
            return

        tmp_dir = os.path.join(settings.MEDIA_ROOT, "tmp")
        if not os.path.isdir(tmp_dir):
            self.stdout.write(self.style.WARNING(f"Directory not found: {tmp_dir}"))
            return

        now = time.time()
        max_age = hours * 3600
        deleted = 0
        skipped = 0

        for root, _, files in os.walk(tmp_dir):
            for name in files:
                path = os.path.join(root, name)
                try:
                    age = now - os.path.getmtime(path)
                    if age > max_age:
                        os.remove(path)
                        deleted += 1
                    else:
                        skipped += 1
                except FileNotFoundError:
                    continue
                except OSError as exc:
                    self.stderr.write(f"Could not remove {path}: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"cleanup_tmp_files completed: deleted={deleted}, kept={skipped}, hours={hours}"
            )
        )
