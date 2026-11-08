"""AlertsPage — alert history with posture snapshots, sorted by severity."""
import os
import threading
import tkinter as tk

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

_IMG_SEMAPHORE = threading.Semaphore(3)   # 동시 이미지 로드 최대 3개

from config import (
    FONT, BG_APP, BG_CARD, BG_ACTIVE, ACCENT,
    TEXT_PRI, TEXT_SEC, TEXT_HINT,
    CLR_GOOD, CLR_WARN, CLR_DANGER, CLR_BLUE, CLR_BORDER,
    score_color, score_grade,
)

THUMB_W = 190
THUMB_H = 143

# (레이블, 단위, m→표시단위 배율, 바 최대값, 가중치 표시)
_AXES = [
    ("축1 목굴곡", "°",  1.0,   30.0, "x2"),
    ("축2 앞돌출", "cm",   1.0, 15.0, ""),
    ("축3 측방",   "°",  1.0,   20.0, ""),
    ("축4 어깨",   "°",  1.0,   12.0, ""),
]
_RAW_KEYS = ["neck_flexion", "forward_dist", "lateral_tilt", "shoulder_tilt"]
_WEIGHTS  = [2, 1, 1, 1]
_BAR_W    = 120


class AlertsPage(tk.Frame):
    def __init__(self, parent, data_manager, **kwargs):
        super().__init__(parent, bg=BG_APP, **kwargs)
        self.data_manager = data_manager
        self._sort_mode   = "time"    # "score" | "time"
        self._img_refs    = []
        self._build_ui()
        self.refresh()

    # ── UI 구조 ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        # 헤더
        hdr = tk.Frame(self, bg=BG_APP)
        hdr.pack(fill="x", padx=20, pady=(18, 0))

        left = tk.Frame(hdr, bg=BG_APP)
        left.pack(side="left")
        tk.Label(left, text="알림 기록", bg=BG_APP, fg=TEXT_PRI,
                 font=(FONT, 18, "bold")).pack(anchor="w")
        tk.Label(left, text="경고 발생 시점의 자세 스냅샷  —  기준 대비 편차 표시",
                 bg=BG_APP, fg=TEXT_SEC, font=(FONT, 10)).pack(anchor="w")

        # 정렬 버튼
        sort_f = tk.Frame(hdr, bg=BG_APP)
        sort_f.pack(side="right", anchor="n", pady=6)
        tk.Label(sort_f, text="정렬", bg=BG_APP, fg=TEXT_HINT,
                 font=(FONT, 8)).pack(side="left", padx=(0, 6))
        self._btn_score = self._mk_sort_btn(sort_f, "나쁜 자세 순", "score")
        self._btn_time  = self._mk_sort_btn(sort_f, "최근순",       "time")
        self._btn_time.pack(side="left", padx=(0, 4))
        self._btn_score.pack(side="left")
        self._refresh_sort_btns()

        tk.Frame(self, bg=CLR_BORDER, height=1).pack(fill="x", padx=20, pady=(10, 0))

        # 스크롤 영역
        self._canvas = tk.Canvas(self, bg=BG_APP, highlightthickness=0)
        vbar = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=BG_APP)
        self._win   = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>",
                         lambda e: self._canvas.configure(
                             scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
                          lambda e: self._canvas.itemconfig(self._win, width=e.width))
        self._canvas.bind("<Enter>",
                          lambda e: self._canvas.bind_all("<MouseWheel>", self._scroll))
        self._canvas.bind("<Leave>",
                          lambda e: self._canvas.unbind_all("<MouseWheel>"))

    def _scroll(self, e):
        self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def _mk_sort_btn(self, parent, label, mode):
        btn = tk.Label(parent, text=label, bg=BG_CARD, fg=TEXT_SEC,
                       font=(FONT, 9), padx=10, pady=4, cursor="hand2",
                       highlightbackground=CLR_BORDER, highlightthickness=1)
        btn.bind("<Button-1>", lambda e: self._set_sort(mode))
        return btn

    def _set_sort(self, mode):
        self._sort_mode = mode
        self._refresh_sort_btns()
        self.refresh()

    def _refresh_sort_btns(self):
        for btn, mode in [(self._btn_score, "score"), (self._btn_time, "time")]:
            active = self._sort_mode == mode
            btn.config(
                bg=BG_ACTIVE if active else BG_CARD,
                fg=ACCENT    if active else TEXT_SEC,
                font=(FONT, 9, "bold") if active else (FONT, 9),
                highlightbackground=ACCENT if active else CLR_BORDER,
            )

    # ── 새로고침 ──────────────────────────────────────────────────────────────
    def refresh(self):
        for w in self._inner.winfo_children():
            w.destroy()
        self._img_refs.clear()

        alerts = self.data_manager.get_all_alerts()

        if not alerts:
            tk.Label(self._inner, text="아직 알림 기록이 없습니다.",
                     bg=BG_APP, fg=TEXT_HINT, font=(FONT, 12)).pack(pady=60)
            return

        if self._sort_mode == "score":
            alerts.sort(key=lambda a: a.get("score") or 0, reverse=True)
        else:
            alerts.sort(
                key=lambda a: (a.get("date", ""), a.get("time", "")),
                reverse=True,
            )

        # 최대 100개만 표시 (위젯 생성 비용 제한)
        alerts = alerts[:100]

        for alert in alerts:
            self._build_card(self._inner, alert)

        tk.Frame(self._inner, bg=BG_APP, height=20).pack()

    # ── 카드 ──────────────────────────────────────────────────────────────────
    def _build_card(self, parent, alert):
        score = alert.get("score")
        col = score_color(score) if score is not None else TEXT_HINT

        row = tk.Frame(
            parent,
            bg=BG_CARD,
            highlightbackground=CLR_BORDER,
            highlightthickness=1
        )
        row.pack(fill="x", padx=20, pady=0)

        time_txt = alert.get("time", "--")
        score_txt = score_grade(score)[0] if score is not None else "--"
        state_txt = alert.get("grade", "주의")
        msg_txt = alert.get("message", "자세 불균형")
        duration_txt = alert.get("duration", "2분")

        values = [
            time_txt,
            score_txt,
            state_txt,
            msg_txt,
            duration_txt,
        ]

        widths = [12, 12, 12, 30, 12]

        for value, width in zip(values, widths):
            fg = TEXT_PRI
            if value == score_txt:
                fg = col
            if value == state_txt:
                fg = CLR_WARN
            if value == msg_txt:
                fg = CLR_DANGER

            tk.Label(
                row,
                text=value,
                bg=BG_CARD,
                fg=fg,
                font=(FONT, 9, "bold") if value in (score_txt, msg_txt) else (FONT, 9),
                width=width,
                anchor="center"
            ).pack(side="left", padx=2, pady=8)

        tk.Button(
            row,
            text="상세 보기>",
            bg=BG_CARD,
            fg=TEXT_SEC,
            font=(FONT, 8),
            bd=0,
            cursor="hand2",
            command=lambda a=alert: self._show_detail_popup(a)
        ).pack(side="right", padx=10)
        
    def _show_detail_popup(self, alert):
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

        if img_path and os.path.exists(img_path) and _PIL_OK:
            try:
                pil = Image.open(img_path)
                pil.thumbnail((420, 260), Image.LANCZOS)
                photo = ImageTk.PhotoImage(pil)
                img_lbl = tk.Label(popup, image=photo, bg=BG_CARD)
                img_lbl.image = photo
                img_lbl.pack(pady=10)
            except Exception:
                tk.Label(popup, text="사진을 불러올 수 없습니다.", bg=BG_CARD, fg=TEXT_HINT).pack(pady=40)
        else:
            tk.Label(popup, text="사진 없음", bg=BG_CARD, fg=TEXT_HINT).pack(pady=40)

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