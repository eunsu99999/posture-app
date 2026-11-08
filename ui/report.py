"""ReportPage — 기간별 자세 분석 리포트."""
import tkinter as tk
from datetime import date, timedelta
import math

from config import (
    FONT, BG_APP, BG_CARD, BG_ACTIVE, ACCENT,
    TEXT_PRI, TEXT_SEC, TEXT_HINT,
    CLR_GOOD, CLR_WARN, CLR_DANGER, CLR_BLUE, CLR_BORDER,
    PSI_MIN, PSI_MAX,
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
        self._top_problem_cards = []

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
        tk.Label(hdr, text="자세 분석", bg=BG_APP, fg=TEXT_PRI,
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
        self._card_avg   = self._summary_card(cards_frame, "평균 자세 등급",      "--", last=False)
        self._card_ratio = self._summary_card(cards_frame, "바른 자세 비율", "--", last=False)
        self._card_alert = self._summary_card(cards_frame, "경고 횟수",      "--", last=True)

        # 주간/기간 점수 추이 차트
        bar_wrap = self._section_card(root, "등급 추이")
        self._bar_canvas = tk.Canvas(bar_wrap, bg=BG_CARD, height=190,
                                      highlightthickness=0)
        self._bar_canvas.pack(fill="x", padx=16, pady=(0, 12))
        self._bar_canvas.bind("<Configure>", lambda e: self._draw_bar_chart())

        # 자세 문제 TOP3
        top_wrap = self._section_card(root, "자세 상태")

        top_row = tk.Frame(top_wrap, bg=BG_CARD)
        top_row.pack(fill="x", padx=12, pady=(0, 12))

        self._top_problem_cards = []

        for _ in range(4):
            card = tk.Frame(
                top_row,
                bg=BG_CARD,
                highlightbackground=CLR_BORDER,
                highlightthickness=1
            )
            card.pack(side="left", fill="both", expand=True, padx=4)

            title_lbl = tk.Label(
                card,
                text="--",
                bg=BG_CARD,
                fg=TEXT_PRI,
                font=(FONT, 10, "bold")
            )
            title_lbl.pack(pady=(12, 2))

            status_lbl = tk.Label(
                card,
                text="--",
                bg=BG_CARD,
                fg=TEXT_HINT,
                font=(FONT, 12, "bold")
            )
            status_lbl.pack(pady=(0, 8))

            scale = tk.Frame(card, bg=BG_CARD, height=22)
            scale.pack(fill="x", padx=14, pady=(0, 0))
            scale.pack_propagate(False)

            tk.Label(scale, text="주의", bg=BG_CARD, fg=CLR_WARN,
                     font=(FONT, 7)).place(relx=0.40, rely=0)
            tk.Label(scale, text="위험", bg=BG_CARD, fg=CLR_DANGER,
                     font=(FONT, 7)).place(relx=0.70, rely=0)

            bar_bg = tk.Frame(card, bg="#E5E7EB", height=8)
            bar_bg.pack(fill="x", padx=14, pady=(0, 10))

            tk.Frame(bar_bg, bg=CLR_WARN, width=1).place(relx=0.40, relheight=1)
            tk.Frame(bar_bg, bg=CLR_DANGER, width=1).place(relx=0.70, relheight=1)

            bar = tk.Frame(bar_bg, bg=TEXT_HINT, height=8)
            bar.place(relwidth=0, relheight=1)

            percent_lbl = tk.Label(
                card,
                text="--",
                bg=BG_CARD,
                fg=TEXT_HINT,
                font=(FONT, 9, "bold")
            )
            percent_lbl.pack(pady=(0, 12))

            self._top_problem_cards.append((title_lbl, status_lbl, bar, percent_lbl))

        # 시간대별 + 등급 분포 (나란히)
        # mid = tk.Frame(root, bg=BG_APP)
        # mid.pack(fill="x", padx=20, pady=(0, 12))

        # hourly_wrap = tk.Frame(mid, bg=BG_CARD,
        #                         highlightbackground=CLR_BORDER, highlightthickness=1)
        # hourly_wrap.pack(side="left", fill="both", expand=True)
        # tk.Label(hourly_wrap, text="시간대별 패턴", bg=BG_CARD, fg=TEXT_SEC,
        #          font=(FONT, 9)).pack(anchor="nw", padx=12, pady=(10, 4))
        # self._hourly_canvas = tk.Canvas(hourly_wrap, bg=BG_CARD, height=130,
        #                                  highlightthickness=0)
        # self._hourly_canvas.pack(fill="x", padx=12, pady=(0, 12))
        # self._hourly_canvas.bind("<Configure>", lambda e: self._draw_hourly())

        # grade_wrap = tk.Frame(mid, bg=BG_CARD,
        #                        highlightbackground=CLR_BORDER, highlightthickness=1)
        # grade_wrap.pack(side="left", fill="both", expand=True, padx=(8, 0))
        # tk.Label(grade_wrap, text="등급 분포", bg=BG_CARD, fg=TEXT_SEC,
        #          font=(FONT, 9)).pack(anchor="nw", padx=12, pady=(10, 4))
        # self._grade_canvas = tk.Canvas(grade_wrap, bg=BG_CARD, height=130,
        #                                 highlightthickness=0)
        # self._grade_canvas.pack(fill="x", padx=12, pady=(0, 12))
        # self._grade_canvas.bind("<Configure>", lambda e: self._draw_grade_dist())

        # 인사이트
        # insight_wrap = self._section_card(root, "인사이트")
        # self._insight_lbl = tk.Label(insight_wrap, text="",
        #                               bg=BG_CARD, fg=TEXT_SEC,
        #                               font=(FONT, 10), wraplength=900,
        #                               justify="left", anchor="w")
        # self._insight_lbl.pack(fill="x", padx=16, pady=(0, 16))

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
    
    def _problem_color(self, percent):
        if percent >= 70:
            return CLR_DANGER
        elif percent >= 40:
            return CLR_WARN
        else:
            return CLR_GOOD
        
    def _problem_status(self, percent):
        if percent >= 70:
            return "위험", CLR_DANGER
        elif percent >= 40:
            return "주의", CLR_WARN
        else:
            return "낮음", CLR_GOOD

    def _get_top3_problems(self, dates):
        axis_info = [
            ("목 기울어짐", "neck_flexion", 30.0),
            ("거북목", "forward_dist", 15.0),
            ("몸 기울어짐", "lateral_tilt", 20.0),
            ("어깨 비대칭", "shoulder_tilt", 12.0),
        ]

        result = []

        for label, key, max_value in axis_info:
            values = []

            for d in dates:
                alerts = self.data_manager.get_day_alerts(d.isoformat())
                for alert in alerts:
                    value = alert.get(key)
                    if value is None:
                        continue
                    try:
                        v = abs(float(value))
                        if not math.isnan(v):
                            values.append(v)
                    except (TypeError, ValueError):
                        pass
            if values:
                avg_value = sum(values) / len(values)
                percent = min(100, int((avg_value / max_value) * 100))
            else:
                avg_value = 0
                percent = 0

            result.append({
                "label": label,
                "value": round(avg_value, 1),
                "percent": percent,
                "max": max_value
            })

        result.sort(key=lambda x: x["percent"], reverse=True)
        return result
    
    def _aggregate(self):
        dates  = self._get_date_range()
        all_scores, total_dur, total_alerts = [], 0, 0
        grade_counts = {"적정": 0, "주의": 0, "부적정": 0}
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
                total_dur    += summary["total_duration"]
                total_alerts += summary["alert_count"]

            for h, sc in self.data_manager.get_hourly_scores(d_str).items():
                hourly_raw.setdefault(h, []).append(sc)

        hourly_avg = {h: sum(v) / len(v) for h, v in hourly_raw.items()}
        avg        = sum(all_scores) / len(all_scores) if all_scores else None
        good_cnt   = sum(1 for sc in all_scores if sc == 1)  # 적정 등급
        ratio      = good_cnt / len(all_scores) * 100 if all_scores else None

        return {
            "avg":          avg,
            "duration":     total_dur,
            "ratio":        ratio,
            "alerts":       total_alerts,
            "grade_counts": grade_counts,
            "hourly":       hourly_avg,
            "top3_problems": self._get_top3_problems(dates),
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
            text=score_grade(avg)[0] if avg is not None else "--",
            fg=score_color(avg) if avg is not None else TEXT_HINT,
        )
        # self._card_time.config(
        #     text=fmt_duration_ko(data["duration"]) if data["duration"] else "--",
        #     fg=TEXT_PRI,
        # )
        ratio = data["ratio"]
        self._card_ratio.config(
            text=f"{ratio:.0f}%" if ratio is not None else "--",
            fg=CLR_GOOD if (ratio or 0) >= 60 else CLR_WARN,
        )
        self._card_alert.config(
            text=str(data["alerts"]),
            fg=CLR_DANGER if data["alerts"] > 5 else TEXT_PRI,
        )

        top3 = data.get("top3_problems", [])

        for i, (title_lbl, status_lbl, bar, percent_lbl) in enumerate(self._top_problem_cards):
            if i < len(top3):
                item = top3[i]
                percent = item["percent"]
                label = item["label"]
                value = item["value"]
                status, col = self._problem_status(percent)

                title_lbl.config(text=label)
                status_lbl.config(text=status, fg=col)
                percent_lbl.config(text=f"{value}", fg=col)

                bar.config(bg=col)
                bar.place(relwidth=percent / 100, relheight=1)
            else:
                title_lbl.config(text="--")
                status_lbl.config(text="--", fg=TEXT_HINT)
                percent_lbl.config(text="--", fg=TEXT_HINT)

                bar.config(bg=TEXT_HINT)
                bar.place(relwidth=0, relheight=1)

        # 인사이트
        # self._insight_lbl.config(text=self._generate_insight(data))

        # 차트 다시 그리기
        self._draw_bar_chart()
        # self._draw_hourly()
        # self._draw_grade_dist()

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

        # y축 기준선 (등급: 낮을수록 좋음 → 높은 위치 = 적정)
        for gval, glabel, col in [(2, "주의", CLR_WARN), (3, "부적정", CLR_DANGER)]:
            frac = (PSI_MAX - gval) / (PSI_MAX - PSI_MIN)
            y = pad_t + chart_h - int(chart_h * frac)
            c.create_line(pad_l, y, w - pad_r, y,
                          fill=col, dash=(4, 4), width=1)
            c.create_text(pad_l - 4, y, text=glabel,
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
                frac = (PSI_MAX - max(PSI_MIN, min(PSI_MAX, avg))) / (PSI_MAX - PSI_MIN)
                bh = int(chart_h * frac)
                x0, x1 = xc - bar_w / 2, xc + bar_w / 2
                y1 = pad_t + chart_h
                col = score_color(avg)
                c.create_rectangle(x0, y1 - bh, x1, y1, fill=col, outline="")
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

        worst_h = max(hourly, key=hourly.get)  # 등급: 높을수록 나쁨
        c.create_text(w // 2, pad_t - 4,
                      text=f"가장 나쁜 시간대: {worst_h}시",
                      fill=CLR_DANGER, font=(FONT, 8), anchor="s")

        for hr in range(min_h, max_h + 1):
            xc  = pad_l + (hr - min_h + 0.5) * slot_w
            avg = hourly.get(hr)
            if avg is not None:
                frac = (PSI_MAX - max(PSI_MIN, min(PSI_MAX, avg))) / (PSI_MAX - PSI_MIN)
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
        GRADE_ORDER  = ["적정", "주의", "부적정"]
        GRADE_COLORS = {
            "적정": CLR_GOOD, "주의": CLR_WARN, "부적정": CLR_DANGER,
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
        col_w = (w - pad_x * 2) // 3
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

        # 종합 등급 (낮을수록 좋음)
        if avg <= 1:
            lines.append("평균 등급 '적정'으로 바른 자세를 유지하고 있습니다.")
        elif avg <= 2:
            lines.append("평균 등급 '주의'입니다. 자세를 점검해보세요.")
        else:
            lines.append(
                "평균 등급 '부적정'으로 자세 교정이 필요합니다. "
                "등받이를 활용하고 모니터 높이를 조정해보세요."
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
                    "자세 교정에 더 신경써주세요."
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

        return "\n".join(lines)
