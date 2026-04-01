import cv2
import numpy as np
import time
from collections import deque

from config import SENSITIVITY_PRESETS, score_color, score_grade

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False


class PostureAnalyzer:
    def __init__(self, sensitivity="normal"):
        import mediapipe as mp
        self.mp_pose    = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7,
        )
        self.ref_values      = {"vertical": None, "lateral": None}
        self.calibrated      = False
        self.calib_data      = []
        self.calib_time      = 5
        self.shoulder_buffer = deque(maxlen=20)
        self.nose_buffer     = deque(maxlen=20)
        self.last_alert_time = 0
        self.alert_interval  = 30
        self.calib_start     = time.time()
        self.sensitivity     = sensitivity
        self._alert_callback = None  # optional: fn(message, severity)

    def set_sensitivity(self, sensitivity):
        self.sensitivity = sensitivity

    def set_alert_callback(self, callback):
        """Set a callback fn(message: str, severity: str) called when alert fires."""
        self._alert_callback = callback

    def start_calibration(self):
        self.calibrated = False
        self.calib_data = []
        self.shoulder_buffer.clear()
        self.nose_buffer.clear()
        self.calib_start = time.time()

    # ── landmark analysis ─────────────────────────────────────────────────────
    def _analyze_landmarks(self, landmarks, w, h):
        nose           = landmarks[self.mp_pose.PoseLandmark.NOSE]
        left_shoulder  = landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER]

        self.nose_buffer.append((int(nose.x * w), int(nose.y * h)))
        self.shoulder_buffer.append((
            int((left_shoulder.x + right_shoulder.x) / 2 * w),
            int((left_shoulder.y + right_shoulder.y) / 2 * h),
        ))

        nose_x     = int(np.mean([p[0] for p in self.nose_buffer]))
        nose_y     = int(np.mean([p[1] for p in self.nose_buffer]))
        shoulder_x = int(np.mean([p[0] for p in self.shoulder_buffer]))
        shoulder_y = int(np.mean([p[1] for p in self.shoulder_buffer]))

        shoulder_w     = max(1.0, abs(left_shoulder.x - right_shoulder.x) * w)
        lateral_ratio  = abs(nose_x - shoulder_x) / shoulder_w
        vertical_ratio = (shoulder_y - nose_y) / h

        return vertical_ratio, lateral_ratio, (nose_x, nose_y), (shoulder_x, shoulder_y)

    def _calc_score(self, vertical_ratio, lateral_ratio):
        rv     = self.ref_values["vertical"]
        rl     = self.ref_values["lateral"]
        preset = SENSITIVITY_PRESETS[self.sensitivity]
        v_mult = preset["v_mult"]
        l_mult = preset["l_mult"]

        # neck / forward lean — higher v_mult = more sensitive
        v_change = (rv - vertical_ratio) / max(rv, 0.001) * 100
        v_score  = max(0, 50 - v_change * v_mult)

        # lateral tilt — lower l_mult = less sensitive
        l_change = (lateral_ratio - rl) * 100
        l_score  = max(0, 50 - l_change * l_mult)

        return min(100, int(v_score + l_score))

    def _send_alert(self, grade, label):
        now = time.time()
        if now - self.last_alert_time < self.alert_interval:
            return

        msg, severity = None, None
        if grade == "C":
            msg, severity = "자세가 나빠지고 있습니다. 바르게 앉아주세요.", "warn"
        elif grade == "D":
            msg, severity = "거북목이 감지되었습니다! 즉시 자세를 교정해주세요.", "danger"

        if msg:
            self.last_alert_time = now
            if self._alert_callback:
                self._alert_callback(msg, severity)
            if PLYER_AVAILABLE:
                try:
                    notification.notify(
                        title=f"Posture {grade}  ({label})",
                        message=msg,
                        timeout=5,
                    )
                except Exception:
                    pass

    # ── main processing ───────────────────────────────────────────────────────
    def process_frame(self, frame):
        h, w   = frame.shape[:2]
        rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.pose.process(rgb)

        state = {
            "detected":        False,
            "calibrated":      self.calibrated,
            "calib_remaining": 0,
            "score":           None,
            "grade":           None,
            "label":           None,
            "vertical_ratio":  None,
            "lateral_ratio":   None,
            "nose_pos":        None,
            "shoulder_pos":    None,
        }

        if not result.pose_landmarks:
            return frame, state

        self.mp_drawing.draw_landmarks(
            frame, result.pose_landmarks, self.mp_pose.POSE_CONNECTIONS,
            self.mp_drawing.DrawingSpec(color=(120, 120, 255), thickness=2, circle_radius=3),
            self.mp_drawing.DrawingSpec(color=(60,  60,  200), thickness=2),
        )

        landmarks = result.pose_landmarks.landmark
        vr, lr, nose_pos, shoulder_pos = self._analyze_landmarks(landmarks, w, h)
        state.update(detected=True, vertical_ratio=vr, lateral_ratio=lr,
                     nose_pos=nose_pos, shoulder_pos=shoulder_pos)

        if not self.calibrated:
            elapsed   = time.time() - self.calib_start
            remaining = int(self.calib_time - elapsed)
            state["calib_remaining"] = max(0, remaining)
            if remaining > 0:
                self.calib_data.append((vr, lr))
                cv2.putText(frame, "Sit Straight!", (w // 2 - 130, 55),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 220, 220), 3)
                cv2.putText(frame, f"Calibrating... {remaining}s", (w // 2 - 145, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 200), 2)
                progress = int((self.calib_time - remaining) / self.calib_time * w)
                cv2.rectangle(frame, (0, h - 20), (w, h),        (40, 40, 40),  -1)
                cv2.rectangle(frame, (0, h - 20), (progress, h), (0, 220, 220), -1)
            else:
                self.ref_values["vertical"] = float(np.mean([d[0] for d in self.calib_data]))
                self.ref_values["lateral"]  = float(np.mean([d[1] for d in self.calib_data]))
                self.calibrated = True
                state["calibrated"] = True
        else:
            score        = self._calc_score(vr, lr)
            grade, label = score_grade(score)
            self._send_alert(grade, label)

            # BGR overlay colour per score
            col_bgr = {
                "#2ECC9A": (154, 204, 46),
                "#63B3ED": (237, 179, 99),
                "#F6AD55": (85,  173, 246),
                "#FC8181": (129, 129, 252),
            }.get(score_color(score), (200, 200, 200))

            cv2.line(frame,   nose_pos,     shoulder_pos, col_bgr, 3)
            cv2.circle(frame, nose_pos,     10, col_bgr, -1)
            cv2.circle(frame, shoulder_pos, 10, col_bgr, -1)
            cv2.line(frame, (shoulder_pos[0], 0), (shoulder_pos[0], h), (80, 80, 80), 1)

            state.update(score=score, grade=grade, label=label)

        return frame, state
