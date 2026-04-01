"""HistoryPage — calendar + day detail panel."""
import tkinter as tk
from datetime import date

from config import (
    FONT, BG_APP, BG_CARD, BG_ACTIVE, ACCENT, TEXT_PRI, TEXT_SEC, TEXT_HINT,
    CLR_GOOD, CLR_WARN, CLR_DANGER, CLR_BLUE, CLR_BORDER,
    score_color, score_grade, score_label_ko, fmt_duration_ko,
)
from ui.widgets import CalendarWidget, ScoreRingCanvas


class HistoryPage(tk.Frame):
    def __init__(self, parent, data_manager, **kwargs):
        super().__init__(parent, bg=BG_APP, **kwargs)
        self.data_manager = data_manager
        self._build()

    def _build(self):
        # page title
        hdr = tk.Frame(self, bg=BG_APP)
        hdr.pack(fill="x", padx=20, pady=(18, 8))
        tk.Label(hdr, text="히스토리", bg=BG_APP, fg=TEXT_PRI,
                 font=(FONT, 18, "bold")).pack(anchor="w")
        tk.Label(hdr, text="날짜를 클릭하면 해당 날의 상세 기록을 볼 수 있습니다.",
                 bg=BG_APP, fg=TEXT_SEC, font=(FONT, 10)).pack(anchor="w")

        tk.Frame(self, bg=CLR_BORDER, height=1).pack(fill="x", padx=20, pady=(0, 10))

        body = tk.Frame(self, bg=BG_APP)
        body.pack(fill="both", expand=True, padx=20, pady=0)

        # left: calendar
        cal_wrap = tk.Frame(body, bg=BG_APP)
        cal_wrap.pack(side="left", fill="both", expand=True, padx=(0, 14))

        self.cal = CalendarWidget(
            cal_wrap, self.data_manager,
            on_date_click=self._on_date_click,
        )
        self.cal.pack(fill="both", expand=True)

        # right: day detail panel
        detail_wrap = tk.Frame(body, bg=BG_APP, width=300)
        detail_wrap.pack(side="left", fill="y")
        detail_wrap.pack_propagate(False)

        self._detail_panel = DayDetailPanel(detail_wrap)
        self._detail_panel.pack(fill="both", expand=True)

    def _on_date_click(self, date_str):
        summary = self.data_manager.get_day_summary(date_str)
        alerts  = self.data_manager.get_day_alerts(date_str)
        self._detail_panel.show(date_str, summary, alerts)

    def refresh(self):
        self.cal.refresh()


# ══════════════════════════════════════════════════════════════════════════════
# DayDetailPanel — shows stats for a selected date
# ══════════════════════════════════════════════════════════════════════════════
class DayDetailPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG_CARD,
                         highlightbackground=CLR_BORDER, highlightthickness=1,
                         **kwargs)
        self._build_placeholder()

    def _build_placeholder(self):
        tk.Label(self, text="날짜를 선택하세요", bg=BG_CARD, fg=TEXT_HINT,
                 font=(FONT, 12)).pack(expand=True)

    def show(self, date_str, summary, alerts):
        for w in self.winfo_children():
            w.destroy()

        # header
        hdr = tk.Frame(self, bg=BG_CARD)
        hdr.pack(fill="x", padx=14, pady=(14, 8))
        year, month, day = date_str.split("-")
        tk.Label(hdr, text=f"{year}년 {month}월 {day}일",
                 bg=BG_CARD, fg=TEXT_PRI, font=(FONT, 13, "bold")).pack(anchor="w")

        if not summary:
            tk.Label(self, text="해당 날짜의\n기록이 없습니다.", bg=BG_CARD,
                     fg=TEXT_HINT, font=(FONT, 11), justify="center").pack(expand=True)
            return

        avg   = summary["avg_score"]
        col   = score_color(avg)
        grade, label = score_grade(avg)

        # ring + score
        ring_row = tk.Frame(self, bg=BG_CARD)
        ring_row.pack(fill="x", padx=14, pady=(0, 8))

        ring = ScoreRingCanvas(ring_row, size=110, ring_width=12, bg=BG_CARD)
        ring.pack(side="left")
        ring.draw(avg)

        info = tk.Frame(ring_row, bg=BG_CARD)
        info.pack(side="left", padx=(10, 0))
        tk.Label(info, text=score_label_ko(avg), bg=BG_CARD, fg=col,
                 font=(FONT, 12, "bold")).pack(anchor="w", pady=(14, 2))
        tk.Label(info, text=f"등급  {grade}  —  {label}", bg=BG_CARD,
                 fg=TEXT_SEC, font=(FONT, 9)).pack(anchor="w")

        # stats grid
        stats = [
            ("자세 점수",      f"{avg:.1f}점",                                 col),
            ("바른 자세 시간", fmt_duration_ko(summary["good_posture_sec"]),   CLR_GOOD),
            ("경고 횟수",      f"{summary['alert_count']}회",
             CLR_DANGER if summary["alert_count"] > 0 else TEXT_SEC),
            ("스트레칭",       f"{summary.get('stretches', 0)}회",             CLR_BLUE),
        ]
        for stat_label, stat_val, stat_col in stats:
            row = tk.Frame(self, bg=BG_APP,
                           highlightbackground=CLR_BORDER, highlightthickness=1)
            row.pack(fill="x", padx=14, pady=2)
            tk.Label(row, text=stat_label, bg=BG_APP, fg=TEXT_SEC,
                     font=(FONT, 9), width=14, anchor="w").pack(
                side="left", padx=10, pady=8)
            tk.Label(row, text=stat_val, bg=BG_APP, fg=stat_col,
                     font=(FONT, 10, "bold")).pack(side="right", padx=10)

        # total sitting time
        dur_row = tk.Frame(self, bg=BG_APP,
                           highlightbackground=CLR_BORDER, highlightthickness=1)
        dur_row.pack(fill="x", padx=14, pady=2)
        tk.Label(dur_row, text="총 착석 시간", bg=BG_APP, fg=TEXT_SEC,
                 font=(FONT, 9), width=14, anchor="w").pack(
            side="left", padx=10, pady=8)
        dur_str = fmt_duration_ko(summary["total_duration"])
        tk.Label(dur_row, text=dur_str, bg=BG_APP, fg=TEXT_PRI,
                 font=(FONT, 10, "bold")).pack(side="right", padx=10)

        # alerts
        if alerts:
            tk.Label(self, text="알림 기록", bg=BG_CARD, fg=TEXT_SEC,
                     font=(FONT, 9, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
            dot_colors = {"danger": CLR_DANGER, "warn": CLR_WARN, "info": CLR_GOOD}
            for alert in alerts[:4]:
                arow = tk.Frame(self, bg=BG_APP,
                                highlightbackground=CLR_BORDER, highlightthickness=1)
                arow.pack(fill="x", padx=14, pady=2)
                sev = alert.get("severity", "info")
                tk.Label(arow, text="●", bg=BG_APP, fg=dot_colors.get(sev, TEXT_HINT),
                         font=(FONT, 9)).pack(side="left", padx=(8, 4), pady=6)
                tk.Label(arow, text=alert["message"], bg=BG_APP, fg=TEXT_PRI,
                         font=(FONT, 8), wraplength=180, justify="left").pack(
                    side="left", fill="x", expand=True, pady=6)
                tk.Label(arow, text=alert["time"], bg=BG_APP, fg=TEXT_HINT,
                         font=(FONT, 8)).pack(side="right", padx=8)
