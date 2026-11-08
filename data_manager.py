import json
import os
import threading
from datetime import date, datetime
import calendar as cal_module

try:
    import numpy as np
    _HAS_NP = True
except ImportError:
    _HAS_NP = False

from config import SCORE_INTERVAL, SESSION_GAP_SEC


class DataManager:
    def __init__(self, filepath):
        self.filepath = filepath
        self._lock    = threading.Lock()
        self.data     = self._load()
        self._img_dir = os.path.join(os.path.dirname(filepath), "alert_images")

    # ── persistence ──────────────────────────────────────────────────────────
    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def _ensure_day(self, date_str):
        if date_str not in self.data:
            self.data[date_str] = {"sessions": [], "alerts": []}
        else:
            self.data[date_str].setdefault("alerts", [])

    # ── score recording ───────────────────────────────────────────────────────
    def add_score(self, score, grade_label):
        today    = date.today().isoformat()
        now      = datetime.now()
        time_str = now.strftime("%H:%M:%S")
        with self._lock:
            self._ensure_day(today)
            sessions = self.data[today]["sessions"]
            if sessions:
                last        = sessions[-1]
                last_scores = last.get("scores", [])
                if last_scores:
                    last_t = datetime.strptime(
                        f"{today} {last_scores[-1]['time']}", "%Y-%m-%d %H:%M:%S"
                    )
                    if (now - last_t).total_seconds() < SESSION_GAP_SEC:
                        last_scores.append({"time": time_str, "score": score, "grade": grade_label})
                        start_t = datetime.strptime(
                            f"{today} {last['start']}", "%Y-%m-%d %H:%M:%S"
                        )
                        last["duration"] = int((now - start_t).total_seconds())
                        self._save()
                        return
            sessions.append({
                "start":    time_str,
                "duration": 0,
                "scores":   [{"time": time_str, "score": score, "grade": grade_label}],
            })
            self._save()

    # ── alert recording ───────────────────────────────────────────────────────
    def add_alert(self, message, severity, frame=None, snapshot=None):
        today = date.today().isoformat()
        now   = datetime.now()

        # 이미지 저장 (락 밖에서 IO)
        img_path = None
        if frame is not None:
            try:
                img_path = self._save_alert_image(frame, now)
            except Exception:
                pass

        entry = {"time": now.strftime("%H:%M"), "message": message, "severity": severity}
        if img_path:
            entry["img_path"] = img_path
        if snapshot:
            for k in ("score", "axis1", "axis2", "axis3", "axis4",
                      "neck_flexion", "forward_dist", "lateral_tilt", "shoulder_tilt"):
                if snapshot.get(k) is not None:
                    entry[k] = snapshot[k]

        with self._lock:
            self._ensure_day(today)
            self.data[today]["alerts"].append(entry)
            self._save()

    def _save_alert_image(self, frame, dt):
        import cv2
        os.makedirs(self._img_dir, exist_ok=True)
        fname = dt.strftime("alert_%Y%m%d_%H%M%S.jpg")
        path  = os.path.join(self._img_dir, fname)
        h, w  = frame.shape[:2]
        if w > 320:
            frame = cv2.resize(frame, (320, int(h * 320 / w)))
        cv2.imwrite(path, frame)
        return path

    def get_all_alerts(self):
        """모든 날짜의 알림을 [{date, ...}] 형태로 반환."""
        with self._lock:
            result = []
            for date_str, day_data in self.data.items():
                for alert in day_data.get("alerts", []):
                    result.append({"date": date_str, **alert})
            return result

    def get_day_alerts(self, date_str):
        with self._lock:
            if date_str not in self.data:
                return []
            return list(reversed(self.data[date_str].get("alerts", [])))

    # ── summaries ─────────────────────────────────────────────────────────────
    def get_day_summary(self, date_str):
        with self._lock:
            if date_str not in self.data:
                return None
            all_scores, total_dur = [], 0
            for s in self.data[date_str].get("sessions", []):
                all_scores.extend(e["score"] for e in s.get("scores", []))
                total_dur += s.get("duration", 0)
            if not all_scores:
                return None
            avg = sum(all_scores) / len(all_scores)
            good_count = sum(1 for sc in all_scores if sc == 1)  # 적정 등급
            return {
                "avg_score":        avg,
                "total_duration":   total_dur,
                "good_posture_sec": good_count * SCORE_INTERVAL,
                "alert_count":      len(self.data[date_str].get("alerts", [])),
                "sessions":         self.data[date_str].get("sessions", []),
            }

    def get_hourly_scores(self, date_str):
        """Returns {hour_int: avg_score} for each hour that has data."""
        with self._lock:
            if date_str not in self.data:
                return {}
            hourly = {}
            for session in self.data[date_str].get("sessions", []):
                for entry in session.get("scores", []):
                    hour = int(entry["time"].split(":")[0])
                    hourly.setdefault(hour, []).append(entry["score"])
            return {h: sum(v) / len(v) for h, v in hourly.items()}

    def get_month_data(self, year, month):
        result = {}
        for day in range(1, 32):
            try:
                d_str   = date(year, month, day).isoformat()
                summary = self.get_day_summary(d_str)
                if summary:
                    result[day] = summary
            except ValueError:
                break
        return result
