"""
Autoscaling Manager — Monitor system load and log scaling events.
"""
import os
import time
import logging
import threading
import psutil

logger = logging.getLogger(__name__)

SCALE_UP_CPU = 80      # CPU % threshold to log scale-up suggestion
SCALE_DOWN_CPU = 20    # CPU % threshold to log scale-down suggestion
CHECK_INTERVAL = 30    # seconds between checks
LOG_FILE = os.path.join(os.path.dirname(__file__), 'autoscaling.log')


class AutoscalingManager:
    def __init__(self):
        self._running = False
        self._thread = None
        self._log_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
        self._log_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        self._scale_logger = logging.getLogger('autoscaling')
        self._scale_logger.addHandler(self._log_handler)
        self._scale_logger.setLevel(logging.INFO)

    def _check(self):
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory().percent
        if cpu > SCALE_UP_CPU:
            self._scale_logger.info(f"SCALE_UP_SUGGESTED cpu={cpu:.1f}% mem={mem:.1f}%")
        elif cpu < SCALE_DOWN_CPU:
            self._scale_logger.info(f"SCALE_DOWN_SUGGESTED cpu={cpu:.1f}% mem={mem:.1f}%")

    def _run(self):
        while self._running:
            try:
                self._check()
            except Exception as e:
                logger.warning(f"Autoscaling check error: {e}")
            time.sleep(CHECK_INTERVAL)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="autoscaling-monitor")
        self._thread.start()
        logger.info("Autoscaling monitor started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Autoscaling monitor stopped")

    def get_current_metrics(self):
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "pid": os.getpid(),
        }


_manager = AutoscalingManager()


def get_autoscaling_manager():
    return _manager
