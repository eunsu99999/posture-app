import math
import cv2
import numpy as np
import time
from collections import deque

from config import score_color, score_grade, NECK_SLOPE, NECK_OFFSET, FWDIST_SLOPE, FWDIST_OFFSET

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False


import threading as _threading

_mp_path_lock  = _threading.Lock()
_mp_path_fixed = False


def _ensure_ascii_mediapipe_path():
    """mediapipe의 C++ 리소스 로더는 경로에 비ASCII(예: 한글) 문자가 있으면
    모델/그래프 파일(.tflite/.binarypb)을 열지 못해 FileNotFoundError를 낸다.
    PyInstaller 동결 빌드가 한글 폴더명이나 한글 Windows 사용자명 경로에 설치되면
    이 문제가 발생한다(파이썬 import는 유니코드 경로를 처리하므로 import 자체는 됨).

    해결: 동결 빌드의 경로(_MEIPASS)가 비ASCII이면 mediapipe/modules 데이터를 항상
    ASCII인 위치(C:\\Users\\Public\\PostureApp)로 한 번 복사하고, solution_base.__file__을
    그쪽으로 바꿔 mediapipe가 ASCII 경로에서 리소스를 찾게 한다. 경로가 이미 ASCII면
    아무것도 하지 않는다."""
    global _mp_path_fixed
    import sys, os
    if not (getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")):
        return
    meipass = sys._MEIPASS
    try:
        meipass.encode("ascii")
        return  # 경로가 이미 ASCII → mediapipe 정상 동작, 복사 불필요
    except UnicodeEncodeError:
        pass
    with _mp_path_lock:
        if _mp_path_fixed:
            return
        import shutil
        public     = os.environ.get("PUBLIC") or r"C:\Users\Public"
        ascii_root = os.path.join(public, "PostureApp")
        src = os.path.join(meipass, "mediapipe", "modules")
        dst = os.path.join(ascii_root, "mediapipe", "modules")
        marker = os.path.join(dst, "pose_landmark", "pose_landmark_cpu.binarypb")
        if not os.path.exists(marker):
            os.makedirs(os.path.join(ascii_root, "mediapipe"), exist_ok=True)
            shutil.copytree(src, dst, dirs_exist_ok=True)
        import mediapipe.python.solution_base as _sb
        _sb.__file__ = os.path.join(ascii_root, "mediapipe", "python", "solution_base.py")
        _mp_path_fixed = True


class PostureAnalyzer:
    def __init__(self):
        _ensure_ascii_mediapipe_path()
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
        self.eye_w_buffer    = deque(maxlen=40)  # 눈 사이 거리 스무딩용 (앞돌출 노이즈 억제)
        self.last_alert_time = 0
        self.alert_interval  = 30
        self.calib_start     = time.time()
        self._alert_callback = None  # optional: fn(message, severity)
        # 머리 앞돌출 관리도(SPC) 기준값 — 캘리브레이션 종료 시 설정
        self.fwd_mu0    = 0.0
        self.fwd_sigma0 = 1.0
        # 4초 유지 규칙(ISO 11226 정적 자세): 새 종합 등급이 HOLD_SECONDS 이상
        # 지속될 때만 state의 종합 등급/원인을 바꾼다
        self.HOLD_SECONDS     = 4.0
        self._committed_grade = 1      # 현재 반영된 종합 등급(1~3)
        self._committed_worst = None   # 현재 반영된 원인 축 키
        self._pending_grade   = None   # 바뀌려고 대기 중인 등급
        self._pending_since   = 0.0

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
        self._committed_grade = 1
        self._committed_worst = None
        self._pending_grade   = None
        self._pending_since   = 0.0

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

    def _judge_axes(self, neck_flex_deg, forward_cm_raw, lateral_tilt, shoulder_tilt):
        """각 축을 1(적정)/2(주의)/3(부적정)으로 독립 판정하고, 종합 등급은
        가장 나쁜 축의 등급(최댓값)으로 한다. 가중치·합산 없음.
        반환: (종합등급, a1, a2, a3, a4, 원인축키)

        근거 기반 임계값:
        - 목 굴곡    : ≤10° 적정 / ≤20° 주의 / >20° 부적정   [RULA, McAtamney & Corlett 1993]
        - 머리 앞돌출: ≤ mu0+3σ 적정 / 초과 부적정 (관리도 SPC)
        - 측방 기울기: ≤10° 적정 / >10° 부적정               [EN 1005-4]
        - 어깨 기울기: ≤10° 적정 / ≤20° 주의 / >20° 부적정   [ISO 11226 몸통 측굴 근사]
        동률 시 원인축 우선순위: 목 > 앞돌출 > 측방 > 어깨
        """
        # 축1: 목 굴곡 (보정식 적용된 값, 3단계)
        if neck_flex_deg <= 10:
            a1 = 1
        elif neck_flex_deg <= 20:
            a1 = 2
        else:
            a1 = 3

        # 축2: 머리 앞돌출 — 관리도(SPC), clamp 안 한 cm 값으로 비교 (2단계)
        a2 = 1 if forward_cm_raw <= (self.fwd_mu0 + 3.0 * self.fwd_sigma0) else 3

        # 축3: 측방 기울기 (2단계)
        a3 = 1 if lateral_tilt <= 10 else 3

        # 축4: 어깨 기울기 (3단계)
        if shoulder_tilt <= 10:
            a4 = 1
        elif shoulder_tilt <= 20:
            a4 = 2
        else:
            a4 = 3

        worst = max(a1, a2, a3, a4)
        if   a1 == worst: cause = "neck"
        elif a2 == worst: cause = "forward"
        elif a3 == worst: cause = "lateral"
        else:             cause = "shoulder"
        return worst, a1, a2, a3, a4, cause

    def _apply_hold(self, inst_grade, inst_cause, now):
        """4초 유지 규칙: 새 종합 등급이 HOLD_SECONDS 이상 지속될 때만 반영한다.
        반환: (반영된 종합등급, 반영된 원인축키)"""
        if inst_grade == self._committed_grade:
            # 같은 등급 유지 → 원인 축만 최신화하고 대기 해제
            self._committed_worst = inst_cause if inst_grade > 1 else None
            self._pending_grade   = None
        else:
            if inst_grade != self._pending_grade:
                self._pending_grade = inst_grade
                self._pending_since = now
            if now - self._pending_since >= self.HOLD_SECONDS:
                self._committed_grade = inst_grade
                self._committed_worst = inst_cause if inst_grade > 1 else None
                self._pending_grade   = None
        return self._committed_grade, self._committed_worst

    def _send_alert(self, grade, cause, snapshot=None):
        now = time.time()
        if now - self.last_alert_time < self.alert_interval:
            return

        msg, severity = None, None
        if grade == "주의":
            msg, severity = "자세가 나빠지고 있습니다. 바르게 앉아주세요.", "warn"
        elif grade == "부적정":
            if cause == "neck":
                msg, severity = "거북목이 감지되었습니다! 즉시 자세를 교정해주세요.", "danger"
            else:
                msg, severity = "자세가 부적정합니다. 즉시 교정해주세요.", "danger"

        if msg:
            self.last_alert_time = now
            if self._alert_callback:
                self._alert_callback(msg, severity, snapshot=snapshot)

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
            "forward_dist":    None,   # 머리 앞돌출 (cm, 표시용)
            "lateral_tilt":    None,
            "shoulder_tilt":   None,
            "axis1": None, "axis2": None, "axis3": None, "axis4": None,  # 축별 등급(1~3)
            "worst_axis":      None,   # 종합 등급의 원인 축 키 (neck/forward/lateral/shoulder)
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
                # 머리 앞돌출 관리도(SPC) 기준: stable 프레임의 clamp 안 한 cm 분포
                ref_eye = self.ref_values["eye_w"]
                cms = [FWDIST_SLOPE * ((d[3] - ref_eye) / ref_eye) + FWDIST_OFFSET
                       for d in stable] if ref_eye else [0.0]
                self.fwd_mu0    = float(np.mean(cms))
                self.fwd_sigma0 = max(1.0, float(np.std(cms)))  # 최소 1.0cm (초음파 검증 최대 오차)
                self.calibrated = True
                state["calibrated"] = True
        else:
            # 목 굴곡도: world_landmarks 기반 atan2 각도 - 기준 설정값
            # 선형 보정 적용: 실제각도 = NECK_SLOPE × raw + NECK_OFFSET
            ref_neck      = self.ref_values.get("neck_angle", 0.0)
            raw_flex      = neck_angle_raw - ref_neck
            neck_flex_deg = raw_flex * NECK_SLOPE + NECK_OFFSET
            state["neck_flexion"] = neck_flex_deg

            ref_ear  = self.ref_values.get("eye_w")
            fwd_ratio = ((fd - ref_ear) / ref_ear) if ref_ear else 0.0
            # 판정용: clamp 안 한 실제 cm 값 (관리도 비교용, 음수 허용)
            forward_cm_raw = FWDIST_SLOPE * fwd_ratio + FWDIST_OFFSET
            # 표시용: 기존과 동일하게 음수 clamp
            fwd_dist = max(0.0, FWDIST_SLOPE * max(0.0, fwd_ratio) + FWDIST_OFFSET)
            state["forward_dist"] = fwd_dist

            # 4개 축 독립 판정(1~3) → 종합은 가장 나쁜 축, 원인 축 산출
            inst, ax1, ax2, ax3, ax4, cause = self._judge_axes(
                neck_flex_deg, forward_cm_raw, lt, st)
            state.update(axis1=ax1, axis2=ax2, axis3=ax3, axis4=ax4)
            # 4초 유지 규칙으로 종합 등급/원인 확정
            score, worst = self._apply_hold(inst, cause, time.time())
            grade, label = score_grade(score)
            state["worst_axis"] = worst

            snapshot = {
                "score":        score,
                "axis1":        ax1,       "axis2":        ax2,
                "axis3":        ax3,       "axis4":        ax4,
                "worst_axis":   worst,
                "neck_flexion": neck_flex_deg,
                "forward_dist": fwd_dist,
                "lateral_tilt": lt,
                "shoulder_tilt": st,
            }
            self._send_alert(grade, worst, snapshot=snapshot)

            col_bgr = {
                "#2ECC9A": (154, 204, 46),
                "#F6AD55": (85,  173, 246),
                "#FC8181": (129, 129, 252),
            }.get(score_color(score), (200, 200, 200))

            cv2.line(frame,   nose_pos,     shoulder_pos, col_bgr, 3)
            cv2.circle(frame, nose_pos,     10, col_bgr, -1)
            cv2.circle(frame, shoulder_pos, 10, col_bgr, -1)
            cv2.line(frame, (shoulder_pos[0], 0), (shoulder_pos[0], h), (80, 80, 80), 1)

            state.update(score=score, grade=grade, label=label)

        return frame, state
