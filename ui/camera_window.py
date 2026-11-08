"""CameraMonitorWindow — popup camera feed + posture analysis."""
import tkinter as tk
import threading
import time

import cv2
import numpy as np
from PIL import Image, ImageTk

from config import (
    FONT, BG_APP, BG_CARD, ACCENT, TEXT_PRI, TEXT_SEC, TEXT_HINT,
    CLR_GOOD, CLR_WARN, CLR_DANGER, CLR_BLUE, CLR_BORDER,
    CAM_DISPLAY_W, SCORE_INTERVAL,
    PSI_MIN, PSI_MAX,
    score_color, score_grade,
)
from analyzer import PostureAnalyzer
from ui.widgets import ScoreRingCanvas
from ui.warning_banner import PostureWarningBanner


_AXIS_GRADE_KO = {1: "적정", 2: "주의", 3: "부적정"}
_WORST_AXIS_KO = {
    "neck":     "목 굴곡",
    "forward":  "머리 앞돌출",
    "lateral":  "측방 기울기",
    "shoulder": "어깨 기울기",
}


class CameraMonitorWindow(tk.Toplevel):
    def __init__(self, parent, data_manager, app_settings=None, on_close_cb=None, preloaded_analyzer=None):
        super().__init__(parent)
        self.title("실시간 모니터링  —  자세 확인")
        self.configure(bg=BG_APP)
        self.resizable(False, False)

        self.data_manager      = data_manager
        self.app_settings      = app_settings
        self.on_close_cb       = on_close_cb
        self.analyzer          = None
        self._preloaded_analyzer = preloaded_analyzer
        self.running           = True
        self._frame_data       = None
        self._frame_lock       = threading.Lock()
        self.last_save_time        = 0.0
        self.session_start         = time.time()
        self.session_scores        = []   # best 추적용 (소규모 유지)
        self._session_sum          = 0.0
        self._session_count        = 0
        self._session_best         = float("inf")
        self._calibration_done     = False
        self._banner_active         = False
        self._banner_cooldown_start = None
        self._last_photo            = None   # PhotoImage GC 방지 + 중복 방지용
        self._last_frame_id         = None   # 동일 프레임 재처리 방지

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        self._warning_banner = PostureWarningBanner(self)

        threading.Thread(target=self._init_analyzer, daemon=True).start()
        threading.Thread(target=self._camera_loop,   daemon=True).start()
        self._refresh_ui()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # header
        hdr = tk.Frame(self, bg=BG_CARD,
                       highlightbackground=CLR_BORDER, highlightthickness=1)
        hdr.pack(fill="x")
        tk.Label(hdr, text="카메라 모니터", bg=BG_CARD, fg=TEXT_PRI,
                 font=(FONT, 12, "bold")).pack(side="left", padx=16, pady=10)
        self.status_lbl = tk.Label(hdr, text="시작 중...", bg=BG_CARD,
                                    fg=TEXT_SEC, font=(FONT, 10))
        self.status_lbl.pack(side="left", padx=8)
        tk.Button(hdr, text="숨기기", bg=BG_APP, fg=TEXT_SEC, bd=0,
                  padx=12, pady=6, cursor="hand2", font=(FONT, 9),
                  command=self.withdraw).pack(side="right", padx=12, pady=6)

        content = tk.Frame(self, bg=BG_APP)
        content.pack(fill="both", expand=True, padx=12, pady=12)

        # camera feed
        cam_wrap = tk.Frame(content, bg=BG_CARD,
                             highlightbackground=CLR_BORDER, highlightthickness=1)
        cam_wrap.pack(side="left", fill="y")
        tk.Label(cam_wrap, text="실시간 피드", bg=BG_CARD, fg=TEXT_HINT,
                 font=(FONT, 8)).pack(anchor="nw", padx=8, pady=(6, 2))
        cam_holder = tk.Frame(cam_wrap, bg="#000000",
                               width=CAM_DISPLAY_W, height=400)
        cam_holder.pack(padx=6, pady=(0, 6))
        cam_holder.pack_propagate(False)
        self.cam_lbl = tk.Label(cam_holder, bg="#000000")
        self.cam_lbl.pack(expand=True, fill="both")

        # right panel
        panel = tk.Frame(content, bg=BG_APP, width=260)
        panel.pack(side="left", fill="y", padx=(12, 0))
        panel.pack_propagate(False)

        # score ring card
        sc = self._card(panel)
        tk.Label(sc, text="자세 등급", bg=BG_CARD, fg=TEXT_SEC,
                 font=(FONT, 9)).pack(anchor="nw", padx=12, pady=(6, 0))
        ring_row = tk.Frame(sc, bg=BG_CARD)
        ring_row.pack(fill="x", padx=8, pady=(2, 0))
        self.ring = ScoreRingCanvas(ring_row, size=80, ring_width=8, bg=BG_CARD)
        self.ring.pack(side="left")
        self.ring.draw(None)
        info_col = tk.Frame(ring_row, bg=BG_CARD)
        info_col.pack(side="left", fill="y", padx=(8, 0))
        self.grade_lbl = tk.Label(info_col, text="기준 설정 중...", bg=BG_CARD,
                                   fg=TEXT_SEC, font=(FONT, 10, "bold"))
        self.grade_lbl.pack(anchor="w", pady=(12, 2))
        # progress bar
        bar_wrap = tk.Frame(sc, bg=BG_CARD)
        bar_wrap.pack(fill="x", padx=12, pady=(2, 6))
        bar_bg = tk.Frame(bar_wrap, bg=CLR_BORDER, height=5)
        bar_bg.pack(fill="x")
        self.bar_fg = tk.Frame(bar_bg, bg=CLR_GOOD, height=5, width=0)
        self.bar_fg.place(x=0, y=0, relheight=1)
        self._bar_bg = bar_bg

        # metrics card
        mc = self._card(panel)
        tk.Label(mc, text="측정값  (축별 등급)", bg=BG_CARD, fg=TEXT_SEC,
                 font=(FONT, 9)).pack(anchor="nw", padx=12, pady=(6, 2))
        self.lbl_vertical = self._row(mc, "축1 목굴곡")
        self.lbl_forward  = self._row(mc, "축2 앞돌출")
        self.lbl_lateral  = self._row(mc, "축3 측방")
        self.lbl_shoulder = self._row(mc, "축4 어깨")
        tk.Frame(mc, bg=BG_CARD, height=3).pack()

        # session card
        ss = self._card(panel)
        tk.Label(ss, text="현재 세션", bg=BG_CARD, fg=TEXT_SEC,
                 font=(FONT, 9)).pack(anchor="nw", padx=12, pady=(6, 2))
        self.lbl_duration = self._row(ss, "경과 시간", "00:00")
        self.lbl_avg      = self._row(ss, "평균 등급")
        self.lbl_low      = self._row(ss, "최고 등급")
        tk.Frame(ss, bg=BG_CARD, height=3).pack()

        # recalibrate button
        tk.Button(panel, text="기준 재설정", bg=ACCENT, fg="#FFFFFF",
                  font=(FONT, 9, "bold"), bd=0, pady=7, cursor="hand2",
                  activebackground="#27AE86", activeforeground="#FFFFFF",
                  command=self._recalibrate).pack(fill="x", pady=(6, 0))

    def _card(self, parent):
        f = tk.Frame(parent, bg=BG_CARD,
                     highlightbackground=CLR_BORDER, highlightthickness=1)
        f.pack(fill="x", pady=(0, 4))
        return f

    def _row(self, parent, label, value="--"):
        row = tk.Frame(parent, bg=BG_CARD)
        row.pack(fill="x", padx=12, pady=1)
        tk.Label(row, text=label, bg=BG_CARD, fg=TEXT_SEC,
                 font=(FONT, 9), width=12, anchor="w").pack(side="left")
        v = tk.Label(row, text=value, bg=BG_CARD, fg=TEXT_PRI,
                     font=(FONT, 9, "bold"))
        v.pack(side="right")
        return v

    # ── background threads ────────────────────────────────────────────────────
    def _init_analyzer(self):
        if self._preloaded_analyzer is not None:
            self.analyzer = self._preloaded_analyzer
            self._preloaded_analyzer = None
        else:
            self.analyzer = PostureAnalyzer()
        def _alert_cb(msg, severity, snapshot=None):
            with self._frame_lock:
                data = self._frame_data
            frame_copy = data[0].copy() if data is not None else None
            self.data_manager.add_alert(msg, severity, frame=frame_copy, snapshot=snapshot)

        self.analyzer.set_alert_callback(_alert_cb)
        self.analyzer.start_calibration()

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

            # 창이 보일 때 ~10fps, 백그라운드일 때 ~2fps
            try:
                visible = self.winfo_viewable()
            except Exception:
                visible = True
            time.sleep(0.08 if visible else 0.5)
        cap.release()

    # ── UI refresh loop ───────────────────────────────────────────────────────
    def _refresh_ui(self):
        if not self.running:
            return

        if self.analyzer and self.app_settings:
            self.analyzer.alert_interval = self.app_settings.alert_interval

        with self._frame_lock:
            data = self._frame_data

        if data is None and self.analyzer is None:
            self.status_lbl.config(text="AI 모델 로딩 중...", fg=TEXT_SEC)

        if data is not None:
            frame, state = data
            # 동일 프레임이면 PhotoImage 재생성 생략 (가장 비싼 연산)
            fid = id(frame)
            if fid != self._last_frame_id:
                self._last_frame_id = fid
                h, w   = frame.shape[:2]
                disp_h = int(h * CAM_DISPLAY_W / w)
                resized = cv2.resize(frame, (CAM_DISPLAY_W, disp_h))
                img     = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))
                photo   = ImageTk.PhotoImage(image=img)
                self._last_photo = photo        # GC 방지
                self.cam_lbl.configure(image=photo)

            if not state["calibrated"]:
                rem = state.get("calib_remaining", 0)
                self.status_lbl.config(text=f"기준 설정 중...  {rem}초 남음", fg=CLR_WARN)
                self.grade_lbl.config(text="바르게 앉아주세요!", fg=CLR_WARN)
                self.ring.draw(None)
            elif state["calibrated"] and not self._calibration_done:
                self._calibration_done = True
                self.after(2000, self.withdraw)
                if self.on_close_cb:
                    self.on_close_cb(minimized=True)

            if state["detected"] and state["score"] is not None and state["calibrated"]:
                score = state["score"]   # RULA 1~5
                grade = state["grade"]   # 한국어 등급
                label = state["label"]
                col   = score_color(score)

                self.status_lbl.config(text="모니터링 중", fg=CLR_GOOD)
                worst_ko = _WORST_AXIS_KO.get(state.get("worst_axis"))
                if grade == "적정" or not worst_ko:
                    self.grade_lbl.config(text=f"종합: {grade}", fg=col)
                else:
                    self.grade_lbl.config(text=f"종합: {grade} (원인: {worst_ko})", fg=col)
                self.ring.draw(score)

                bw = self._bar_bg.winfo_width()
                if bw > 1:
                    frac = (PSI_MAX - max(PSI_MIN, min(PSI_MAX, score))) / (PSI_MAX - PSI_MIN)
                    self.bar_fg.place(x=0, y=0, relheight=1,
                                      width=max(0, int(bw * frac)))
                self.bar_fg.config(bg=col)

                nf = state["neck_flexion"]
                fd = state["forward_dist"]
                lt = state["lateral_tilt"]
                st = state["shoulder_tilt"]
                a1 = state["axis1"]
                a2 = state["axis2"]
                a3 = state["axis3"]
                a4 = state["axis4"]
                self.lbl_vertical.config(
                    text=f"{nf:.1f}°  ·  {_AXIS_GRADE_KO.get(a1, '--')}" if nf is not None else "--",
                    fg=score_color(a1) if a1 else TEXT_PRI)
                self.lbl_forward.config(
                    text=f"{fd:.1f}cm  ·  {_AXIS_GRADE_KO.get(a2, '--')}" if fd is not None else "--",
                    fg=score_color(a2) if a2 else TEXT_PRI)
                self.lbl_lateral.config(
                    text=f"{lt:.1f}°  ·  {_AXIS_GRADE_KO.get(a3, '--')}" if lt is not None else "--",
                    fg=score_color(a3) if a3 else TEXT_PRI)
                self.lbl_shoulder.config(
                    text=f"{st:.1f}°  ·  {_AXIS_GRADE_KO.get(a4, '--')}" if st is not None else "--",
                    fg=score_color(a4) if a4 else TEXT_PRI)

                elapsed = int(time.time() - self.session_start)
                m, s = divmod(elapsed, 60)
                self.lbl_duration.config(text=f"{m:02d}:{s:02d}")

                self._session_sum   += score
                self._session_count += 1
                if score < self._session_best:
                    self._session_best = score
                avg  = self._session_sum / self._session_count
                best = self._session_best
                self.lbl_avg.config(text=score_grade(avg)[0], fg=score_color(avg))
                self.lbl_low.config(text=score_grade(best)[0], fg=score_color(best))

                now = time.time()
                if now - self.last_save_time >= SCORE_INTERVAL:
                    self.data_manager.add_score(score, grade)
                    self.last_save_time = now

            if state["calibrated"] and not state["detected"]:
                self.status_lbl.config(text="사람을 감지할 수 없습니다.", fg=TEXT_HINT)

            # 경고 배너 업데이트 (alert_interval 쿨다운 적용)
            grade = state.get("grade")
            if grade in ("주의", "부적정"):
                now = time.time()
                if not self._banner_active:
                    interval = self.app_settings.alert_interval if self.app_settings else 30
                    cooldown_elapsed = (
                        self._banner_cooldown_start is None or
                        now - self._banner_cooldown_start >= interval
                    )
                    if cooldown_elapsed:
                        self._banner_active = True
                effective_grade = grade if self._banner_active else "적정"
            else:
                if self._banner_active:
                    self._banner_active = False
                    self._banner_cooldown_start = time.time()
                effective_grade = grade
            self._warning_banner.update(
                grade=effective_grade,
                detected=state["detected"],
                calibrated=state["calibrated"],
                cause=state.get("worst_axis"),
            )

        self.after(100, self._refresh_ui)

    # ── controls ──────────────────────────────────────────────────────────────
    def _recalibrate(self):
        if self.analyzer is None:
            return
        self.analyzer.start_calibration()
        self.session_scores.clear()
        self._session_sum          = 0.0
        self._session_count        = 0
        self._session_best         = float("inf")
        self.session_start         = time.time()
        self.last_save_time        = 0.0
        self._calibration_done     = False
        self._banner_active         = False
        self._banner_cooldown_start = None
        self._warning_banner.hide_immediately()
        self.deiconify()
        self.lift()

    def get_analyzer(self):
        return self.analyzer

    def stop(self):
        self.running = False
        self._warning_banner.destroy()
        if self.on_close_cb:
            self.on_close_cb()
        self.after(200, self.destroy)
