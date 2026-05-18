# from django.apps import AppConfig
# import os


# class CoreConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'core'

#     def ready(self):
#         run_main = os.environ.get("RUN_MAIN")
#         if run_main is not None and run_main != "true":
#             return
#         try:
#             from .detector import start_detector
#             start_detector()
#         except Exception:
#             # avoid crashing app if detector fails during startup
#             import logging
#             logging.getLogger(__name__).exception("Failed to start AI detector")

from django.apps import AppConfig
import sys

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # ❌ Không phải runserver thì thoát ngay
        if 'runserver' not in sys.argv:
            return

        # ✅ Chỉ runserver mới chạy AI
        from .detector import start_detector
        print("🚀 Auto-starting AI detector...")
        start_detector()
