import cv2
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk
import threading
import json
import os
import time
from datetime import datetime, date
from collections import deque
import calendar as cal_module

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates

# ── 경로 / 설정 ─────────────────────────────────────────────────────────────────
DATA_DIR  = r"C:\storage\med"
DATA_FILE = os.path.join(DATA_DIR, "posture_data.json")

# ── 다크 테마 팔레트 ────────────────────────────────────────────────────────────
BG_DARK    = "#0d1117"
BG_PANEL   = "#161b22"
BG_CARD    = "#21262d"
ACCENT_BLU = "#1f6feb"
TEXT_PRI   = "#e6edf3"
TEXT_SEC   = "#8b949e"
CLR_GOOD   = "#3fb950"
CLR_WARN   = "#d29922"
CLR_DANGER = "#f85149"
CLR_BLUE   = "#58a6ff"
CLR_BORDER = "#30363d"

SCORE_INTERVAL  = 5    # 데이터 저장 주기(초)
CAM_DISPLAY_W   = 560  # 카메라 표시 너비
SESSION_GAP_SEC = 120  # 이 시간 이상 공백이면 새 세션으로 간주


# ── 점수 → 색상 ─────────────────────────────────────────────────────────────────
def score_color(score):
    if score >= 80: return CLR_GOOD
    if score >= 60: return CLR_BLUE
    if score >= 40: return CLR_WARN
    return CLR_DANGER


def score_grade(score):
    if score >= 80: return "A", "Perfect!"
    if score >= 60: return "B", "Good"
    if score >= 40: return "C", "Warning"
    return "D", "Danger!"


# ══════════════════════════════════════════════════════════════════════════════
# DataManager  ─ JSON 저장 / 조회
# ══════════════════════════════════════════════════════════════════════════════
class DataManager:
    def __init__(self, filepath):
        self.filepath = filepath
        self._lock = threading.Lock()
        self.data = self._load()

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

    # 점수 한 개 기록
    def add_score(self, score, grade_label):
        today     = date.today().isoformat()
        now       = datetime.now()
        time_str  = now.strftime("%H:%M:%S")

        with self._lock:
            if today not in self.data:
                self.data[today] = {"sessions": []}

            sessions = self.data[today]["sessions"]

            # 마지막 세션이 SESSION_GAP_SEC 내면 이어붙임
            if sessions:
                last = sessions[-1]
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

            # 새 세션 시작
            sessions.append({
                "start":    time_str,
                "duration": 0,
                "scores":   [{"time": time_str, "score": score, "grade": grade_label}]
            })
            self._save()

    # 하루 요약 반환
    def get_day_summary(self, date_str):
        with self._lock:
            if date_str not in self.data:
                return None
            all_scores, total_dur = [], 0
            for s in self.data[date_str]["sessions"]:
                all_scores.extend(e["score"] for e in s.get("scores", []))
                total_dur += s.get("duration", 0)
            if not all_scores:
                return None
            return {
                "avg_score":      float(np.mean(all_scores)),
                "total_duration": total_dur,
                "sessions":       self.data[date_str]["sessions"],
            }

    # 특정 월의 날짜별 요약 반환
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


