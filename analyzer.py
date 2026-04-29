import math
import cv2
import numpy as np
import time
from collections import deque

from config import score_color, score_grade

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False


class PostureAnalyzer:
    def __init__(self):
        import mediapipe as mp
        self.mp_pose    = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            model_complexity=0,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7,
        )
        self.ref_values      = {"vertical": None, "shoulder_w": None, "eye_w": None}
        self.calibrated      = False
        self.calib_data      = []
        self.calib_time      = 5
        self.shoulder_buffer = deque(maxlen=20)
        self.nose_buffer     = deque(maxlen=20)
        self.eye_buffer      = deque(maxlen=20)  # (eye_dy, eye_dx) 스무딩용
        self.eye_w_buffer    = deque(maxlen=20)  # 눈 사이 거리 스무딩용
        self.last_alert_time = 0
        self.alert_interval  = 30
        self.calib_start     = time.time()
        self._alert_callback = None  # optional: fn(message, severity)

    def set_alert_callback(self, callback):
        """Set a callback fn(message: str, severity: str) called when alert fires."""
        self._alert_callback = callback

    def start_calibration(self):
        self.calibrated = False
        self.calib_data = []
        self.shoulder_buffer.clear()
        self.nose_buffer.clear()
        self.eye_buffer.clear()
        self.eye_w_buffer.clear()
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
        self.eye_w_buffer.append(max(1.0, abs(left_eye.x - right_eye.x) * w))
        eye_w = float(np.mean(self.eye_w_buffer))

        # 코~어깨 수직 거리 (픽셀)
        vertical_dist = shoulder_y - nose_y

        # 기울기 각도 (눈~눈 선)
        lateral_tilt = abs(math.degrees(math.atan2(eye_dy_avg, max(1.0, abs(eye_dx_avg)))))

        # 어깨 기울어짐 각도 (양쪽 어깨 y좌표 차이)
        sh_dy = abs(left_shoulder.y - right_shoulder.y) * h
        sh_dx = abs(left_shoulder.x - right_shoulder.x) * w
        shoulder_tilt = abs(math.degrees(math.atan2(sh_dy, max(1.0, sh_dx))))

        # 목 굴곡 raw 각도: 눈 중점 → 입 중점 벡터의 Y, Z 성분으로 얼굴 피치 측정
        neck_angle_raw = 0.0
        if world_landmarks is not None:
            le_w  = world_landmarks[self.mp_pose.PoseLandmark.LEFT_EYE]
            re_w  = world_landmarks[self.mp_pose.PoseLandmark.RIGHT_EYE]
            ml_w  = world_landmarks[self.mp_pose.PoseLandmark.MOUTH_LEFT]
            mr_w  = world_landmarks[self.mp_pose.PoseLandmark.MOUTH_RIGHT]
            eye_mid_y   = (le_w.y + re_w.y) / 2
            eye_mid_z   = (le_w.z + re_w.z) / 2
            mouth_mid_y = (ml_w.y + mr_w.y) / 2
            mouth_mid_z = (ml_w.z + mr_w.z) / 2
            dy = mouth_mid_y - eye_mid_y   # 아래 방향이 양수
            dz = mouth_mid_z - eye_mid_z   # 입이 눈보다 앞으로 나올수록 양수
            neck_angle_raw = math.degrees(math.atan2(dz, max(0.001, dy)))

        return vertical_dist, lateral_tilt, shoulder_w, eye_w, shoulder_tilt, \
               (int(nose_x), int(nose_y)), (int(shoulder_x), int(shoulder_y)), neck_angle_raw

    def _calc_psi(self, neck_flex_deg, forward_dist, lateral_tilt, shoulder_tilt):
        """PSI 채점: 4축 독립 채점 후 가중 합산. 범위 5-18, 낮을수록 좋음.
        W1=2 (목 전방 기울기), W2=1 (머리 앞돌출), W3=1 (측방), W4=1 (어깨)
        """
        # 축1: 목 전방 기울기 (후신전은 정상 처리)
        if neck_flex_deg <= 10:
            axis1 = 1
        elif neck_flex_deg <= 20:
            axis1 = 2
        else:
            axis1 = 3

        # 축2: 머리 앞돌출 (귀 너비 비율, 양수 = 기준보다 가까워짐)
        fwd_r = max(0.0, forward_dist)
        if fwd_r <= 0.07:
            axis2 = 1
        elif fwd_r <= 0.15:
            axis2 = 2
        elif fwd_r <= 0.25:
            axis2 = 3
        else:
            axis2 = 4

        # 축3: 측방 기울기 (도)
        if lateral_tilt <= 5:
            axis3 = 1
        elif lateral_tilt <= 10:
            axis3 = 2
        elif lateral_tilt <= 15:
            axis3 = 3
        else:
            axis3 = 4

        # 축4: 어깨 기울어짐 (도)
        if shoulder_tilt <= 3:
            axis4 = 1
        elif shoulder_tilt <= 6:
            axis4 = 2
        elif shoulder_tilt <= 9:
            axis4 = 3
        else:
            axis4 = 4

        total = (axis1 * 2) + axis2 + axis3 + axis4
        return total, axis1, axis2, axis3, axis4

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
            "forward_dist":    None,   # 머리 앞돌출 비율 (귀 너비 기준)
            "lateral_tilt":    None,
            "shoulder_tilt":   None,
            "axis1": None, "axis2": None, "axis3": None, "axis4": None,
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
        vd, lt, sw, fd, st, nose_pos, shoulder_pos, neck_angle_raw = self._analyze_landmarks(landmarks, world_lm, w, h)
        state.update(detected=True, lateral_tilt=lt, shoulder_tilt=st,
                     nose_pos=nose_pos, shoulder_pos=shoulder_pos)

        if not self.calibrated:
            elapsed   = time.time() - self.calib_start
            remaining = int(self.calib_time - elapsed)
            state["calib_remaining"] = max(0, remaining)
            if remaining > 0:
                self.calib_data.append((vd, lt, sw, fd, neck_angle_raw))
                cv2.putText(frame, "Sit Straight!", (w // 2 - 130, 55),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 220, 220), 3)
                cv2.putText(frame, f"Calibrating... {remaining}s", (w // 2 - 145, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 200), 2)
                progress = int((self.calib_time - remaining) / self.calib_time * w)
                cv2.rectangle(frame, (0, h - 20), (w, h),        (40, 40, 40),  -1)
                cv2.rectangle(frame, (0, h - 20), (progress, h), (0, 220, 220), -1)
            else:
                stable = self.calib_data[-30:] if len(self.calib_data) >= 30 else self.calib_data
                self.ref_values["vertical"]    = float(np.mean([d[0] for d in stable]))
                self.ref_values["shoulder_w"]  = float(np.mean([d[2] for d in stable]))
                self.ref_values["eye_w"]       = float(np.mean([d[3] for d in stable]))
                self.ref_values["neck_angle"]  = float(np.mean([d[4] for d in stable]))
                self.calibrated = True
                state["calibrated"] = True
        else:
            # 목 굴곡도: world_landmarks 기반 atan2 각도 - 기준 설정값
            ref_neck      = self.ref_values.get("neck_angle", 0.0)
            neck_flex_deg = neck_angle_raw - ref_neck
            state["neck_flexion"] = neck_flex_deg

            ref_ear = self.ref_values.get("eye_w")
            fwd_dist = ((fd - ref_ear) / ref_ear) if ref_ear else 0.0
            state["forward_dist"] = fwd_dist

            psi, ax1, ax2, ax3, ax4 = self._calc_psi(neck_flex_deg, fwd_dist, lt, st)
            grade, label = score_grade(psi)
            state.update(axis1=ax1, axis2=ax2, axis3=ax3, axis4=ax4)
            self._send_alert(grade, label)

            col_bgr = {
                "#2ECC9A": (154, 204, 46),
                "#63B3ED": (237, 179, 99),
                "#F6AD55": (85,  173, 246),
                "#FC8181": (129, 129, 252),
                "#E53E3E": (62,   62, 229),
            }.get(score_color(psi), (200, 200, 200))

            cv2.line(frame,   nose_pos,     shoulder_pos, col_bgr, 3)
            cv2.circle(frame, nose_pos,     10, col_bgr, -1)
            cv2.circle(frame, shoulder_pos, 10, col_bgr, -1)
            cv2.line(frame, (shoulder_pos[0], 0), (shoulder_pos[0], h), (80, 80, 80), 1)

            state.update(score=psi, grade=grade, label=label)

        return frame, state
