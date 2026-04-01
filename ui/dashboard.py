"""DashboardPage — main overview screen matching the mockup."""
import tkinter as tk
from datetime import date, datetime

from config import (
    FONT, BG_APP, BG_CARD, BG_ACTIVE, ACCENT, ACCENT_DRK,
    TEXT_PRI, TEXT_SEC, TEXT_HINT,
    CLR_GOOD, CLR_WARN, CLR_DANGER, CLR_BLUE, CLR_BORDER,
    STRETCH_GOAL,
    score_color, score_grade, score_label_ko, score_desc_ko,
    fmt_duration_ko,
)
from ui.widgets import MetricCard, ScoreRingCanvas

TIPS = [
    ("모니터 높이",   "화면 상단이 눈높이와 같거나 약간 낮게 두세요."),
    ("발 위치",       "발바닥이 바닥에 완전히 닿도록 의자 높이를 조정하세요."),
    ("허리 지지",     "허리 쿠션으로 요추 곡선을 자연스럽게 유지하세요."),
    ("20-20-20 규칙", "20분마다 20초간 6m 거리를 바라보세요."),
]


class DashboardPage(tk.Frame):
    def __init__(self, parent, data_manager, on_start_monitoring=None, **kwargs):
        super().__init__(parent, bg=BG_APP, **kwargs)
        self.data_manager        = data_manager
        self.on_start_monitoring = on_start_monitoring
        self._monitoring_active  = False
        self._today              = date.today().isoformat()

        self._build()
        self.refresh()
        self._tick()

    # ── build ─────────────────────────────────────────────────────────────────
    def _build(self):
        # ── header row ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG_APP)
        hdr.pack(fill="x", padx=20, pady=(18, 0))

        left_hdr = tk.Frame(hdr, bg=BG_APP)
        left_hdr.pack(side="left")
        tk.Label(left_hdr, text="오늘의 자세 현황", bg=BG_APP, fg=TEXT_PRI,
                 font=(FONT, 18, "bold")).pack(anchor="w")
        self._date_lbl = tk.Label(left_hdr, text="", bg=BG_APP, fg=TEXT_SEC,
                                   font=(FONT, 10))
        self._date_lbl.pack(anchor="w")

        right_hdr = tk.Frame(hdr, bg=BG_APP)
        right_hdr.pack(side="right", anchor="n")
        self._sitting_lbl = tk.Label(right_hdr, text="", bg=BG_ACTIVE,
                                      fg=ACCENT, font=(FONT, 9, "bold"),
                                      padx=10, pady=4)
        self._sitting_lbl.pack(side="left", padx=(0, 10))
        self._monitor_btn = tk.Button(
            right_hdr, text="실시간 시작", bg=ACCENT, fg="#FFFFFF",
            font=(FONT, 10, "bold"), bd=0, padx=16, pady=8, cursor="hand2",
            activebackground=ACCENT_DRK, activeforeground="#FFFFFF",
            command=self._on_monitor_click,
        )
        self._monitor_btn.pack(side="left")

        tk.Frame(self, bg=CLR_BORDER, height=1).pack(fill="x", padx=20, pady=(12, 0))

        # ── 4 metric cards ────────────────────────────────────────────────────
        cards_row = tk.Frame(self, bg=BG_APP)
        cards_row.pack(fill="x", padx=20, pady=12)

        self._card_score    = MetricCard(cards_row, "오늘 자세 점수",  "--", "", TEXT_PRI)
        self._card_time     = MetricCard(cards_row, "바른 자세 시간",  "--", "", CLR_GOOD)
        self._card_alerts   = MetricCard(cards_row, "경고 횟수",       "--", "", CLR_DANGER)
        self._card_stretch  = MetricCard(cards_row, "스트레칭 완료",   "--", f"오늘 목표  {STRETCH_GOAL}회", TEXT_PRI)

        for card in (self._card_score, self._card_time,
                     self._card_alerts, self._card_stretch):
            card.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=4)
            card.pack_info()  # ensure layout

        # stretch button inside stretch card
        tk.Button(self._card_stretch, text="+ 완료", bg=BG_ACTIVE, fg=ACCENT,
                  bd=0, font=(FONT, 8, "bold"), padx=8, pady=3, cursor="hand2",
                  activebackground=BG_ACTIVE,
                  command=self._on_stretch).pack(anchor="e", padx=14, pady=(0, 8))

        # ── middle row: bar chart + gauge ─────────────────────────────────────
        mid = tk.Frame(self, bg=BG_APP)
        mid.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # hourly bar chart
        chart_card = tk.Frame(mid, bg=BG_CARD,
                               highlightbackground=CLR_BORDER, highlightthickness=1)
        chart_card.pack(side="left", fill="both", expand=True, padx=(0, 10))
        tk.Label(chart_card, text="시간대별 자세 점수", bg=BG_CARD, fg=TEXT_PRI,
                 font=(FONT, 11, "bold")).pack(anchor="nw", padx=14, pady=(12, 4))
        self._chart_canvas = tk.Canvas(chart_card, bg=BG_CARD,
                                        highlightthickness=0, height=160)
        self._chart_canvas.pack(fill="x", padx=14, pady=(0, 12))
        self._chart_canvas.bind("<Configure>", lambda e: self._draw_chart())

        # circular gauge + label
        gauge_card = tk.Frame(mid, bg=BG_CARD,
                               highlightbackground=CLR_BORDER, highlightthickness=1,
                               width=220)
        gauge_card.pack(side="left", fill="y")
        gauge_card.pack_propagate(False)
        tk.Label(gauge_card, text="종합 자세 점수", bg=BG_CARD, fg=TEXT_PRI,
                 font=(FONT, 11, "bold")).pack(anchor="nw", padx=14, pady=(12, 0))

        self._ring = ScoreRingCanvas(gauge_card, size=150, ring_width=14, bg=BG_CARD)
        self._ring.pack(pady=(8, 4))
        self._ring.draw(None)

        self._gauge_label = tk.Label(gauge_card, text="--", bg=BG_CARD,
                                      fg=ACCENT, font=(FONT, 11, "bold"))
        self._gauge_label.pack()
        self._gauge_desc = tk.Label(gauge_card, text="", bg=BG_CARD, fg=TEXT_SEC,
                                     font=(FONT, 8), wraplength=180, justify="center")
        self._gauge_desc.pack(pady=(2, 12))

        # ── bottom row: alert log + tips ──────────────────────────────────────
        bot = tk.Frame(self, bg=BG_APP)
        bot.pack(fill="x", padx=20, pady=(0, 16))

        # alert log
        alert_card = tk.Frame(bot, bg=BG_CARD,
                               highlightbackground=CLR_BORDER, highlightthickness=1)
        alert_card.pack(side="left", fill="both", expand=True, padx=(0, 10))
        tk.Label(alert_card, text="오늘 알림 로그", bg=BG_CARD, fg=TEXT_PRI,
                 font=(FONT, 11, "bold")).pack(anchor="nw", padx=14, pady=(12, 6))
        self._alert_frame = tk.Frame(alert_card, bg=BG_CARD)
        self._alert_frame.pack(fill="x", padx=10, pady=(0, 10))

        # tips
        tips_card = tk.Frame(bot, bg=BG_CARD,
                              highlightbackground=CLR_BORDER, highlightthickness=1,
                              width=280)
        tips_card.pack(side="left", fill="y")
        tips_card.pack_propagate(False)
        tk.Label(tips_card, text="자세 개선 팁", bg=BG_CARD, fg=TEXT_PRI,
                 font=(FONT, 11, "bold")).pack(anchor="nw", padx=14, pady=(12, 6))
        self._build_tips(tips_card)

    def _build_tips(self, parent):
        grid = tk.Frame(parent, bg=BG_CARD)
        grid.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        for i, (title, desc) in enumerate(TIPS):
            row = i // 2
            col = i % 2
            cell = tk.Frame(grid, bg=BG_APP,
                            highlightbackground=CLR_BORDER, highlightthickness=1)
            cell.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
            grid.columnconfigure(col, weight=1)
            tk.Label(cell, text=title, bg=BG_APP, fg=TEXT_PRI,
                     font=(FONT, 9, "bold"), wraplength=110, justify="left").pack(
                anchor="nw", padx=8, pady=(8, 2))
            tk.Label(cell, text=desc, bg=BG_APP, fg=TEXT_SEC,
                     font=(FONT, 8), wraplength=110, justify="left").pack(
                anchor="nw", padx=8, pady=(0, 8))

    # ── data refresh ──────────────────────────────────────────────────────────
    def refresh(self):
        today   = date.today().isoformat()
        summary = self.data_manager.get_day_summary(today)
        alerts  = self.data_manager.get_day_alerts(today)
        stretch = self.data_manager.get_stretch_count(today)

        if summary:
            avg   = summary["avg_score"]
            col   = score_color(avg)
            grade, label = score_grade(avg)

            dur_good  = summary["good_posture_sec"]
            alert_cnt = summary["alert_count"]

            self._card_score.update(f"{avg:.0f}점", f"등급  {grade}  —  {label}", col)
            self._card_time.update(fmt_duration_ko(dur_good), "바른 자세 유지", CLR_GOOD)
            self._card_alerts.update(str(alert_cnt), "경고 발생 횟수",
                                      CLR_DANGER if alert_cnt > 0 else TEXT_SEC)
            self._ring.draw(avg)
            self._gauge_label.config(text=score_label_ko(avg), fg=col)
            self._gauge_desc.config(text=score_desc_ko(avg))
        else:
            self._card_score.update("--", "데이터 없음", TEXT_HINT)
            self._card_time.update("--", "", TEXT_HINT)
            self._card_alerts.update("0", "", TEXT_HINT)
            self._ring.draw(None)
            self._gauge_label.config(text="데이터 없음", fg=TEXT_HINT)
            self._gauge_desc.config(text="모니터링을 시작하면\n점수가 기록됩니다")

        self._card_stretch.update(
            f"{stretch} / {STRETCH_GOAL}",
            f"오늘 목표  {STRETCH_GOAL}회",
            CLR_GOOD if stretch >= STRETCH_GOAL else TEXT_PRI,
        )

        self._draw_alerts(alerts[:6])
        self._draw_chart()

    def _draw_alerts(self, alerts):
        for w in self._alert_frame.winfo_children():
            w.destroy()

        if not alerts:
            tk.Label(self._alert_frame, text="오늘 알림이 없습니다.", bg=BG_CARD,
                     fg=TEXT_HINT, font=(FONT, 9)).pack(anchor="w", padx=4, pady=6)
            return

        dot_colors = {"danger": CLR_DANGER, "warn": CLR_WARN, "info": CLR_GOOD}
        for alert in alerts:
            row = tk.Frame(self._alert_frame, bg=BG_APP,
                           highlightbackground=CLR_BORDER, highlightthickness=1)
            row.pack(fill="x", pady=2)
            sev = alert.get("severity", "info")
            tk.Label(row, text="●", bg=BG_APP, fg=dot_colors.get(sev, TEXT_HINT),
                     font=(FONT, 10)).pack(side="left", padx=(10, 6), pady=6)
            tk.Label(row, text=alert["message"], bg=BG_APP, fg=TEXT_PRI,
                     font=(FONT, 9), anchor="w").pack(side="left", fill="x", expand=True)
            tk.Label(row, text=alert["time"], bg=BG_APP, fg=TEXT_HINT,
                     font=(FONT, 8)).pack(side="right", padx=10)

    def _draw_chart(self):
        c  = self._chart_canvas
        cw = c.winfo_width()
        ch = c.winfo_height()
        if cw < 10 or ch < 10:
            return
        c.delete("all")

        today     = date.today().isoformat()
        hourly    = self.data_manager.get_hourly_scores(today)
        hours     = list(range(8, 21))
        n         = len(hours)
        pad_l, pad_r = 10, 10
        pad_t, pad_b = 10, 24
        bar_area_w   = cw - pad_l - pad_r
        bar_w        = max(4, bar_area_w // n - 4)
        gap          = (bar_area_w - bar_w * n) // (n + 1)
        chart_h      = ch - pad_t - pad_b

        bar_colors = {
            "good":   "#2ECC9A",
            "ok":     "#63B3ED",
            "warn":   "#F6AD55",
            "danger": "#FC8181",
            "empty":  "#E2E8F0",
        }

        for i, hour in enumerate(hours):
            x = pad_l + gap + i * (bar_w + gap)
            score = hourly.get(hour)

            if score is not None:
                frac  = score / 100
                bh    = max(4, int(chart_h * frac))
                y_top = pad_t + (chart_h - bh)
                if score >= 80:   col = bar_colors["good"]
                elif score >= 60: col = bar_colors["ok"]
                elif score >= 40: col = bar_colors["warn"]
                else:             col = bar_colors["danger"]
            else:
                bh    = 4
                y_top = pad_t + chart_h - bh
                col   = bar_colors["empty"]

            c.create_rectangle(x, y_top, x + bar_w, pad_t + chart_h,
                                fill=col, outline="", width=0)
            # hour label
            label = f"{hour}시"
            if hour % 2 == 0:
                c.create_text(x + bar_w // 2, ch - pad_b + 8,
                              text=label, fill=TEXT_HINT, font=(FONT, 7))

    # ── controls ──────────────────────────────────────────────────────────────
    def _on_monitor_click(self):
        if self.on_start_monitoring:
            self.on_start_monitoring()

    def _on_stretch(self):
        self.data_manager.add_stretch()
        self.refresh()

    def set_monitoring_active(self, active: bool):
        self._monitoring_active = active
        if active:
            self._monitor_btn.config(text="모니터 보기", bg="#2D7A5E")
        else:
            self._monitor_btn.config(text="실시간 시작", bg=ACCENT)

    def _tick(self):
        now  = datetime.now()
        date_str = now.strftime("%Y년 %m월 %d일, %A").replace(
            "Monday", "월요일").replace("Tuesday", "화요일").replace(
            "Wednesday", "수요일").replace("Thursday", "목요일").replace(
            "Friday", "금요일").replace("Saturday", "토요일").replace(
            "Sunday", "일요일")
        self._date_lbl.config(text=date_str)

        # sitting time from today's total duration
        today   = date.today().isoformat()
        summary = self.data_manager.get_day_summary(today)
        if summary:
            secs = summary["total_duration"]
            h, m = divmod(secs // 60, 60)
            self._sitting_lbl.config(text=f"오늘  {h}시간 {m}분 착석")
        else:
            self._sitting_lbl.config(text="오늘 착석 기록 없음")

        self.after(10000, self._tick)
