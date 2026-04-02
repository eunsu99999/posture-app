"""Shared reusable widgets: CalendarWidget, ScoreRingCanvas, MetricCard."""
import tkinter as tk
import calendar as cal_module
from datetime import date, datetime

from config import (
    FONT, BG_APP, BG_CARD, BG_ACTIVE, ACCENT, TEXT_PRI, TEXT_SEC,
    TEXT_HINT, CLR_GOOD, CLR_WARN, CLR_DANGER, CLR_BLUE, CLR_BORDER,
    score_color, score_grade, score_label_ko, score_desc_ko, fmt_duration_ko,
)


# ══════════════════════════════════════════════════════════════════════════════
# ScoreRingCanvas  — canvas-based circular gauge
# ══════════════════════════════════════════════════════════════════════════════
class ScoreRingCanvas(tk.Canvas):
    def __init__(self, parent, size=160, ring_width=14, **kwargs):
        super().__init__(parent, width=size, height=size,
                         highlightthickness=0, **kwargs)
        self._size  = size
        self._lw    = ring_width
        self.draw(None)

    def draw(self, score):
        self.delete("all")
        s  = self._size
        lw = self._lw
        cx = cy = s // 2
        r  = cx - lw

        color = score_color(score) if score is not None else CLR_BORDER
        bg    = self.cget("bg")

        # background arc
        self.create_arc(cx - r, cy - r, cx + r, cy + r,
                        start=225, extent=-270,
                        outline="#E2E8F0", width=lw, style="arc")

        if score is not None:
            extent = -(score / 5 * 270)
            self.create_arc(cx - r, cy - r, cx + r, cy + r,
                            start=225, extent=extent,
                            outline=color, width=lw, style="arc")
            self.create_text(cx, cy - 12, text=str(int(round(score))),
                             fill=color, font=(FONT, int(s * 0.22), "bold"))
            self.create_text(cx, cy + 14, text="/ 5",
                             fill=TEXT_SEC, font=(FONT, int(s * 0.08)))
        else:
            self.create_text(cx, cy, text="--",
                             fill=TEXT_HINT, font=(FONT, int(s * 0.18), "bold"))


# ══════════════════════════════════════════════════════════════════════════════
# MetricCard  — one of the 4 top-of-dashboard cards
# ══════════════════════════════════════════════════════════════════════════════
class MetricCard(tk.Frame):
    def __init__(self, parent, title, value, sub="", value_color=TEXT_PRI, **kwargs):
        super().__init__(parent, bg=BG_CARD,
                         highlightbackground=CLR_BORDER, highlightthickness=1,
                         **kwargs)
        self._title_str = title
        self._lbl_val   = None
        self._lbl_sub   = None
        self._build(title, value, sub, value_color)

    def _build(self, title, value, sub, value_color):
        tk.Label(self, text=title, bg=BG_CARD, fg=TEXT_SEC,
                 font=(FONT, 9)).pack(anchor="w", padx=14, pady=(12, 0))
        self._lbl_val = tk.Label(self, text=value, bg=BG_CARD, fg=value_color,
                                  font=(FONT, 22, "bold"))
        self._lbl_val.pack(anchor="w", padx=14, pady=(2, 0))
        self._lbl_sub = tk.Label(self, text=sub, bg=BG_CARD, fg=TEXT_SEC,
                                  font=(FONT, 9))
        self._lbl_sub.pack(anchor="w", padx=14, pady=(0, 12))

    def update(self, value, sub="", value_color=None):
        self._lbl_val.config(text=value)
        if value_color:
            self._lbl_val.config(fg=value_color)
        self._lbl_sub.config(text=sub)


