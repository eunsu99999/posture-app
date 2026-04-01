"""DashboardPage — main overview screen."""
import tkinter as tk
from datetime import date, datetime

from config import (
    FONT, BG_APP, BG_CARD, BG_ACTIVE, ACCENT, ACCENT_DRK,
    TEXT_PRI, TEXT_SEC, TEXT_HINT,
    CLR_GOOD, CLR_WARN, CLR_DANGER, CLR_BLUE, CLR_BORDER,
    score_color, score_grade, score_label_ko, score_desc_ko,
    fmt_duration_ko,
)
STRETCH_GOAL_DEFAULT = 5
from ui.widgets import MetricCard, ScoreRingCanvas

TIPS = [
    ("모니터 높이",   "화면 상단이 눈높이와 같거나 약간 낮게 두세요."),
    ("발 위치",       "발바닥이 바닥에 완전히 닿도록 의자 높이를 조정하세요."),
    ("허리 지지",     "허리 쿠션으로 요추 곡선을 자연스럽게 유지하세요."),
    ("20-20-20 규칙", "20분마다 20초간 6m 거리를 바라보세요."),
]

# y축 기준선 (점수)
CHART_GUIDES = [
    (80, CLR_GOOD,   "80"),
    (60, CLR_BLUE,   "60"),
    (40, CLR_WARN,   "40"),
]


