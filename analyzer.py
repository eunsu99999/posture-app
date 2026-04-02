import math
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
        self.ref_values      = {"vertical": None, "shoulder_w": None, "forward": None}
        self.calibrated      = False
        self.calib_data      = []
        self.calib_time      = 5
        self.shoulder_buffer = deque(maxlen=20)
        self.nose_buffer     = deque(maxlen=20)
        self.eye_buffer      = deque(maxlen=20)  # (eye_dy, eye_dx) 스무딩용
        self.forward_buffer  = deque(maxlen=20)  # 머리 앞돌출 z거리 스무딩용
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
        self.eye_buffer.clear()
        self.forward_buffer.clear()
        self.calib_start = time.time()

    # ── landmark analysis ─────────────────────────────────────────────────────
    def _analyze_landmarks(self, landmarks, world_landmarks, w, h):
        nose           = landmarks[self.mp_pose.PoseLandmark.NOSE]
        left_shoulder  = landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER]
        left_eye       = landmarks[self.mp_pose.PoseLandmark.LEFT_EYE]
        right_eye      = landmarks[self.mp_pose.PoseLandmark.RIGHT_EYE]

        self.nose_buffer.append((nose.x * w, nose.y * h))
        self.shoulder_buffer.append((
            (left_shoulder.x + right_shoulder.x) / 2 * w,
            (left_shoulder.y + right_shoulder.y) / 2 * h,
        ))
        # 눈~눈 선: 오른쪽눈 y - 왼쪽눈 y (머리 기울기 방향)
        self.eye_buffer.append((
            (right_eye.y - left_eye.y) * h,
            (right_eye.x - left_eye.x) * w,
        ))

        nose_x     = float(np.mean([p[0] for p in self.nose_buffer]))
        nose_y     = float(np.mean([p[1] for p in self.nose_buffer]))
        shoulder_x = float(np.mean([p[0] for p in self.shoulder_buffer]))
        shoulder_y = float(np.mean([p[1] for p in self.shoulder_buffer]))

        eye_dy_avg = float(np.mean([e[0] for e in self.eye_buffer]))
        eye_dx_avg = float(np.mean([e[1] for e in self.eye_buffer]))

        shoulder_w = max(1.0, abs(left_shoulder.x - right_shoulder.x) * w)

        # 코~어깨 수직 거리 (픽셀)
        vertical_dist = shoulder_y - nose_y

        # 기울기 각도 (눈~눈 선)
        lateral_tilt = abs(math.degrees(math.atan2(eye_dy_avg, max(1.0, abs(eye_dx_avg)))))

        # 머리 앞돌출: world_landmarks z축 (코 z - 어깨 중간 z, 미터 단위)
        if world_landmarks is not None:
            nose_w = world_landmarks[self.mp_pose.PoseLandmark.NOSE]
            ls_w   = world_landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER]
            rs_w   = world_landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER]
            self.forward_buffer.append(
                nose_w.z - (ls_w.z + rs_w.z) / 2
            )
        forward_dist = float(np.mean(self.forward_buffer)) if self.forward_buffer else 0.0

        return vertical_dist, lateral_tilt, shoulder_w, forward_dist, \
               (int(nose_x), int(nose_y)), (int(shoulder_x), int(shoulder_y))

    def _calc_rula(self, vertical_dist, lateral_tilt, forward_dist=0.0):
        """RULA 목 점수 계산 (1~5). 낮을수록 좋음."""
        rv = self.ref_values.get("vertical")
        if rv is None:
            return 1

        delta = rv - vertical_dist   # 양수 = 머리가 기준보다 아래 (전방 굴곡)
        L = max(1.0, rv * 2.0)

        # 수직 굴곡각도
        if delta < 0:
            ratio = min(1.0, (-delta) / L)
            vert_angle  = math.degrees(math.acos(1.0 - ratio))
            is_extension = vert_angle > 10
        else:
            ratio = min(1.0, delta / L)
            vert_angle   = math.degrees(math.acos(1.0 - ratio))
            is_extension = False

        # 앞돌출 각도 (world z 기준)
        fwd_angle = 0.0
        ref_fwd = self.ref_values.get("forward")
        if ref_fwd is not None:
            fwd_delta = ref_fwd - forward_dist  # 양수 = 기준보다 앞으로 나옴
            if fwd_delta > 0:
                # 목 높이 약 0.15m 기준 atan2 로 각도 추정
                fwd_angle = math.degrees(math.atan2(fwd_delta, 0.15))

        if is_extension:
            neck_score = 4
        else:
            effective = max(vert_angle, fwd_angle)
            if effective <= 10:
                neck_score = 1
            elif effective <= 20:
                neck_score = 2
            else:
                neck_score = 3

        # 좌우 기울기 +1점
        lat_threshold = SENSITIVITY_PRESETS[self.sensitivity].get("lateral_threshold", 10)
        if lateral_tilt > lat_threshold:
            neck_score += 1

        return min(5, neck_score)

    def _send_alert(self, grade, label):
        now = time.time()
        if now - self.last_alert_time < self.alert_interval:
            return

        msg, severity = None, None
        if grade == "주의":
            msg, severity = "자세가 나빠지고 있습니다. 바르게 앉아주세요.", "warn"
        elif grade == "경고":
            msg, severity = "자세가 매우 나쁩니다. 즉시 교정해주세요.", "warn"
        elif grade == "위험":
            msg, severity = "거북목이 감지되었습니다! 즉시 자세를 교정해주세요.", "danger"

        if msg:
            self.last_alert_time = now
            if self._alert_callback:
                self._alert_callback(msg, severity)

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
            "neck_flexion":    None,
            "forward_dist":    None,   # 앞돌출 거리 (m)
            "lateral_tilt":    None,
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

        landmarks    = result.pose_landmarks.landmark
        world_lm     = result.pose_world_landmarks.landmark if result.pose_world_landmarks else None
        vd, lt, sw, fd, nose_pos, shoulder_pos = self._analyze_landmarks(landmarks, world_lm, w, h)
        state.update(detected=True, lateral_tilt=lt,
                     nose_pos=nose_pos, shoulder_pos=shoulder_pos)

        if not self.calibrated:
            elapsed   = time.time() - self.calib_start
            remaining = int(self.calib_time - elapsed)
            state["calib_remaining"] = max(0, remaining)
            if remaining > 0:
                self.calib_data.append((vd, lt, sw, fd))
                cv2.putText(frame, "Sit Straight!", (w // 2 - 130, 55),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 220, 220), 3)
                cv2.putText(frame, f"Calibrating... {remaining}s", (w // 2 - 145, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 200), 2)
                progress = int((self.calib_time - remaining) / self.calib_time * w)
                cv2.rectangle(frame, (0, h - 20), (w, h),        (40, 40, 40),  -1)
                cv2.rectangle(frame, (0, h - 20), (progress, h), (0, 220, 220), -1)
            else:
                stable = self.calib_data[-30:] if len(self.calib_data) >= 30 else self.calib_data
                self.ref_values["vertical"]   = float(np.mean([d[0] for d in stable]))
                self.ref_values["shoulder_w"] = float(np.mean([d[2] for d in stable]))
                self.ref_values["forward"]    = float(np.mean([d[3] for d in stable]))
                self.calibrated = True
                state["calibrated"] = True
        else:
            rv    = self.ref_values["vertical"]
            delta = rv - vd
            L     = max(1.0, rv * 2.0)
            if delta >= 0:
                neck_flex_deg = math.degrees(math.acos(1.0 - min(1.0, delta / L)))
            else:
                neck_flex_deg = -math.degrees(math.acos(1.0 - min(1.0, (-delta) / L)))
            state["neck_flexion"] = neck_flex_deg
            ref_fwd = self.ref_values.get("forward")
            state["forward_dist"] = (ref_fwd - fd) if ref_fwd is not None else 0.0

            rula         = self._calc_rula(vd, lt, fd)
            grade, label = score_grade(rula)
            self._send_alert(grade, label)

            col_bgr = {
                "#2ECC9A": (154, 204, 46),
                "#63B3ED": (237, 179, 99),
                "#F6AD55": (85,  173, 246),
                "#FC8181": (129, 129, 252),
            }.get(score_color(rula), (200, 200, 200))

            cv2.line(frame,   nose_pos,     shoulder_pos, col_bgr, 3)
            cv2.circle(frame, nose_pos,     10, col_bgr, -1)
            cv2.circle(frame, shoulder_pos, 10, col_bgr, -1)
            cv2.line(frame, (shoulder_pos[0], 0), (shoulder_pos[0], h), (80, 80, 80), 1)

            state.update(score=rula, grade=grade, label=label)

        return frame, state