# ══════════════════════════════════════════════════════════════════════════════
# PostureAnalyzer  ─ mediapipe 자세 분석
# ══════════════════════════════════════════════════════════════════════════════
class PostureAnalyzer:
    def __init__(self):
        import mediapipe as mp
        self.mp_pose    = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
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

    def start_calibration(self):
        self.calibrated = False
        self.calib_data = []
        self.shoulder_buffer.clear()
        self.nose_buffer.clear()
        self.calib_start = time.time()

    def _analyze_landmarks(self, landmarks, w, h):
        nose           = landmarks[self.mp_pose.PoseLandmark.NOSE]
        left_shoulder  = landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER]

        self.nose_buffer.append((int(nose.x * w), int(nose.y * h)))
        self.shoulder_buffer.append((
            int((left_shoulder.x + right_shoulder.x) / 2 * w),
            int((left_shoulder.y + right_shoulder.y) / 2 * h)
        ))

        nose_x     = int(np.mean([p[0] for p in self.nose_buffer]))
        nose_y     = int(np.mean([p[1] for p in self.nose_buffer]))
        shoulder_x = int(np.mean([p[0] for p in self.shoulder_buffer]))
        shoulder_y = int(np.mean([p[1] for p in self.shoulder_buffer]))

        shoulder_w = max(1.0, abs(left_shoulder.x - right_shoulder.x) * w)
        lateral_ratio  = abs(nose_x - shoulder_x) / shoulder_w
        vertical_ratio = (shoulder_y - nose_y) / h

        return vertical_ratio, lateral_ratio, (nose_x, nose_y), (shoulder_x, shoulder_y)

    def _calc_score(self, vertical_ratio, lateral_ratio):
        rv = self.ref_values["vertical"]
        rl = self.ref_values["lateral"]
        v_change = (rv - vertical_ratio) / rv * 100
        v_score  = max(0, 50 - v_change * 2)
        l_change = (lateral_ratio - rl) * 100
        l_score  = max(0, 50 - l_change * 3)
        return min(100, int(v_score + l_score))

    def _send_alert(self, grade):
        if not PLYER_AVAILABLE:
            return
        now = time.time()
        if now - self.last_alert_time < self.alert_interval:
            return
        if grade == "C":
            notification.notify(title="Posture Warning!",
                                 message="자세가 나빠지고 있습니다. 바르게 앉아주세요.", timeout=5)
            self.last_alert_time = now
        elif grade == "D":
            notification.notify(title="Posture Danger!",
                                 message="거북목이 감지되었습니다! 즉시 자세를 교정해주세요.", timeout=5)
            self.last_alert_time = now

    # 메인 처리: frame 을 받아 skeleton 그리고 state dict 반환
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

        # 스켈레톤 그리기
        self.mp_drawing.draw_landmarks(
            frame, result.pose_landmarks, self.mp_pose.POSE_CONNECTIONS,
            self.mp_drawing.DrawingSpec(color=(120, 120, 255), thickness=2, circle_radius=3),
            self.mp_drawing.DrawingSpec(color=(60, 60, 200),  thickness=2)
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
                # 캘리브레이션 오버레이
                cv2.putText(frame, "Sit Straight!", (w // 2 - 130, 55),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 220, 220), 3)
                cv2.putText(frame, f"Calibrating... {remaining}s", (w // 2 - 145, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 200), 2)
                progress = int((self.calib_time - remaining) / self.calib_time * w)
                cv2.rectangle(frame, (0, h - 20), (w, h),      (40, 40, 40),    -1)
                cv2.rectangle(frame, (0, h - 20), (progress, h), (0, 220, 220), -1)
            else:
                self.ref_values["vertical"] = float(np.mean([d[0] for d in self.calib_data]))
                self.ref_values["lateral"]  = float(np.mean([d[1] for d in self.calib_data]))
                self.calibrated = True
                state["calibrated"] = True
        else:
            score = self._calc_score(vr, lr)
            grade, label = score_grade(score)
            self._send_alert(grade)
            state.update(score=score, grade=grade, label=label)

            # 코~어깨 연결선 / 마커
            col_bgr = {
                CLR_GOOD:   (59, 185, 63),
                CLR_BLUE:   (255, 166, 88),
                CLR_WARN:   (34, 153, 210),
                CLR_DANGER: (81, 72, 248),
            }.get(score_color(score), (200, 200, 200))

            cv2.line(frame,   nose_pos,     shoulder_pos, col_bgr, 3)
            cv2.circle(frame, nose_pos,     10, col_bgr, -1)
            cv2.circle(frame, shoulder_pos, 10, col_bgr, -1)
            cv2.line(frame, (shoulder_pos[0], 0), (shoulder_pos[0], h), (80, 80, 80), 1)

        return frame, state


# ══════════════════════════════════════════════════════════════════════════════
# DetailGraph  ─ 특정 날짜의 시간대별 점수 그래프
# ══════════════════════════════════════════════════════════════════════════════
class DetailGraph(tk.Toplevel):
    THRESHOLD = 60

    def __init__(self, parent, data_manager, date_str):
        super().__init__(parent)
        self.title(f"Posture Detail  ─  {date_str}")
        self.configure(bg=BG_DARK)
        self.geometry("920x520")
        self.resizable(True, True)

        summary = data_manager.get_day_summary(date_str)
        if not summary:
            tk.Label(self, text="해당 날짜의 데이터가 없습니다.",
                     bg=BG_DARK, fg=TEXT_SEC, font=("Segoe UI", 14)).pack(expand=True)
            return

        self._build_info_bar(summary, date_str)
        self._build_graph(summary, date_str)

    def _build_info_bar(self, summary, date_str):
        bar = tk.Frame(self, bg=BG_PANEL, pady=9)
        bar.pack(fill="x")

        avg  = summary["avg_score"]
        dur  = summary["total_duration"]
        mins = dur // 60
        t_str = f"{mins // 60}시간 {mins % 60}분" if mins >= 60 else f"{mins}분"

        tk.Label(bar, text=date_str,            bg=BG_PANEL, fg=TEXT_PRI,
                 font=("Segoe UI", 13, "bold")).pack(side="left", padx=16)
        tk.Label(bar, text=f"평균 점수  {avg:.1f}점", bg=BG_PANEL,
                 fg=score_color(avg), font=("Segoe UI", 12, "bold")).pack(side="left", padx=20)
        tk.Label(bar, text=f"총 사용시간  {t_str}", bg=BG_PANEL, fg=TEXT_SEC,
                 font=("Segoe UI", 11)).pack(side="left", padx=16)
        n_sessions = len(summary["sessions"])
        tk.Label(bar, text=f"세션 {n_sessions}회", bg=BG_PANEL, fg=TEXT_SEC,
                 font=("Segoe UI", 10)).pack(side="right", padx=16)

    def _build_graph(self, summary, date_str):
        # 시간 / 점수 배열 수집
        all_times, all_scores = [], []
        for session in summary["sessions"]:
            for entry in session.get("scores", []):
                t = datetime.strptime(f"{date_str} {entry['time']}", "%Y-%m-%d %H:%M:%S")
                all_times.append(t)
                all_scores.append(entry["score"])

        fig = Figure(figsize=(9.2, 4.2), dpi=100, facecolor=BG_DARK)
        ax  = fig.add_subplot(111)
        ax.set_facecolor(BG_PANEL)
        fig.tight_layout(pad=2.5)

        if all_times:
            t_arr = np.array(all_times)
            s_arr = np.array(all_scores, dtype=float)
            thr   = self.THRESHOLD

            # ── 등급 배경 영역 ─────────────────────────────────────────────
            ax.axhspan(80, 105, alpha=0.06, color=CLR_GOOD,   zorder=0)
            ax.axhspan(60,  80, alpha=0.06, color=CLR_BLUE,   zorder=0)
            ax.axhspan(40,  60, alpha=0.06, color=CLR_WARN,   zorder=0)
            ax.axhspan(0,   40, alpha=0.06, color=CLR_DANGER, zorder=0)

            # ── 좋음 / 나쁨 채움 영역 (초록 / 빨강) ──────────────────────
            ax.fill_between(t_arr, s_arr, thr,
                            where=(s_arr >= thr),
                            alpha=0.35, color=CLR_GOOD,   interpolate=True,
                            label=f"Good (≥{thr}점)")
            ax.fill_between(t_arr, s_arr, thr,
                            where=(s_arr < thr),
                            alpha=0.35, color=CLR_DANGER, interpolate=True,
                            label=f"Poor (<{thr}점)")

            # ── 꺾은선 ──────────────────────────────────────────────────────
            ax.plot(t_arr, s_arr, color=CLR_BLUE, linewidth=1.8, zorder=5, label="Score")

            # ── 기준선 ──────────────────────────────────────────────────────
            ax.axhline(thr, color=CLR_WARN,   linestyle="--", linewidth=1.0,
                       alpha=0.8, label=f"Threshold {thr}")
            ax.axhline(80,  color=CLR_GOOD,   linestyle=":",  linewidth=1.0,
                       alpha=0.6, label="Perfect 80")

            # ── 세션 구분선 ─────────────────────────────────────────────────
            for session in summary["sessions"]:
                if session.get("scores"):
                    t0 = datetime.strptime(
                        f"{date_str} {session['scores'][0]['time']}", "%Y-%m-%d %H:%M:%S"
                    )
                    ax.axvline(t0, color=CLR_BORDER, linewidth=1.2,
                               linestyle="-.", alpha=0.7)

        # ── 축 스타일링 ────────────────────────────────────────────────────
        ax.set_ylim(0, 108)
        ax.set_ylabel("Posture Score", color=TEXT_SEC, fontsize=9)
        ax.set_xlabel("Time of Day",   color=TEXT_SEC, fontsize=9)
        ax.tick_params(colors=TEXT_SEC, labelsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        fig.autofmt_xdate(rotation=30)

        for spine in ax.spines.values():
            spine.set_edgecolor(CLR_BORDER)

        legend = ax.legend(
            facecolor=BG_CARD, edgecolor=CLR_BORDER,
            labelcolor=TEXT_SEC, fontsize=8, loc="lower right"
        )

        canvas = FigureCanvasTkAgg(fig, master=self)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=6)


# ══════════════════════════════════════════════════════════════════════════════
# CalendarView  ─ 월별 달력 + 날짜 요약
# ══════════════════════════════════════════════════════════════════════════════
class CalendarView(tk.Toplevel):
    CELL_W = 104
    CELL_H = 84

    def __init__(self, parent, data_manager):
        super().__init__(parent)
        self.data_manager = data_manager
        self.title("Posture History  ─  Calendar")
        self.configure(bg=BG_DARK)
        self.resizable(False, False)

        now = datetime.now()
        self.cur_year  = now.year
        self.cur_month = now.month

        self._build_chrome()
        self._render()

    def _build_chrome(self):
        # 상단 헤더
        hdr = tk.Frame(self, bg=BG_PANEL, pady=10)
        hdr.pack(fill="x")

        tk.Button(hdr, text="◀", bg=BG_CARD, fg=TEXT_PRI,
                  bd=0, padx=16, pady=4, cursor="hand2",
                  font=("Segoe UI", 11),
                  command=self._prev_month).pack(side="left", padx=10)

        self.month_lbl = tk.Label(hdr, text="", bg=BG_PANEL, fg=TEXT_PRI,
                                   font=("Segoe UI", 14, "bold"))
        self.month_lbl.pack(side="left", expand=True)

        tk.Button(hdr, text="▶", bg=BG_CARD, fg=TEXT_PRI,
                  bd=0, padx=16, pady=4, cursor="hand2",
                  font=("Segoe UI", 11),
                  command=self._next_month).pack(side="right", padx=10)

        # 범례
        legend = tk.Frame(self, bg=BG_DARK, pady=6)
        legend.pack(fill="x", padx=12)
        for label, color in [("A 80+", CLR_GOOD), ("B 60+", CLR_BLUE),
                              ("C 40+", CLR_WARN), ("D ~40", CLR_DANGER)]:
            tk.Label(legend, text="●", bg=BG_DARK, fg=color,
                     font=("Segoe UI", 12)).pack(side="left", padx=(6, 1))
            tk.Label(legend, text=label, bg=BG_DARK, fg=TEXT_SEC,
                     font=("Segoe UI", 9)).pack(side="left", padx=(0, 10))

        # 달력 그리드 컨테이너
        self.grid_frame = tk.Frame(self, bg=BG_DARK, padx=10, pady=8)
        self.grid_frame.pack(fill="both", expand=True)

    def _render(self):
        for w in self.grid_frame.winfo_children():
            w.destroy()

        self.month_lbl.config(
            text=f"{self.cur_year}년  {self.cur_month:02d}월"
        )

        # 요일 헤더
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for col, name in enumerate(day_names):
            c = CLR_DANGER if col == 6 else TEXT_SEC
            tk.Label(self.grid_frame, text=name, bg=BG_DARK, fg=c,
                     font=("Segoe UI", 9, "bold"),
                     width=13).grid(row=0, column=col, pady=(0, 4))

        month_data = self.data_manager.get_month_data(self.cur_year, self.cur_month)
        today      = date.today()
        weeks      = cal_module.monthcalendar(self.cur_year, self.cur_month)

        for week_r, week in enumerate(weeks, start=1):
            for col, day in enumerate(week):
                if day == 0:
                    spacer = tk.Frame(self.grid_frame, bg=BG_DARK,
                                      width=self.CELL_W, height=self.CELL_H)
                    spacer.grid(row=week_r, column=col, padx=3, pady=3)
                    continue

                is_today   = (day == today.day and
                              self.cur_month == today.month and
                              self.cur_year  == today.year)
                border_col = ACCENT_BLU if is_today else CLR_BORDER
                day_col    = ACCENT_BLU if is_today else (CLR_DANGER if col == 6 else TEXT_PRI)

                cell = tk.Frame(self.grid_frame, bg=BG_CARD,
                                width=self.CELL_W, height=self.CELL_H,
                                highlightbackground=border_col, highlightthickness=1)
                cell.grid(row=week_r, column=col, padx=3, pady=3)
                cell.pack_propagate(False)

                tk.Label(cell, text=str(day), bg=BG_CARD, fg=day_col,
                         font=("Segoe UI", 11, "bold")).pack(anchor="nw", padx=6, pady=4)

                if day in month_data:
                    summary = month_data[day]
                    avg     = summary["avg_score"]
                    dur     = summary["total_duration"]
                    mins    = dur // 60
                    t_str   = (f"{mins // 60}h {mins % 60}m" if mins >= 60
                               else f"{mins}m")
                    sc      = score_color(avg)

                    tk.Label(cell, text=f"{avg:.0f}점", bg=BG_CARD, fg=sc,
                             font=("Segoe UI", 10, "bold")).pack(anchor="center")
                    tk.Label(cell, text=t_str, bg=BG_CARD, fg=TEXT_SEC,
                             font=("Segoe UI", 8)).pack(anchor="center")

                    d_str = date(self.cur_year, self.cur_month, day).isoformat()
                    self._bind_click(cell, d_str)

    def _bind_click(self, cell, date_str):
        def handler(e=None):
            DetailGraph(self, self.data_manager, date_str)

        cell.config(cursor="hand2")
        cell.bind("<Button-1>", handler)
        for child in cell.winfo_children():
            child.config(cursor="hand2")
            child.bind("<Button-1>", handler)

    def _prev_month(self):
        if self.cur_month == 1:
            self.cur_month = 12; self.cur_year -= 1
        else:
            self.cur_month -= 1
        self._render()

    def _next_month(self):
        if self.cur_month == 12:
            self.cur_month = 1; self.cur_year += 1
        else:
            self.cur_month += 1
        self._render()


# ══════════════════════════════════════════════════════════════════════════════
# PostureApp  ─ 메인 tkinter 애플리케이션
# ══════════════════════════════════════════════════════════════════════════════
class PostureApp:
    def __init__(self, root: tk.Tk):
        self.root     = root
        self.root.title("Posture Monitor Pro")
        self.root.configure(bg=BG_DARK)

        self.data_manager  = DataManager(DATA_FILE)
        self.analyzer      = None

        self.running         = True
        self._frame_data     = None
        self._frame_lock     = threading.Lock()
        self.last_save_time  = 0.0
        self.session_start   = time.time()
        self.session_scores: list[int] = []

        self._build_ui()

        self.root.after(200, self._fix_window_size)

        self._init_thread = threading.Thread(target=self._init_analyzer, daemon=True)
        self._init_thread.start()

        self._cam_thread = threading.Thread(target=self._camera_loop, daemon=True)
        self._cam_thread.start()

        self._refresh_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _fix_window_size(self):
        # 버튼이 패널 아래로 잘리는 경우 창 높이를 자동으로 늘림
        btn_bottom = self.btn_frame.winfo_y() + self.btn_frame.winfo_reqheight()
        panel_h    = self.panel.winfo_height()
        if btn_bottom > panel_h:
            deficit = btn_bottom - panel_h + 10
            new_h   = self.root.winfo_height() + deficit
            self.root.geometry(f"{self.root.winfo_width()}x{new_h}")
        self.root.resizable(False, False)

    # ── UI 구성 ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── 타이틀 바 ─────────────────────────────────────────────────────────
        title_bar = tk.Frame(self.root, bg=BG_PANEL, pady=8)
        title_bar.pack(fill="x")

        tk.Label(title_bar, text="◉  POSTURE MONITOR PRO", bg=BG_PANEL,
                 fg=CLR_GOOD, font=("Segoe UI", 12, "bold")).pack(side="left", padx=14)

        self.status_lbl = tk.Label(title_bar, text="Starting…",
                                    bg=BG_PANEL, fg=TEXT_SEC, font=("Segoe UI", 10))
        self.status_lbl.pack(side="left", padx=10)

        tk.Label(title_bar, text=date.today().isoformat(),
                 bg=BG_PANEL, fg=TEXT_SEC, font=("Segoe UI", 10)).pack(side="right", padx=14)

        # ── 콘텐츠 영역 ───────────────────────────────────────────────────────
        content = tk.Frame(self.root, bg=BG_DARK)
        content.pack(fill="both", expand=True, padx=10, pady=10)

        # ── 왼쪽: 카메라 피드 ────────────────────────────────────────────────
        cam_frame = tk.Frame(content, bg=BG_PANEL,
                              highlightbackground=CLR_BORDER, highlightthickness=1)
        cam_frame.pack(side="left", fill="y")

        tk.Label(cam_frame, text="LIVE  FEED", bg=BG_PANEL, fg=TEXT_SEC,
                 font=("Segoe UI", 7, "bold")).pack(anchor="nw", padx=8, pady=(5, 2))

        cam_holder = tk.Frame(cam_frame, bg="#000000",
                              width=CAM_DISPLAY_W, height=420)
        cam_holder.pack(padx=5, pady=(0, 5))
        cam_holder.pack_propagate(False)
        self.cam_lbl = tk.Label(cam_holder, bg="#000000")
        self.cam_lbl.pack(expand=True, fill="both")

        # ── 오른쪽: 정보 패널 ────────────────────────────────────────────────
        self.panel = tk.Frame(content, bg=BG_DARK, width=268)
        self.panel.pack(side="left", fill="y", padx=(10, 0))
        self.panel.pack_propagate(False)
        panel = self.panel

        # 점수 카드
        sc = self._card(panel)
        tk.Label(sc, text="POSTURE SCORE", bg=BG_PANEL, fg=TEXT_SEC,
                 font=("Segoe UI", 7, "bold")).pack(anchor="nw", padx=10, pady=(8, 0))

        self.score_lbl = tk.Label(sc, text="--", bg=BG_PANEL, fg=TEXT_PRI,
                                   font=("Segoe UI", 52, "bold"))
        self.score_lbl.pack(pady=(2, 0))

        self.grade_lbl = tk.Label(sc, text="Calibrating…", bg=BG_PANEL,
                                   fg=TEXT_SEC, font=("Segoe UI", 13, "bold"))
        self.grade_lbl.pack(pady=(0, 8))

        # 점수 바
        bar_wrap = tk.Frame(sc, bg=BG_PANEL)
        bar_wrap.pack(fill="x", padx=10, pady=(0, 10))
        self.bar_bg = tk.Frame(bar_wrap, bg=BG_CARD, height=8)
        self.bar_bg.pack(fill="x")
        self.bar_fg = tk.Frame(self.bar_bg, bg=CLR_GOOD, height=8, width=0)
        self.bar_fg.place(x=0, y=0, relheight=1)

        # 측정값 카드
        mc = self._card(panel)
        tk.Label(mc, text="METRICS", bg=BG_PANEL, fg=TEXT_SEC,
                 font=("Segoe UI", 7, "bold")).pack(anchor="nw", padx=10, pady=(8, 4))
        self.lbl_vertical = self._metric_row(mc, "Vertical (neck)", "--")
        self.lbl_lateral  = self._metric_row(mc, "Lateral  (tilt)", "--")
        tk.Frame(mc, bg=BG_PANEL, height=6).pack()

        # 세션 카드
        ss = self._card(panel)
        tk.Label(ss, text="SESSION", bg=BG_PANEL, fg=TEXT_SEC,
                 font=("Segoe UI", 7, "bold")).pack(anchor="nw", padx=10, pady=(8, 4))
        self.lbl_duration = self._metric_row(ss, "Duration", "00:00")
        self.lbl_avg      = self._metric_row(ss, "Avg Score", "--")
        self.lbl_low      = self._metric_row(ss, "Lowest",   "--")
        tk.Frame(ss, bg=BG_PANEL, height=6).pack()

        # 버튼
        self.btn_frame = tk.Frame(panel, bg=BG_DARK)
        self.btn_frame.pack(fill="x", pady=(4, 0))
        btn_frame = self.btn_frame

        self._btn(btn_frame, "Recalibrate",        ACCENT_BLU, self._recalibrate).pack(fill="x", pady=2)
        self._btn(btn_frame, "Calendar / History", BG_CARD,    self._open_calendar).pack(fill="x", pady=2)
        self._btn(btn_frame, "Quit",               "#4a2020",  self._on_close).pack(fill="x", pady=2)

    def _card(self, parent):
        f = tk.Frame(parent, bg=BG_PANEL,
                     highlightbackground=CLR_BORDER, highlightthickness=1)
        f.pack(fill="x", pady=(0, 8))
        return f

    def _metric_row(self, parent, label, value):
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x", padx=10, pady=2)
        tk.Label(row, text=label, bg=BG_PANEL, fg=TEXT_SEC,
                 font=("Segoe UI", 9), width=17, anchor="w").pack(side="left")
        v = tk.Label(row, text=value, bg=BG_PANEL, fg=TEXT_PRI,
                     font=("Segoe UI", 9, "bold"))
        v.pack(side="right")
        return v

    def _btn(self, parent, text, bg, cmd):
        return tk.Button(parent, text=text, bg=bg, fg=TEXT_PRI,
                         font=("Segoe UI", 10, "bold"), bd=0, pady=9,
                         cursor="hand2", activebackground=bg,
                         activeforeground=TEXT_PRI, command=cmd)

    # ── 모델 초기화 (별도 스레드) ─────────────────────────────────────────────
    def _init_analyzer(self):
        self.analyzer = PostureAnalyzer()
        self.analyzer.start_calibration()

    # ── 카메라 루프 (별도 스레드) ──────────────────────────────────────────────
    def _camera_loop(self):
        cap = cv2.VideoCapture(0)
        while self.running:
            if self.analyzer is None:
                time.sleep(0.1)
                continue
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue
            frame = cv2.flip(frame, 1)
            frame, state = self.analyzer.process_frame(frame)
            with self._frame_lock:
                self._frame_data = (frame, state)
            time.sleep(0.03)
        cap.release()

    # ── UI 갱신 루프 (메인 스레드) ────────────────────────────────────────────
    def _refresh_ui(self):
        if not self.running:
            return

        with self._frame_lock:
            data = self._frame_data

        if data is None and self.analyzer is None:
            self.status_lbl.config(text="AI 모델 로딩 중…", fg=TEXT_SEC)

        if data is not None:
            frame, state = data

            # 카메라 이미지 업데이트
            h, w = frame.shape[:2]
            disp_h = int(h * CAM_DISPLAY_W / w)
            resized = cv2.resize(frame, (CAM_DISPLAY_W, disp_h))
            img     = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))
            photo   = ImageTk.PhotoImage(image=img)
            self.cam_lbl.configure(image=photo)
            self.cam_lbl.image = photo

            # 상태에 따라 우측 패널 갱신
            if not state["calibrated"]:
                rem = state.get("calib_remaining", 0)
                self.status_lbl.config(text=f"캘리브레이션 중…  {rem}초 남음", fg=CLR_WARN)
                self.grade_lbl.config(text="Sit Straight!", fg=CLR_WARN)
                self.score_lbl.config(text="--", fg=TEXT_SEC)

            elif state["detected"] and state["score"] is not None:
                score = state["score"]
                grade = state["grade"]
                label = state["label"]
                col   = score_color(score)

                self.status_lbl.config(text="모니터링 중", fg=CLR_GOOD)
                self.score_lbl.config(text=str(score), fg=col)
                self.grade_lbl.config(text=f"{grade}  ─  {label}", fg=col)

                # 점수 바
                bw = self.bar_bg.winfo_width()
                if bw > 1:
                    self.bar_fg.place(x=0, y=0, relheight=1,
                                      width=max(0, int(bw * score / 100)))
                self.bar_fg.config(bg=col)

                # 측정값
                vr = state["vertical_ratio"]
                lr = state["lateral_ratio"]
                rv = self.analyzer.ref_values["vertical"]
                rl = self.analyzer.ref_values["lateral"]
                self.lbl_vertical.config(text=f"{vr:.3f}  (ref {rv:.3f})")
                self.lbl_lateral.config(text=f"{lr:.3f}  (ref {rl:.3f})")

                # 세션 통계
                elapsed = int(time.time() - self.session_start)
                m, s = divmod(elapsed, 60)
                self.lbl_duration.config(text=f"{m:02d}:{s:02d}")

                self.session_scores.append(score)
                avg = float(np.mean(self.session_scores))
                low = min(self.session_scores)
                self.lbl_avg.config(text=f"{avg:.0f}점")
                self.lbl_low.config(text=f"{low}점",
                                    fg=score_color(low))

                # JSON 저장
                now = time.time()
                if now - self.last_save_time >= SCORE_INTERVAL:
                    self.data_manager.add_score(score, f"{grade} - {label}")
                    self.last_save_time = now

            elif not state["detected"]:
                self.status_lbl.config(text="사람을 감지할 수 없습니다.", fg=TEXT_SEC)

        self.root.after(33, self._refresh_ui)   # ~30 fps

    # ── 버튼 핸들러 ────────────────────────────────────────────────────────────
    def _recalibrate(self):
        if self.analyzer is None:
            return
        self.analyzer.start_calibration()
        self.session_scores.clear()
        self.session_start = time.time()
        self.last_save_time = 0.0

    def _open_calendar(self):
        CalendarView(self.root, self.data_manager)

    def _on_close(self):
        self.running = False
        self.root.after(200, self.root.destroy)


# ══════════════════════════════════════════════════════════════════════════════
# 진입점
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    app  = PostureApp(root)
    root.lift()
    root.focus_force()
    root.mainloop()
