"""ReportPage — 기간별 자세 분석 리포트."""
import tkinter as tk
from datetime import date, timedelta

from config import (
    FONT, BG_APP, BG_CARD, BG_ACTIVE, ACCENT,
    TEXT_PRI, TEXT_SEC, TEXT_HINT,
    CLR_GOOD, CLR_WARN, CLR_DANGER, CLR_BLUE, CLR_BORDER,
    score_color, score_grade, fmt_duration_ko,
)

PERIODS = [("오늘", "today"), ("이번 주", "week"), ("이번 달", "month")]


class ReportPage(tk.Frame):
    def __init__(self, parent, data_manager, app_settings, **kwargs):
        super().__init__(parent, bg=BG_APP, **kwargs)
        self.data_manager  = data_manager
        self.app_settings  = app_settings
        self._period       = "week"
        self._tab_btns     = {}
        self._data_cache   = {}
        self._series_cache = []

        self._build_scroll_container()
        self._build(self._inner)
        self.refresh()

    # ── 스크롤 컨테이너 ───────────────────────────────────────────────────────
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
        self._inner.bind("<Configure>",
                          lambda e: self._canvas.configure(
                              scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
                          lambda e: self._canvas.itemconfig(
                              self._win, width=e.width))
        self._canvas.bind("<Enter>", lambda e: self._canvas.bind_all(
            "<MouseWheel>",
            lambda ev: self._canvas.yview_scroll(
                int(-1 * (ev.delta / 120)), "units")))
        self._canvas.bind("<Leave>",
                          lambda e: self._canvas.unbind_all("<MouseWheel>"))

    # ── 전체 레이아웃 ─────────────────────────────────────────────────────────
    def _build(self, root):
        # 헤더
        hdr = tk.Frame(root, bg=BG_APP)
        hdr.pack(fill="x", padx=20, pady=(18, 8))
        tk.Label(hdr, text="리포트", bg=BG_APP, fg=TEXT_PRI,
                 font=(FONT, 18, "bold")).pack(anchor="w")
        tk.Label(hdr, text="기간별 자세 데이터를 분석합니다.",
                 bg=BG_APP, fg=TEXT_SEC, font=(FONT, 10)).pack(anchor="w")

        # 기간 탭
        tab_row = tk.Frame(root, bg=BG_APP)
        tab_row.pack(fill="x", padx=20, pady=(8, 12))
        for label, key in PERIODS:
            btn = tk.Label(tab_row, text=label, bg=BG_CARD, fg=TEXT_SEC,
                           font=(FONT, 10), padx=18, pady=8, cursor="hand2",
                           highlightbackground=CLR_BORDER, highlightthickness=1)
            btn.pack(side="left", padx=(0, 6))
            btn.bind("<Button-1>", lambda e, k=key: self._set_period(k))
            self._tab_btns[key] = btn
        self._update_tabs()

        tk.Frame(root, bg=CLR_BORDER, height=1).pack(fill="x", padx=20,
                                                      pady=(0, 16))

        # 요약 카드 4개
        cards_frame = tk.Frame(root, bg=BG_APP)
        cards_frame.pack(fill="x", padx=20, pady=(0, 12))
        self._card_avg   = self._summary_card(cards_frame, "평균 점수",      "--", last=False)
        self._card_time  = self._summary_card(cards_frame, "모니터링 시간",   "--", last=False)
        self._card_ratio = self._summary_card(cards_frame, "바른 자세 비율", "--", last=False)
        self._card_alert = self._summary_card(cards_frame, "경고 횟수",      "--", last=True)

        # 주간/기간 점수 추이 차트
        bar_wrap = self._section_card(root, "점수 추이")
        self._bar_canvas = tk.Canvas(bar_wrap, bg=BG_CARD, height=190,
                                      highlightthickness=0)
        self._bar_canvas.pack(fill="x", padx=16, pady=(0, 12))
        self._bar_canvas.bind("<Configure>", lambda e: self._draw_bar_chart())

        # 시간대별 + 등급 분포 (나란히)
        mid = tk.Frame(root, bg=BG_APP)
        mid.pack(fill="x", padx=20, pady=(0, 12))

        hourly_wrap = tk.Frame(mid, bg=BG_CARD,
                                highlightbackground=CLR_BORDER, highlightthickness=1)
        hourly_wrap.pack(side="left", fill="both", expand=True)
        tk.Label(hourly_wrap, text="시간대별 패턴", bg=BG_CARD, fg=TEXT_SEC,
                 font=(FONT, 9)).pack(anchor="nw", padx=12, pady=(10, 4))
        self._hourly_canvas = tk.Canvas(hourly_wrap, bg=BG_CARD, height=130,
                                         highlightthickness=0)
        self._hourly_canvas.pack(fill="x", padx=12, pady=(0, 12))
        self._hourly_canvas.bind("<Configure>", lambda e: self._draw_hourly())

        grade_wrap = tk.Frame(mid, bg=BG_CARD,
                               highlightbackground=CLR_BORDER, highlightthickness=1)
        grade_wrap.pack(side="left", fill="both", expand=True, padx=(8, 0))
        tk.Label(grade_wrap, text="등급 분포", bg=BG_CARD, fg=TEXT_SEC,
                 font=(FONT, 9)).pack(anchor="nw", padx=12, pady=(10, 4))
        self._grade_canvas = tk.Canvas(grade_wrap, bg=BG_CARD, height=130,
                                        highlightthickness=0)
        self._grade_canvas.pack(fill="x", padx=12, pady=(0, 12))
        self._grade_canvas.bind("<Configure>", lambda e: self._draw_grade_dist())

        # 스트레칭 달성률
        stretch_wrap = self._section_card(root, "스트레칭 달성률")
        si = tk.Frame(stretch_wrap, bg=BG_CARD)
        si.pack(fill="x", padx=16, pady=(0, 16))

        top_row = tk.Frame(si, bg=BG_CARD)
        top_row.pack(fill="x", pady=(0, 6))
        self._stretch_count_lbl = tk.Label(top_row, text="0 / 5회",
                                            bg=BG_CARD, fg=TEXT_PRI,
                                            font=(FONT, 13, "bold"))
        self._stretch_count_lbl.pack(side="left")
        self._stretch_hint_lbl = tk.Label(top_row, text="",
                                           bg=BG_CARD, fg=TEXT_HINT,
                                           font=(FONT, 9))
        self._stretch_hint_lbl.pack(side="left", padx=(12, 0))

        bar_bg = tk.Frame(si, bg=CLR_BORDER, height=12)
        bar_bg.pack(fill="x")
        self._stretch_bar    = tk.Frame(bar_bg, bg=CLR_GOOD, height=12, width=0)
        self._stretch_bar.place(x=0, y=0, relheight=1)
        self._stretch_bar_bg = bar_bg

        # 인사이트
        insight_wrap = self._section_card(root, "인사이트")
        self._insight_lbl = tk.Label(insight_wrap, text="",
                                      bg=BG_CARD, fg=TEXT_SEC,
                                      font=(FONT, 10), wraplength=900,
                                      justify="left", anchor="w")
        self._insight_lbl.pack(fill="x", padx=16, pady=(0, 16))

        tk.Frame(root, bg=BG_APP, height=24).pack()

    # ── 헬퍼 위젯 ─────────────────────────────────────────────────────────────
    def _section_card(self, parent, title):
        f = tk.Frame(parent, bg=BG_CARD,
                     highlightbackground=CLR_BORDER, highlightthickness=1)
        f.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(f, text=title, bg=BG_CARD, fg=TEXT_SEC,
                 font=(FONT, 9)).pack(anchor="nw", padx=12, pady=(10, 6))
        return f

    def _summary_card(self, parent, label, value, last=False):
        f = tk.Frame(parent, bg=BG_CARD,
                     highlightbackground=CLR_BORDER, highlightthickness=1)
        f.pack(side="left", fill="both", expand=True,
               padx=(0, 0 if last else 8))
        tk.Label(f, text=label, bg=BG_CARD, fg=TEXT_SEC,
                 font=(FONT, 8)).pack(anchor="w", padx=12, pady=(10, 2))
        lbl = tk.Label(f, text=value, bg=BG_CARD, fg=TEXT_PRI,
                       font=(FONT, 16, "bold"))
        lbl.pack(anchor="w", padx=12, pady=(0, 12))
        return lbl

    # ── 기간 전환 ─────────────────────────────────────────────────────────────
    def _set_period(self, period):
        self._period = period
        self._update_tabs()
        self.refresh()

    def _update_tabs(self):
        for key, btn in self._tab_btns.items():
            if key == self._period:
                btn.config(bg=BG_ACTIVE, fg=ACCENT, font=(FONT, 10, "bold"),
                           highlightbackground=ACCENT)
            else:
                btn.config(bg=BG_CARD, fg=TEXT_SEC, font=(FONT, 10),
                           highlightbackground=CLR_BORDER)

    # ── 데이터 집계 ───────────────────────────────────────────────────────────
    def _get_date_range(self):
        today = date.today()
        if self._period == "today":
            return [today]
        elif self._period == "week":
            return [today - timedelta(days=i) for i in range(6, -1, -1)]
        else:
            days, d = [], date(today.year, today.month, 1)
            while d.month == today.month and d <= today:
                days.append(d)
                d += timedelta(days=1)
            return days

    def _aggregate(self):
        dates  = self._get_date_range()
        all_scores, total_dur, total_alerts, total_stretch = [], 0, 0, 0
        grade_counts = {"완벽": 0, "허용": 0, "주의": 0, "경고": 0, "위험": 0}
        hourly_raw   = {}

        for d in dates:
            d_str   = d.isoformat()
            summary = self.data_manager.get_day_summary(d_str)
            if summary:
                for session in summary["sessions"]:
                    for entry in session.get("scores", []):
                        sc = entry["score"]
                        all_scores.append(sc)
                        g, _ = score_grade(sc)
                        grade_counts[g] = grade_counts.get(g, 0) + 1
                total_dur     += summary["total_duration"]
                total_alerts  += summary["alert_count"]
                total_stretch += summary["stretches"]

            for h, sc in self.data_manager.get_hourly_scores(d_str).items():
                hourly_raw.setdefault(h, []).append(sc)

        hourly_avg = {h: sum(v) / len(v) for h, v in hourly_raw.items()}
        avg        = sum(all_scores) / len(all_scores) if all_scores else None
        good_cnt   = sum(1 for sc in all_scores if sc <= 2)  # RULA 1~2
        ratio      = good_cnt / len(all_scores) * 100 if all_scores else None

        return {
            "avg":          avg,
            "duration":     total_dur,
            "ratio":        ratio,
            "alerts":       total_alerts,
            "stretch":      total_stretch,
            "grade_counts": grade_counts,
            "hourly":       hourly_avg,
        }

    def _get_daily_series(self):
        """기간에 따른 (레이블, 평균점수|None) 리스트."""
        today     = date.today()
        day_names = ["월", "화", "수", "목", "금", "토", "일"]

        if self._period == "today":
            h_data = self.data_manager.get_hourly_scores(today.isoformat())
            return [(f"{h}시", v) for h, v in sorted(h_data.items())]

        dates  = self._get_date_range()
        result = []
        for d in dates:
            summary = self.data_manager.get_day_summary(d.isoformat())
            avg     = summary["avg_score"] if summary else None
            if self._period == "week":
                label = "오늘" if d == today else day_names[d.weekday()]
            else:
                label = str(d.day)
            result.append((label, avg))
        return result

    # ── 새로고침 ──────────────────────────────────────────────────────────────
    def refresh(self):
        self._data_cache   = self._aggregate()
        self._series_cache = self._get_daily_series()
        data               = self._data_cache

        avg = data["avg"]
        self._card_avg.config(
            text=f"RULA {avg:.1f}" if avg is not None else "--",
            fg=score_color(avg) if avg is not None else TEXT_HINT,
        )
        self._card_time.config(
            text=fmt_duration_ko(data["duration"]) if data["duration"] else "--",
            fg=TEXT_PRI,
        )
        ratio = data["ratio"]
        self._card_ratio.config(
            text=f"{ratio:.0f}%" if ratio is not None else "--",
            fg=CLR_GOOD if (ratio or 0) >= 60 else CLR_WARN,
        )
        self._card_alert.config(
            text=str(data["alerts"]),
            fg=CLR_DANGER if data["alerts"] > 5 else TEXT_PRI,
        )

        # 스트레칭
        goal  = self.app_settings.stretch_goal
        count = data["stretch"]
        self._stretch_count_lbl.config(
            text=f"{count} / {goal}회",
            fg=CLR_GOOD if count >= goal else TEXT_PRI,
        )
        self._stretch_hint_lbl.config(
            text="목표 달성!" if count >= goal else f"목표까지 {goal - count}회 남았습니다.",
            fg=CLR_GOOD if count >= goal else TEXT_HINT,
        )
        self.after(60, lambda: self._update_stretch_bar(count, goal))

        # 인사이트
        self._insight_lbl.config(text=self._generate_insight(data))

        # 차트 다시 그리기
        self._draw_bar_chart()
        self._draw_hourly()
        self._draw_grade_dist()

    def _update_stretch_bar(self, count, goal):
        bw = self._stretch_bar_bg.winfo_width()
        if bw > 1:
            ratio = min(1.0, count / max(goal, 1))
            self._stretch_bar.place(x=0, y=0, relheight=1,
                                    width=int(bw * ratio))
            self._stretch_bar.config(bg=CLR_GOOD if count >= goal else ACCENT)

    # ── 점수 추이 막대 차트 ───────────────────────────────────────────────────
    def _draw_bar_chart(self):
        c = self._bar_canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 10:
            return

        series  = self._series_cache
        pad_l, pad_r, pad_t, pad_b = 38, 16, 20, 30
        chart_w = w - pad_l - pad_r
        chart_h = h - pad_t - pad_b

        # y축 기준선 (RULA: 낮을수록 좋음)
        for rula_val, col in [(2, CLR_GOOD), (3, CLR_WARN), (4, CLR_DANGER)]:
            frac = (6 - rula_val) / 5
            y = pad_t + chart_h - int(chart_h * frac)
            c.create_line(pad_l, y, w - pad_r, y,
                          fill=col, dash=(4, 4), width=1)
            c.create_text(pad_l - 4, y, text=str(rula_val),
                          anchor="e", fill=TEXT_HINT, font=(FONT, 7))

        if not series:
            c.create_text(w // 2, h // 2, text="데이터 없음",
                          fill=TEXT_HINT, font=(FONT, 10))
            return

        n      = len(series)
        slot_w = chart_w / n
        bar_w  = max(4, min(32, slot_w * 0.55))

        for i, (label, avg) in enumerate(series):
            xc = pad_l + (i + 0.5) * slot_w
            if avg is not None:
                frac = (6 - max(1.0, min(5.0, avg))) / 5
                bh = int(chart_h * frac)
                x0, x1 = xc - bar_w / 2, xc + bar_w / 2
                y1 = pad_t + chart_h
                col = score_color(avg)
                c.create_rectangle(x0, y1 - bh, x1, y1, fill=col, outline="")
                if bh > 14:
                    c.create_text(xc, y1 - bh + 8, text=f"{avg:.1f}",
                                  fill="#FFFFFF", font=(FONT, 7, "bold"))
            else:
                c.create_text(xc, pad_t + chart_h // 2, text="-",
                              fill=TEXT_HINT, font=(FONT, 9))

            c.create_text(xc, pad_t + chart_h + 10, text=label,
                          fill=TEXT_SEC, font=(FONT, 8))

    # ── 시간대별 패턴 ─────────────────────────────────────────────────────────
    def _draw_hourly(self):
        c = self._hourly_canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 10:
            return

        hourly = self._data_cache.get("hourly", {})
        if not hourly:
            c.create_text(w // 2, h // 2, text="데이터 없음",
                          fill=TEXT_HINT, font=(FONT, 10))
            return

        pad_l, pad_r, pad_t, pad_b = 6, 6, 20, 22
        chart_h = h - pad_t - pad_b
        hours   = sorted(hourly.keys())
        min_h   = min(min(hours), 6)
        max_h   = max(max(hours), 20)
        span    = max_h - min_h + 1
        slot_w  = (w - pad_l - pad_r) / span
        bar_w   = max(3, slot_w * 0.72)

        worst_h = max(hourly, key=hourly.get)  # RULA: 높을수록 나쁨
        c.create_text(w // 2, pad_t - 4,
                      text=f"가장 나쁜 시간대: {worst_h}시 (RULA {hourly[worst_h]:.1f}점)",
                      fill=CLR_DANGER, font=(FONT, 8), anchor="s")

        for hr in range(min_h, max_h + 1):
            xc  = pad_l + (hr - min_h + 0.5) * slot_w
            avg = hourly.get(hr)
            if avg is not None:
                frac = (6 - max(1.0, min(5.0, avg))) / 5
                bh = int(chart_h * frac)
                x0, x1 = xc - bar_w / 2, xc + bar_w / 2
                y1 = pad_t + chart_h
                c.create_rectangle(x0, y1 - bh, x1, y1,
                                   fill=score_color(avg), outline="")
            if hr % 3 == 0:
                c.create_text(xc, h - 8, text=f"{hr}",
                              fill=TEXT_HINT, font=(FONT, 7))

    # ── 등급 분포 ─────────────────────────────────────────────────────────────
    def _draw_grade_dist(self):
        c = self._grade_canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 10:
            return

        gc    = self._data_cache.get("grade_counts", {})
        total = sum(gc.values())
        if total == 0:
            c.create_text(w // 2, h // 2, text="데이터 없음",
                          fill=TEXT_HINT, font=(FONT, 10))
            return

        pad_x  = 16
        bar_y  = 28
        bar_h  = 28
        bar_w  = w - pad_x * 2
        GRADE_ORDER  = ["완벽", "허용", "주의", "경고", "위험"]
        GRADE_COLORS = {
            "완벽": CLR_GOOD, "허용": CLR_BLUE,
            "주의": CLR_WARN, "경고": CLR_DANGER, "위험": CLR_DANGER,
        }

        # 분할 바
        x = pad_x
        for grade in GRADE_ORDER:
            count  = gc.get(grade, 0)
            ratio  = count / total
            seg_w  = int(bar_w * ratio)
            if seg_w > 0:
                c.create_rectangle(x, bar_y, x + seg_w, bar_y + bar_h,
                                   fill=GRADE_COLORS[grade], outline="")
                if seg_w > 28:
                    c.create_text(x + seg_w // 2, bar_y + bar_h // 2,
                                  text=f"{ratio * 100:.0f}%",
                                  fill="#FFFFFF", font=(FONT, 8, "bold"))
            x += seg_w

        # 범례
        leg_x = pad_x
        leg_y = bar_y + bar_h + 14
        col_w = (w - pad_x * 2) // 5
        for grade in GRADE_ORDER:
            count = gc.get(grade, 0)
            pct   = count / total * 100
            c.create_rectangle(leg_x, leg_y, leg_x + 10, leg_y + 10,
                               fill=GRADE_COLORS[grade], outline="")
            c.create_text(leg_x + 13, leg_y + 5,
                          text=f"{grade} {pct:.0f}%",
                          anchor="w", fill=TEXT_SEC, font=(FONT, 8))
            leg_x += col_w

    # ── 인사이트 생성 ─────────────────────────────────────────────────────────
    def _generate_insight(self, data):
        avg = data["avg"]
        if avg is None:
            return ("아직 데이터가 없습니다.\n"
                    "측정을 시작하면 인사이트가 자동으로 생성됩니다.")

        lines = []

        # RULA 점수 (낮을수록 좋음)
        if avg <= 1.5:
            lines.append(f"평균 RULA {avg:.1f}점으로 매우 좋은 자세를 유지하고 있습니다.")
        elif avg <= 2.5:
            lines.append(f"평균 RULA {avg:.1f}점입니다. 허용 가능한 자세입니다.")
        elif avg <= 3.5:
            lines.append(
                f"평균 RULA {avg:.1f}점으로 자세 교정이 필요합니다. "
                "등받이를 활용하고 모니터 높이를 조정해보세요."
            )
        else:
            lines.append(
                f"평균 RULA {avg:.1f}점으로 심각한 자세 불량입니다. 즉시 교정이 필요합니다."
            )

        # 바른 자세 비율
        ratio = data["ratio"]
        if ratio is not None:
            if ratio >= 80:
                lines.append(f"바른 자세 비율 {ratio:.0f}%로 매우 우수합니다.")
            elif ratio >= 50:
                lines.append(
                    f"바른 자세 비율 {ratio:.0f}% — "
                    "절반 이상의 시간 동안 좋은 자세를 유지했습니다."
                )
            else:
                lines.append(
                    f"바른 자세 비율이 {ratio:.0f}%로 낮습니다. "
                    "1시간마다 스트레칭을 추가해보세요."
                )

        # 최악 시간대
        hourly = data["hourly"]
        if hourly:
            worst_h = min(hourly, key=hourly.get)
            lines.append(
                f"{worst_h}시 전후로 자세가 가장 나빠집니다. "
                "해당 시간대에 의식적으로 자세를 점검해보세요."
            )

        # 경고 횟수
        if data["alerts"] > 10:
            lines.append(
                f"경고가 {data['alerts']}회 발생했습니다. "
                "알림 간격을 줄이거나 자세 교정 운동을 늘려보세요."
            )

        # 스트레칭 목표
        goal = self.app_settings.stretch_goal
        if data["stretch"] >= goal:
            lines.append(f"스트레칭 목표({goal}회)를 달성했습니다.")
        elif data["stretch"] > 0:
            lines.append(
                f"스트레칭을 {data['stretch']}회 했습니다. "
                f"목표({goal}회)까지 {goal - data['stretch']}회 남았습니다."
            )

        return "\n".join(lines)