class DashboardPage(tk.Frame):
    def __init__(self, parent, data_manager, app_settings=None,
                 on_start_monitoring=None, on_stop_monitoring=None, **kwargs):
        super().__init__(parent, bg=BG_APP, **kwargs)
        self.data_manager        = data_manager
        self.app_settings        = app_settings
        self.on_start_monitoring = on_start_monitoring
        self.on_stop_monitoring  = on_stop_monitoring
        self._monitoring_active  = False

        self._build_scroll_container()

        self._build(self._inner)
        self.refresh()
        self._tick()

    # ── scrollable container ──────────────────────────────────────────────────
    def _build_scroll_container(self):
        self._canvas = tk.Canvas(self, bg=BG_APP, highlightthickness=0)
        self._vbar   = tk.Scrollbar(self, orient="vertical",
                                    command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vbar.set)
        self._vbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=BG_APP)
        self._win   = self._canvas.create_window((0, 0), window=self._inner,
                                                  anchor="nw")
        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<Enter>", lambda e: self._canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self._canvas.bind("<Leave>", lambda e: self._canvas.unbind_all("<MouseWheel>"))

    @property
    def _stretch_goal(self):
        if self.app_settings:
            return self.app_settings.stretch_goal
        return STRETCH_GOAL_DEFAULT

    def _on_inner_configure(self, e):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, e):
        self._canvas.itemconfig(self._win, width=e.width)

    def _on_mousewheel(self, e):
        self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    # ── build content ─────────────────────────────────────────────────────────
    def _build(self, root):

        # ── header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(root, bg=BG_APP)
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
        self._sitting_lbl.pack(side="left", padx=(0, 8))
        self._monitor_btn = tk.Button(
            right_hdr, text="실시간 시작", bg=ACCENT, fg="#FFFFFF",
            font=(FONT, 10, "bold"), bd=0, padx=16, pady=8, cursor="hand2",
            activebackground=ACCENT_DRK, activeforeground="#FFFFFF",
            command=self._on_monitor_click,
        )
        self._monitor_btn.pack(side="left", padx=(0, 6))
        self._stop_btn = tk.Button(
            right_hdr, text="측정 중지", bg="#FFF5F5", fg=CLR_DANGER,
            font=(FONT, 10, "bold"), bd=0, padx=14, pady=8, cursor="hand2",
            activebackground="#FED7D7", activeforeground=CLR_DANGER,
            command=self._on_stop_click,
        )

        tk.Frame(root, bg=CLR_BORDER, height=1).pack(fill="x", padx=20, pady=(12, 0))

        # ── 4 metric cards ────────────────────────────────────────────────────
        cards_row = tk.Frame(root, bg=BG_APP)
        cards_row.pack(fill="x", padx=20, pady=12)

        self._card_score   = MetricCard(cards_row, "오늘 자세 점수", "--", "", TEXT_PRI)
        self._card_time    = MetricCard(cards_row, "바른 자세 시간", "--", "", CLR_GOOD)
        self._card_alerts  = MetricCard(cards_row, "경고 횟수",      "--", "", CLR_DANGER)
        self._card_stretch = MetricCard(cards_row, "스트레칭 완료",  "--",
                                         f"오늘 목표  {self._stretch_goal}회", TEXT_PRI)
        for card in (self._card_score, self._card_time,
                     self._card_alerts, self._card_stretch):
            card.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=4)

        tk.Button(self._card_stretch, text="+ 완료", bg=BG_ACTIVE, fg=ACCENT,
                  bd=0, font=(FONT, 8, "bold"), padx=8, pady=3, cursor="hand2",
                  activebackground=BG_ACTIVE,
                  command=self._on_stretch).pack(anchor="e", padx=14, pady=(0, 8))

        # ── 바른 자세 비율 바 (전체 대비) ────────────────────────────────────
        ratio_card = tk.Frame(root, bg=BG_CARD,
                               highlightbackground=CLR_BORDER, highlightthickness=1)
        ratio_card.pack(fill="x", padx=20, pady=(0, 10))

        ratio_top = tk.Frame(ratio_card, bg=BG_CARD)
        ratio_top.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(ratio_top, text="바른 자세 비율", bg=BG_CARD, fg=TEXT_PRI,
                 font=(FONT, 10, "bold")).pack(side="left")
        self._ratio_pct_lbl = tk.Label(ratio_top, text="--", bg=BG_CARD,
                                        fg=CLR_GOOD, font=(FONT, 10, "bold"))
        self._ratio_pct_lbl.pack(side="right")

        # 바 컨테이너
        bar_outer = tk.Frame(ratio_card, bg=BG_CARD)
        bar_outer.pack(fill="x", padx=14, pady=(0, 4))
        self._ratio_bar_bg = tk.Frame(bar_outer, bg=CLR_BORDER, height=12)
        self._ratio_bar_bg.pack(fill="x")
        self._ratio_bar_fg = tk.Frame(self._ratio_bar_bg, bg=CLR_GOOD, height=12)
        self._ratio_bar_fg.place(x=0, y=0, relheight=1, width=0)

        ratio_bot = tk.Frame(ratio_card, bg=BG_CARD)
        ratio_bot.pack(fill="x", padx=14, pady=(2, 10))
        self._ratio_good_lbl = tk.Label(ratio_bot, text="바른 자세: --",
                                         bg=BG_CARD, fg=CLR_GOOD, font=(FONT, 8))
        self._ratio_good_lbl.pack(side="left")
        self._ratio_total_lbl = tk.Label(ratio_bot, text="전체: --",
                                          bg=BG_CARD, fg=TEXT_SEC, font=(FONT, 8))
        self._ratio_total_lbl.pack(side="right")

        # ── middle row: chart + gauge ─────────────────────────────────────────
        mid = tk.Frame(root, bg=BG_APP)
        mid.pack(fill="x", padx=20, pady=(0, 10))

        # hourly bar chart
        chart_card = tk.Frame(mid, bg=BG_CARD,
                               highlightbackground=CLR_BORDER, highlightthickness=1)
        chart_card.pack(side="left", fill="both", expand=True, padx=(0, 10))

        chart_hdr = tk.Frame(chart_card, bg=BG_CARD)
        chart_hdr.pack(fill="x", padx=14, pady=(12, 0))
        tk.Label(chart_hdr, text="시간대별 자세 점수", bg=BG_CARD, fg=TEXT_PRI,
                 font=(FONT, 11, "bold")).pack(side="left")
        # 범례
        leg = tk.Frame(chart_hdr, bg=BG_CARD)
        leg.pack(side="right")
        for lbl, clr in [("80+", CLR_GOOD), ("60+", CLR_BLUE),
                          ("40+", CLR_WARN), ("~40", CLR_DANGER)]:
            tk.Label(leg, text="●", bg=BG_CARD, fg=clr,
                     font=(FONT, 9)).pack(side="left", padx=(4, 0))
            tk.Label(leg, text=lbl, bg=BG_CARD, fg=TEXT_SEC,
                     font=(FONT, 8)).pack(side="left", padx=(1, 6))

        self._chart_canvas = tk.Canvas(chart_card, bg=BG_CARD,
                                        highlightthickness=0, height=180)
        self._chart_canvas.pack(fill="x", padx=14, pady=(4, 12))
        self._chart_canvas.bind("<Configure>", lambda e: self._draw_chart())

        # gauge
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

        # ── bottom: tips (full width) ─────────────────────────────────────────
        tips_card = tk.Frame(root, bg=BG_CARD,
                              highlightbackground=CLR_BORDER, highlightthickness=1)
        tips_card.pack(fill="x", padx=20, pady=(0, 20))
        tk.Label(tips_card, text="자세 개선 팁", bg=BG_CARD, fg=TEXT_PRI,
                 font=(FONT, 11, "bold")).pack(anchor="nw", padx=14, pady=(12, 6))
        self._build_tips(tips_card)

    def _build_tips(self, parent):
        grid = tk.Frame(parent, bg=BG_CARD)
        grid.pack(fill="x", padx=10, pady=(0, 12))
        for i, (title, desc) in enumerate(TIPS):
            r = i // 2
            c = i % 2
            cell = tk.Frame(grid, bg=BG_APP,
                            highlightbackground=CLR_BORDER, highlightthickness=1)
            cell.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")
            grid.columnconfigure(c, weight=1)
            tk.Label(cell, text=title, bg=BG_APP, fg=TEXT_PRI,
                     font=(FONT, 9, "bold"), wraplength=200, justify="left").pack(
                anchor="nw", padx=10, pady=(8, 2))
            tk.Label(cell, text=desc, bg=BG_APP, fg=TEXT_SEC,
                     font=(FONT, 8), wraplength=200, justify="left").pack(
                anchor="nw", padx=10, pady=(0, 8))

    # ── data refresh ──────────────────────────────────────────────────────────
    def refresh(self):
        today   = date.today().isoformat()
        summary = self.data_manager.get_day_summary(today)
        stretch = self.data_manager.get_stretch_count(today)

        if summary:
            avg        = summary["avg_score"]
            col        = score_color(avg)
            grade, lbl = score_grade(avg)
            good_sec   = summary["good_posture_sec"]
            total_sec  = summary["total_duration"]
            alert_cnt  = summary["alert_count"]

            self._card_score.update(f"{avg:.0f}점", f"등급  {grade}  —  {lbl}", col)
            self._card_time.update(fmt_duration_ko(good_sec), "바른 자세 유지", CLR_GOOD)
            self._card_alerts.update(str(alert_cnt), "경고 발생 횟수",
                                      CLR_DANGER if alert_cnt > 0 else TEXT_SEC)
            self._ring.draw(avg)
            self._gauge_label.config(text=score_label_ko(avg), fg=col)
            self._gauge_desc.config(text=score_desc_ko(avg))

            # 바른 자세 비율 바
            self._update_ratio_bar(good_sec, total_sec)
        else:
            self._card_score.update("--", "데이터 없음", TEXT_HINT)
            self._card_time.update("--", "", TEXT_HINT)
            self._card_alerts.update("0", "", TEXT_HINT)
            self._ring.draw(None)
            self._gauge_label.config(text="데이터 없음", fg=TEXT_HINT)
            self._gauge_desc.config(text="모니터링을 시작하면\n점수가 기록됩니다")
            self._update_ratio_bar(0, 0)

        self._card_stretch.update(
            f"{stretch} / {self._stretch_goal}",
            f"오늘 목표  {self._stretch_goal}회",
            CLR_GOOD if stretch >= self._stretch_goal else TEXT_PRI,
        )
        self._draw_chart()

    def _update_ratio_bar(self, good_sec, total_sec):
        if total_sec > 0:
            ratio = min(1.0, good_sec / total_sec)
            pct   = int(ratio * 100)
            col   = score_color(pct)
            self._ratio_pct_lbl.config(text=f"{pct}%", fg=col)
            self._ratio_bar_fg.config(bg=col)
            self._ratio_good_lbl.config(text=f"바른 자세: {fmt_duration_ko(good_sec)}")
            self._ratio_total_lbl.config(text=f"전체 모니터링: {fmt_duration_ko(total_sec)}")
            # 바 너비 갱신
            self.update_idletasks()
            bw = self._ratio_bar_bg.winfo_width()
            if bw > 1:
                self._ratio_bar_fg.place(x=0, y=0, relheight=1,
                                          width=max(0, int(bw * ratio)))
        else:
            self._ratio_pct_lbl.config(text="--", fg=TEXT_HINT)
            self._ratio_bar_fg.place(x=0, y=0, relheight=1, width=0)
            self._ratio_good_lbl.config(text="바른 자세: --")
            self._ratio_total_lbl.config(text="전체 모니터링: --")

    def _draw_chart(self):
        c  = self._chart_canvas
        cw = c.winfo_width()
        ch = c.winfo_height()
        if cw < 10 or ch < 10:
            return
        c.delete("all")

        today  = date.today().isoformat()
        hourly = self.data_manager.get_hourly_scores(today)
        hours  = list(range(8, 21))
        n      = len(hours)

        pad_l = 36   # 왼쪽 여백 (y축 레이블용)
        pad_r = 10
        pad_t = 10
        pad_b = 24   # 아래 여백 (x축 레이블용)

        bar_area_w = cw - pad_l - pad_r
        bar_w      = max(4, bar_area_w // n - 6)
        gap        = (bar_area_w - bar_w * n) // (n + 1)
        chart_h    = ch - pad_t - pad_b
        chart_bot  = pad_t + chart_h

        # ── y축 기준선 ─────────────────────────────────────────────────────────
        for score_val, guide_col, label in CHART_GUIDES:
            y = pad_t + chart_h - int(chart_h * score_val / 100)
            # 점선
            c.create_line(pad_l, y, cw - pad_r, y,
                          fill=guide_col, dash=(4, 3), width=1)
            # 레이블
            c.create_text(pad_l - 4, y, text=label, anchor="e",
                          fill=guide_col, font=(FONT, 7, "bold"))

        # ── 막대 그래프 ────────────────────────────────────────────────────────
        for i, hour in enumerate(hours):
            x     = pad_l + gap + i * (bar_w + gap)
            score = hourly.get(hour)

            if score is not None:
                frac  = score / 100
                bh    = max(4, int(chart_h * frac))
                y_top = chart_bot - bh
                if score >= 80:   col = CLR_GOOD
                elif score >= 60: col = CLR_BLUE
                elif score >= 40: col = CLR_WARN
                else:             col = CLR_DANGER
            else:
                bh    = 4
                y_top = chart_bot - bh
                col   = CLR_BORDER

            c.create_rectangle(x, y_top, x + bar_w, chart_bot,
                                fill=col, outline="", width=0)

            # x축 레이블 (짝수 시간만)
            if hour % 2 == 0:
                c.create_text(x + bar_w // 2, ch - pad_b + 10,
                              text=f"{hour}시", fill=TEXT_HINT, font=(FONT, 7))

        # ── x축 기준선 ─────────────────────────────────────────────────────────
        c.create_line(pad_l, chart_bot, cw - pad_r, chart_bot,
                      fill=CLR_BORDER, width=1)

    # ── controls ──────────────────────────────────────────────────────────────
    def _on_monitor_click(self):
        if self.on_start_monitoring:
            self.on_start_monitoring()

    def _on_stop_click(self):
        if self.on_stop_monitoring:
            self.on_stop_monitoring()

    def _on_stretch(self):
        self.data_manager.add_stretch()
        self.refresh()

    def set_monitoring_active(self, active: bool):
        self._monitoring_active = active
        if active:
            self._monitor_btn.config(text="모니터 보기", bg="#2D7A5E")
            self._stop_btn.pack(side="left")
        else:
            self._monitor_btn.config(text="실시간 시작", bg=ACCENT)
            self._stop_btn.pack_forget()

    def _tick(self):
        now      = datetime.now()
        weekdays = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        wd       = weekdays[now.weekday()]
        self._date_lbl.config(
            text=f"{now.year}년 {now.month}월 {now.day}일, {wd}")

        today   = date.today().isoformat()
        summary = self.data_manager.get_day_summary(today)
        if summary:
            secs = summary["total_duration"]
            h, m = divmod(secs // 60, 60)
            self._sitting_lbl.config(text=f"오늘  {h}시간 {m}분 착석")
        else:
            self._sitting_lbl.config(text="오늘 착석 기록 없음")

        self.after(10000, self._tick)
