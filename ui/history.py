"""HistoryPage — calendar + day detail panel."""
import tkinter as tk
from ui.alerts import AlertsPage
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
        self.selected_alerts = []
        self.alert_page = 0

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.scale = min(screen_w / 1920, screen_h / 1080, 1.0)
        
        self._build()

    def S(self, v):
        return max(1, int(v * self.scale))

    
    
    def _build(self):
    

        # 전체 컨테이너
        container = tk.Frame(self, bg=BG_APP)
        container.pack(fill="both", expand=True, padx=self.S(55), pady=self.S(35))

        # 제목
        tk.Label(
            container,
            text="기록",
            bg=BG_APP,
            fg=TEXT_PRI,
            font=(FONT, 20, "bold")
        ).pack(anchor="w")

        tk.Label(
            container,
            text="날짜를 선택하면 해당 날짜의 기록을 확인할 수 있습니다.",
            bg=BG_APP,
            fg=TEXT_SEC,
            font=(FONT, 9)
        ).pack(anchor="w", pady=(4, 18))

        # 상단 카드 영역
        top = tk.Frame(container, bg=BG_APP)
        top.pack(fill="both", expand=True)

        # 왼쪽 달력 카드
        cal_card = tk.Frame(
            top,
            bg=BG_CARD,
            highlightbackground=CLR_BORDER,
            highlightthickness=1,
        )
        cal_card.pack(side="left", fill="both", expand=True, padx=(0, 12))

        self.cal = CalendarWidget(
            cal_card,
            self.data_manager,
            on_date_click=self._on_date_click,
        )
        self.cal.pack(fill="both", expand=True, padx=self.S(12), pady=self.S(12))

        # 오른쪽 상세 카드
        detail_card = tk.Frame(
            top,
            bg=BG_CARD,
            highlightbackground=CLR_BORDER,
            highlightthickness=1,
            width=self.S(470)
        )
        detail_card.pack(side="left", fill="both", padx=(12,0))
        detail_card.pack_propagate(False)

        self._detail_panel = DayDetailPanel(detail_card)
        self._detail_panel.pack(fill="both", expand=True)


        # 알림 리스트 영역
        tk.Label(
            container,
            text="알림 기록",
            bg=BG_APP,
            fg=TEXT_PRI,
            font=(FONT, 16, "bold")
        ).pack(anchor="w", pady=(18, 6))
        alerts_wrap = tk.Frame(container, bg=BG_APP)
        alerts_wrap.pack(fill="x", pady=(0, 0))

        # self._alerts_page = AlertsPage(alerts_wrap, self.data_manager)
        # self._alerts_page.pack(fill="both", expand=True)
        self.alert_table = tk.Frame(
            alerts_wrap,
            bg=BG_CARD,
            highlightbackground=CLR_BORDER,
            highlightthickness=1
        )
        self.alert_table.pack(fill="x")

        header = tk.Frame(self.alert_table, bg=BG_CARD)
        header.pack(fill="x")

        cols = ["No", "시간", "자세 등급", "상태", "주요 문제", ""]
        widths = [8, 20, 20, 18, 55, 25]

        col_weights = [1, 2, 2, 2, 5, 2]

        for i, col in enumerate(cols):
            header.columnconfigure(i, weight=col_weights[i])

            tk.Label(
                header,
                text=col,
                bg=BG_CARD,
                fg=TEXT_PRI,
                font=(FONT, 11, "bold"),
                pady=8
            ).grid(row=0, column=i, sticky="nsew")

        self.alert_rows = tk.Frame(self.alert_table, bg=BG_CARD)
        self.alert_rows.pack(fill="x")

        self._render_alert_rows()

        pager = tk.Frame(alerts_wrap, bg=BG_APP)
        pager.pack(pady=(10, 0))

        tk.Button(
            pager,
            text="<",
            bg="#E2E8F0",
            fg=TEXT_PRI,
            bd=0,
            width=3,
            command=lambda: self._change_alert_page(-1)
        ).pack(side="left", padx=6)
                
        self.page_btn = tk.Button(
            pager,
            text="1",
            bg=BG_CARD,
            fg=ACCENT,
            bd=1,
            width=3
        )
        self.page_btn.pack(side="left", padx=6)

        tk.Button(
            pager,
            text=">",
            bg="#E2E8F0",
            fg=TEXT_PRI,
            bd=0,
            width=3,
            command=lambda: self._change_alert_page(1)
        ).pack(side="left", padx=6)

    def _on_date_click(self, date_str):
        summary = self.data_manager.get_day_summary(date_str)
        alerts = self.data_manager.get_day_alerts(date_str)

        self.selected_alerts = alerts
        self.alert_page = 0

        self.cal.set_selected_date(date_str)

        self._detail_panel.show(date_str, summary, alerts)
        self._render_alert_rows()

    def _change_alert_page(self, diff):
        max_page = max(0, (len(self.selected_alerts) - 1) // 3)

        self.alert_page = max(
            0,
            min(max_page, self.alert_page + diff)
        )

        self._render_alert_rows()

    def _get_main_problem(self, alert):
        problems = []

        checks = [
            ("목 기울어짐", alert.get("neck_flexion"), 30.0),
            ("거북목", alert.get("forward_dist"), 15.0),
            ("몸 기울어짐", alert.get("lateral_tilt"), 20.0),
            ("어깨 비대칭", alert.get("shoulder_tilt"), 12.0),
        ]

        for name, value, max_value in checks:
            if value is None:
                continue

            try:
                ratio = abs(float(value)) / max_value
            except (TypeError, ValueError):
                continue

            problems.append((ratio, name))

        if not problems:
            return alert.get("message", "-")

        problems.sort(reverse=True)
        return problems[0][1]

    def _render_alert_rows(self):
        for w in self.alert_rows.winfo_children():
            w.destroy()

        start = self.alert_page * 3
        alerts = self.selected_alerts[start:start + 3]

        for i in range(3):
            row = tk.Frame(self.alert_rows, bg=BG_CARD)
            row.pack(fill="x")

            row_no = start + i + 1

            if i < len(alerts):
                a = alerts[i]

                score = a.get("score", "-")
                if isinstance(score, (int, float)):
                    score = score_grade(score)[0]

                severity = a.get("severity", "-")
                if severity == "warn":
                    severity = "주의"
                elif severity == "danger":
                    severity = "부적정"
                elif severity == "info":
                    severity = "정보"

                values = [
                    str(row_no),
                    a.get("time", "-"),
                    score,
                    severity,
                     self._get_main_problem(a),
                    "상세 보기 >"
                ]
            else:
                values = ["", "", "", "", "", ""]

            col_weights = [1, 2, 2, 2, 5, 2]

            for idx, value in enumerate(values):
                row.columnconfigure(idx, weight=col_weights[idx])

                if idx == len(values) - 1 and value:
                    tk.Button(
                        row,
                        text=value,
                        bg=BG_CARD,
                        fg=ACCENT,
                        font=(FONT, self.S(10), "bold"),
                        bd=0,
                        cursor="hand2",
                        command=lambda alert=a: self._show_alert_detail(alert)
                    ).grid(row=0, column=idx, sticky="nsew", pady=self.S(8))
                else:
                    tk.Label(
                        row,
                        text=value,
                        bg=BG_CARD,
                        fg=TEXT_SEC,
                        font=(FONT, self.S(10)),
                        pady=self.S(8)
                    ).grid(row=0, column=idx, sticky="nsew")

        if hasattr(self, "page_btn"):
            self.page_btn.config(text=str(self.alert_page + 1))

    def _show_alert_detail(self, alert):
        popup = tk.Toplevel(self)
        popup.title("상세 보기")
        popup.geometry("600x420")
        popup.configure(bg=BG_CARD)

        tk.Label(
            popup,
            text="자세 상세 기록",
            bg=BG_CARD,
            fg=TEXT_PRI,
            font=(FONT, 16, "bold")
        ).pack(anchor="w", padx=20, pady=(20, 10))

        img_path = alert.get("img_path")

        try:
            from PIL import Image, ImageTk
            import os

            if img_path and os.path.exists(img_path):
                pil = Image.open(img_path)
                pil.thumbnail((420, 260))
                photo = ImageTk.PhotoImage(pil)

                img_lbl = tk.Label(popup, image=photo, bg=BG_CARD)
                img_lbl.image = photo
                img_lbl.pack(pady=10)
            else:
                tk.Label(
                    popup,
                    text="저장된 사진이 없습니다.",
                    bg=BG_CARD,
                    fg=TEXT_HINT,
                    font=(FONT, 11)
                ).pack(pady=40)

        except Exception:
            tk.Label(
                popup,
                text="사진을 불러올 수 없습니다.",
                bg=BG_CARD,
                fg=TEXT_HINT,
                font=(FONT, 11)
            ).pack(pady=40)

        tk.Label(
            popup,
            text=alert.get("message", "자세 분석 정보가 없습니다."),
            bg=BG_CARD,
            fg=TEXT_SEC,
            font=(FONT, 10),
            wraplength=520
        ).pack(padx=20, pady=10)

        tk.Button(
            popup,
            text="닫기",
            bg=ACCENT,
            fg="#FFFFFF",
            bd=0,
            padx=20,
            pady=8,
            command=popup.destroy
        ).pack(pady=10)

    def refresh(self):
        self.cal.refresh()

        if hasattr(self, "alert_rows"):
            self._render_alert_rows()
        


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

        avg = summary["avg_score"]
        col = score_color(avg)

        total_sec = summary["total_duration"]
        good_sec = summary["good_posture_sec"]
        alert_count = summary["alert_count"]

        ratio = int((good_sec / total_sec) * 100) if total_sec > 0 else 0

        stats = [
            ("평균 자세 등급", score_grade(avg)[0], "", col),
            ("바른 자세 비율", f"{ratio}", "%", CLR_GOOD if ratio >= 60 else CLR_WARN),
            ("경고 횟수", f"{alert_count}", "회",
             CLR_DANGER if alert_count > 0 else TEXT_SEC),
            ("총 착석 시간", fmt_duration_ko(total_sec), "", TEXT_PRI),
        ]

        grid = tk.Frame(self, bg=BG_CARD)
        grid.pack(fill="both", expand=True, padx=10, pady=10)

        for i, (title, value, unit, color) in enumerate(stats):
            r = i // 2
            c = i % 2

            card = tk.Frame(
                grid,
                bg=BG_APP,
                highlightbackground=CLR_BORDER,
                highlightthickness=1
            )
            card.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")

            grid.columnconfigure(c, weight=1)
            grid.rowconfigure(r, weight=1)

            tk.Label(
                card,
                text=title,
                bg=BG_APP,
                fg=TEXT_PRI,
                font=(FONT, 8, "bold")
            ).pack(anchor="nw", padx=10, pady=(10, 4))

            value_row = tk.Frame(card, bg=BG_APP)
            value_row.pack(expand=True, pady=(0, 10))

            tk.Label(
                value_row,
                text=value,
                bg=BG_APP,
                fg=color,
                font=(FONT, 18, "bold")
            ).pack(side="left")

            if unit:
                tk.Label(
                    value_row,
                    text=unit,
                    bg=BG_APP,
                    fg=TEXT_SEC,
                    font=(FONT, 9)
                ).pack(side="left", padx=(4, 0))