# ══════════════════════════════════════════════════════════════════════════════
# CalendarWidget  — embeddable monthly calendar
# ══════════════════════════════════════════════════════════════════════════════
class CalendarWidget(tk.Frame):
    CELL_W = 90
    CELL_H = 68

    def __init__(self, parent, data_manager, on_date_click=None, **kwargs):
        super().__init__(parent, bg=BG_APP, **kwargs)
        self.data_manager  = data_manager
        self.on_date_click = on_date_click
        now = datetime.now()
        self.cur_year  = now.year
        self.cur_month = now.month
        self._build_chrome()
        self._render()

    def _build_chrome(self):
        nav = tk.Frame(self, bg=BG_CARD,
                       highlightbackground=CLR_BORDER, highlightthickness=1)
        nav.pack(fill="x", padx=0, pady=(0, 2))

        tk.Button(nav, text="<", bg=BG_CARD, fg=TEXT_SEC, bd=0,
                  padx=14, pady=6, cursor="hand2", font=(FONT, 11),
                  command=self._prev).pack(side="left")
        self.month_lbl = tk.Label(nav, text="", bg=BG_CARD, fg=TEXT_PRI,
                                   font=(FONT, 13, "bold"))
        self.month_lbl.pack(side="left", expand=True)
        tk.Button(nav, text=">", bg=BG_CARD, fg=TEXT_SEC, bd=0,
                  padx=14, pady=6, cursor="hand2", font=(FONT, 11),
                  command=self._next).pack(side="right")

        # legend
        leg = tk.Frame(self, bg=BG_APP, pady=4)
        leg.pack(fill="x", padx=4)
        for lbl, clr in [("완벽 1", CLR_GOOD), ("허용 2", CLR_BLUE),
                          ("주의 3", CLR_WARN), ("경고+ 4~5", CLR_DANGER)]:
            dot = tk.Label(leg, text="●", bg=BG_APP, fg=clr, font=(FONT, 10))
            dot.pack(side="left", padx=(4, 1))
            tk.Label(leg, text=lbl, bg=BG_APP, fg=TEXT_SEC,
                     font=(FONT, 8)).pack(side="left", padx=(0, 8))

        self.grid_f = tk.Frame(self, bg=BG_APP, padx=2, pady=2)
        self.grid_f.pack(fill="both", expand=True)

    def _render(self):
        for w in self.grid_f.winfo_children():
            w.destroy()
        self.month_lbl.config(text=f"{self.cur_year}년  {self.cur_month:02d}월")

        days_ko = ["월", "화", "수", "목", "금", "토", "일"]
        for col, name in enumerate(days_ko):
            c = CLR_DANGER if col >= 5 else TEXT_SEC
            tk.Label(self.grid_f, text=name, bg=BG_APP, fg=c,
                     font=(FONT, 9, "bold"), width=11).grid(
                row=0, column=col, pady=(0, 4))

        month_data = self.data_manager.get_month_data(self.cur_year, self.cur_month)
        today      = date.today()

        for row, week in enumerate(cal_module.monthcalendar(self.cur_year, self.cur_month), 1):
            for col, day in enumerate(week):
                if day == 0:
                    tk.Frame(self.grid_f, bg=BG_APP,
                             width=self.CELL_W, height=self.CELL_H).grid(
                        row=row, column=col, padx=2, pady=2)
                    continue

                is_today   = (day == today.day and
                              self.cur_month == today.month and
                              self.cur_year  == today.year)
                border_col = ACCENT if is_today else CLR_BORDER
                day_col    = ACCENT if is_today else (CLR_DANGER if col >= 5 else TEXT_PRI)
                cell_bg    = BG_ACTIVE if is_today else BG_CARD

                cell = tk.Frame(self.grid_f, bg=cell_bg,
                                width=self.CELL_W, height=self.CELL_H,
                                highlightbackground=border_col, highlightthickness=1)
                cell.grid(row=row, column=col, padx=2, pady=2)
                cell.pack_propagate(False)

                tk.Label(cell, text=str(day), bg=cell_bg, fg=day_col,
                         font=(FONT, 10, "bold")).pack(anchor="nw", padx=5, pady=3)

                if day in month_data:
                    s   = month_data[day]
                    avg = s["avg_score"]
                    sc  = score_color(avg)
                    mins = s["total_duration"] // 60
                    t_str = f"{mins//60}h{mins%60}m" if mins >= 60 else f"{mins}m"
                    tk.Label(cell, text=f"{avg:.1f}점", bg=cell_bg, fg=sc,
                             font=(FONT, 10, "bold")).pack(anchor="center")
                    tk.Label(cell, text=t_str, bg=cell_bg, fg=TEXT_HINT,
                             font=(FONT, 7)).pack(anchor="center")
                    d_str = date(self.cur_year, self.cur_month, day).isoformat()
                    self._bind_click(cell, d_str)

    def _bind_click(self, cell, date_str):
        def handler(e=None):
            if self.on_date_click:
                self.on_date_click(date_str)
        cell.config(cursor="hand2")
        cell.bind("<Button-1>", handler)
        for ch in cell.winfo_children():
            ch.config(cursor="hand2")
            ch.bind("<Button-1>", handler)

    def _prev(self):
        if self.cur_month == 1:
            self.cur_month = 12; self.cur_year -= 1
        else:
            self.cur_month -= 1
        self._render()

    def _next(self):
        if self.cur_month == 12:
            self.cur_month = 1; self.cur_year += 1
        else:
            self.cur_month += 1
        self._render()

    def refresh(self):
        self._render()
