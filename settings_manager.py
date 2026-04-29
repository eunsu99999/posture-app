"""AppSettings — 앱 설정을 JSON 파일에 영구 저장."""
import json
import os

SETTINGS_FILE = r"C:\storage\med\app_settings.json"

DEFAULTS = {
    "alert_interval": 5,    # 경고 알림 간격 (초) — 기본값 5초
    "stretch_goal":   5,    # 일일 스트레칭 목표 횟수
}


class AppSettings:
    def __init__(self, filepath=SETTINGS_FILE):
        self.filepath = filepath
        self._data    = dict(DEFAULTS)
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self._data.update(json.load(f))
            except Exception:
                pass

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self._save()

    # ── 편의 프로퍼티 ─────────────────────────────────────────────────────────
    @property
    def alert_interval(self):
        return int(self._data.get("alert_interval", DEFAULTS["alert_interval"]))

    @alert_interval.setter
    def alert_interval(self, value):
        self.set("alert_interval", int(value))

    @property
    def stretch_goal(self):
        return int(self._data.get("stretch_goal", DEFAULTS["stretch_goal"]))

    @stretch_goal.setter
    def stretch_goal(self, value):
        self.set("stretch_goal", int(value))

