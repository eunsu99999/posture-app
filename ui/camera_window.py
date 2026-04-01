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
    CAM_DISPLAY_W, SCORE_INTERVAL, SENSITIVITY_PRESETS,
    score_color, score_grade,
)
from analyzer import PostureAnalyzer
from ui.widgets import ScoreRingCanvas
from ui.warning_banner import PostureWarningBanner


class CameraMonitorWindow(tk.Toplevel):
    def __init__(self, parent, data_manager, sensitivity_var, app_settings=None, on_close_cb=None):
        super().__init__(parent)
        self.title("실시간 모니터링  —  자세 확인")
        self.configure(bg=BG_APP)
        self.resizable(False, False)

        self.data_manager      = data_manager
        self.sensitivity_var   = sensitivity_var
        self.app_settings      = app_settings
        self.on_close_cb       = on_close_cb
        self.analyzer          = None
        self.running           = True
        self._frame_data       = None
        self._frame_lock       = threading.Lock()
        self.last_save_time        = 0.0
        self.session_start         = time.time()
        self.session_scores        = []
        self._calibration_done     = False
        self._banner_active        = False   # 현재 배너 표시 사이클 중인지
        self._banner_cooldown_until = 0.0   # 이 시각까지 배너 억제

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.iconify)

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
                  command=self.iconify).pack(side="right", padx=12, pady=6)

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
        tk.Label(sc, text="자세 점수", bg=BG_CARD, fg=TEXT_SEC,
                 font=(FONT, 9)).pack(anchor="nw", padx=12, pady=(10, 0))
        ring_row = tk.Frame(sc, bg=BG_CARD)
        ring_row.pack(fill="x", padx=8, pady=(4, 0))
        self.ring = ScoreRingCanvas(ring_row, size=100, ring_width=10, bg=BG_CARD)
        self.ring.pack(side="left")
        self.ring.draw(None)
        info_col = tk.Frame(ring_row, bg=BG_CARD)
        info_col.pack(side="left", fill="y", padx=(10, 0))
        self.grade_lbl = tk.Label(info_col, text="캘리브레이션 중...", bg=BG_CARD,
                                   fg=TEXT_SEC, font=(FONT, 11, "bold"))
        self.grade_lbl.pack(anchor="w", pady=(18, 4))
        self.sens_lbl = tk.Label(info_col, text="", bg=BG_CARD,
                                  fg=CLR_BLUE, font=(FONT, 8))
        self.sens_lbl.pack(anchor="w")
        # progress bar
        bar_wrap = tk.Frame(sc, bg=BG_CARD)
        bar_wrap.pack(fill="x", padx=12, pady=(4, 10))
        bar_bg = tk.Frame(bar_wrap, bg=CLR_BORDER, height=6)
        bar_bg.pack(fill="x")
        self.bar_fg = tk.Frame(bar_bg, bg=CLR_GOOD, height=6, width=0)
        self.bar_fg.place(x=0, y=0, relheight=1)
        self._bar_bg = bar_bg

        # metrics card
        mc = self._card(panel)
        tk.Label(mc, text="측정값", bg=BG_CARD, fg=TEXT_SEC,
                 font=(FONT, 9)).pack(anchor="nw", padx=12, pady=(10, 2))
        self.lbl_vertical = self._row(mc, "목 (수직)")
        self.lbl_lateral  = self._row(mc, "기울기 (수평)")
        tk.Frame(mc, bg=BG_CARD, height=6).pack()

        # session card
        ss = self._card(panel)
        tk.Label(ss, text="현재 세션", bg=BG_CARD, fg=TEXT_SEC,
                 font=(FONT, 9)).pack(anchor="nw", padx=12, pady=(10, 2))
        self.lbl_duration = self._row(ss, "경과 시간", "00:00")
        self.lbl_avg      = self._row(ss, "평균 점수")
        self.lbl_low      = self._row(ss, "최저 점수")
        tk.Frame(ss, bg=BG_CARD, height=6).pack()

        # recalibrate button
        tk.Button(panel, text="다시 캘리브레이션", bg=ACCENT, fg="#FFFFFF",
                  font=(FONT, 10, "bold"), bd=0, pady=10, cursor="hand2",
                  activebackground="#27AE86", activeforeground="#FFFFFF",
                  command=self._recalibrate).pack(fill="x", pady=(8, 0))

    def _card(self, parent):
        f = tk.Frame(parent, bg=BG_CARD,
                     highlightbackground=CLR_BORDER, highlightthickness=1)
        f.pack(fill="x", pady=(0, 6))
        return f

    def _row(self, parent, label, value="--"):
        row = tk.Frame(parent, bg=BG_CARD)
        row.pack(fill="x", padx=12, pady=2)
        tk.Label(row, text=label, bg=BG_CARD, fg=TEXT_SEC,
                 font=(FONT, 9), width=16, anchor="w").pack(side="left")
        v = tk.Label(row, text=value, bg=BG_CARD, fg=TEXT_PRI,
                     font=(FONT, 9, "bold"))
        v.pack(side="right")
        return v

    # ── background threads ────────────────────────────────────────────────────
    def _init_analyzer(self):
        self.analyzer = PostureAnalyzer(sensitivity=self.sensitivity_var.get())
        self.analyzer.set_alert_callback(self.data_manager.add_alert)
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
            time.sleep(0.03)
        cap.release()

    # ── UI refresh loop ───────────────────────────────────────────────────────
    def _refresh_ui(self):
        if not self.running:
            return

        # sync sensitivity + alert_interval from settings
        sens   = self.sensitivity_var.get()
        preset = SENSITIVITY_PRESETS.get(sens, SENSITIVITY_PRESETS["normal"])
        if self.analyzer and self.analyzer.sensitivity != sens:
            self.analyzer.set_sensitivity(sens)
        if self.analyzer and self.app_settings:
            self.analyzer.alert_interval = self.app_settings.alert_interval
        self.sens_lbl.config(
            text=f"{preset['label']} — {preset['ko']}",
            fg=preset["color"]
        )

        with self._frame_lock:
            data = self._frame_data

        if data is None and self.analyzer is None:
            self.status_lbl.config(text="AI 모델 로딩 중...", fg=TEXT_SEC)

        if data is not None:
            frame, state = data
            h, w = frame.shape[:2]
            disp_h = int(h * CAM_DISPLAY_W / w)
            resized = cv2.resize(frame, (CAM_DISPLAY_W, disp_h))
            img   = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))
            photo = ImageTk.PhotoImage(image=img)
            self.cam_lbl.configure(image=photo)
            self.cam_lbl.image = photo

            if not state["calibrated"]:
                rem = state.get("calib_remaining", 0)
                self.status_lbl.config(text=f"캘리브레이션 중...  {rem}초 남음", fg=CLR_WARN)
                self.grade_lbl.config(text="바르게 앉아주세요!", fg=CLR_WARN)
                self.ring.draw(None)
            elif state["calibrated"] and not self._calibration_done:
                self._calibration_done = True
                self.after(2000, self.iconify)
                if self.on_close_cb:
                    self.on_close_cb(minimized=True)

            if state["detected"] and state["score"] is not None and state["calibrated"]:
                score = state["score"]
                grade = state["grade"]
                label = state["label"]
                col   = score_color(score)

                self.status_lbl.config(text="모니터링 중", fg=CLR_GOOD)
                self.grade_lbl.config(text=f"{grade}  —  {label}", fg=col)
                self.ring.draw(score)

                bw = self._bar_bg.winfo_width()
                if bw > 1:
                    self.bar_fg.place(x=0, y=0, relheight=1,
                                      width=max(0, int(bw * score / 100)))
                self.bar_fg.config(bg=col)

                rv = self.analyzer.ref_values.get("vertical") or 0
                rl = self.analyzer.ref_values.get("lateral")  or 0
                self.lbl_vertical.config(text=f"{state['vertical_ratio']:.3f}  (ref {rv:.3f})")
                self.lbl_lateral.config( text=f"{state['lateral_ratio']:.3f}  (ref {rl:.3f})")

                elapsed = int(time.time() - self.session_start)
                m, s = divmod(elapsed, 60)
                self.lbl_duration.config(text=f"{m:02d}:{s:02d}")

                self.session_scores.append(score)
                avg = sum(self.session_scores) / len(self.session_scores)
                low = min(self.session_scores)
                self.lbl_avg.config(text=f"{avg:.0f}pt", fg=score_color(avg))
                self.lbl_low.config(text=f"{low}pt",     fg=score_color(low))

                now = time.time()
                if now - self.last_save_time >= SCORE_INTERVAL:
                    self.data_manager.add_score(score, f"{grade} - {label}")
                    self.last_save_time = now

            if state["calibrated"] and not state["detected"]:
                self.status_lbl.config(text="사람을 감지할 수 없습니다.", fg=TEXT_HINT)

            # 경고 배너 업데이트 (alert_interval 쿨다운 적용)
            grade = state.get("grade")
            if grade in ("C", "D"):
                now = time.time()
                if not self._banner_active and now >= self._banner_cooldown_until:
                    self._banner_active = True
                effective_grade = grade if self._banner_active else "A"
            else:
                if self._banner_active:
                    self._banner_active = False
                    interval = self.app_settings.alert_interval if self.app_settings else 30
                    self._banner_cooldown_until = time.time() + interval
                effective_grade = grade
            self._warning_banner.update(
                grade=effective_grade,
                detected=state["detected"],
                calibrated=state["calibrated"],
            )

        self.after(33, self._refresh_ui)

    # ── controls ──────────────────────────────────────────────────────────────
    def _recalibrate(self):
        if self.analyzer is None:
            return
        self.analyzer.start_calibration()
        self.session_scores.clear()
        self.session_start     = time.time()
        self.last_save_time    = 0.0
        self._calibration_done = False
        self._warning_banner.hide_immediately()
        self.deiconify()
        self.lift()

    def stop(self):
        self.running = False
        self._warning_banner.destroy()
        if self.on_close_cb:
            self.on_close_cb()
        self.after(200, self.destroy)
