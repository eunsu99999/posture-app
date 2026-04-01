"""MonitorPage — controls for real-time camera monitoring."""
import tkinter as tk

from config import (
    FONT, BG_APP, BG_CARD, BG_ACTIVE, ACCENT, ACCENT_DRK,
    TEXT_PRI, TEXT_SEC, TEXT_HINT, CLR_GOOD, CLR_WARN, CLR_DANGER, CLR_BORDER,
    SENSITIVITY_PRESETS,
)


class MonitorPage(tk.Frame):
    def __init__(self, parent, data_manager, sensitivity_var,
                 on_open_camera=None, on_stop_camera=None, **kwargs):
        super().__init__(parent, bg=BG_APP, **kwargs)
        self.data_manager    = data_manager
        self.sensitivity_var = sensitivity_var
        self.on_open_camera  = on_open_camera
        self.on_stop_camera  = on_stop_camera
        self._active         = False
        self._sens_cards     = {}
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=BG_APP)
        hdr.pack(fill="x", padx=20, pady=(18, 8))
        tk.Label(hdr, text="실시간 모니터링", bg=BG_APP, fg=TEXT_PRI,
                 font=(FONT, 18, "bold")).pack(anchor="w")
        tk.Label(hdr, text="카메라로 실시간 자세를 분석합니다. 캘리브레이션 후 백그라운드에서 자동 측정됩니다.",
                 bg=BG_APP, fg=TEXT_SEC, font=(FONT, 10)).pack(anchor="w")
        tk.Frame(self, bg=CLR_BORDER, height=1).pack(fill="x", padx=20, pady=(4, 14))

        # status card
        status_card = tk.Frame(self, bg=BG_CARD,
                                highlightbackground=CLR_BORDER, highlightthickness=1)
        status_card.pack(fill="x", padx=20, pady=(0, 14))
        status_inner = tk.Frame(status_card, bg=BG_CARD)
        status_inner.pack(fill="x", padx=16, pady=14)

        self._status_dot = tk.Label(status_inner, text="●", bg=BG_CARD,
                                     fg=TEXT_HINT, font=(FONT, 14))
        self._status_dot.pack(side="left")
        status_text = tk.Frame(status_inner, bg=BG_CARD)
        status_text.pack(side="left", padx=(10, 0))
        self._status_title = tk.Label(status_text, text="오프라인", bg=BG_CARD,
                                       fg=TEXT_PRI, font=(FONT, 13, "bold"))
        self._status_title.pack(anchor="w")
        self._status_desc = tk.Label(status_text,
                                      text="아래 버튼으로 모니터링을 시작하세요.",
                                      bg=BG_CARD, fg=TEXT_SEC, font=(FONT, 9))
        self._status_desc.pack(anchor="w")

        # sensitivity selector
        tk.Label(self, text="민감도 설정", bg=BG_APP, fg=TEXT_PRI,
                 font=(FONT, 13, "bold")).pack(anchor="w", padx=20, pady=(0, 8))
        tk.Label(self, text="거북목 감지(수직) 민감도와 옆 기울기(수평) 민감도를 조정합니다.",
                 bg=BG_APP, fg=TEXT_SEC, font=(FONT, 9)).pack(anchor="w", padx=20, pady=(0, 10))

        sens_row = tk.Frame(self, bg=BG_APP)
        sens_row.pack(fill="x", padx=20, pady=(0, 16))
        for key, preset in SENSITIVITY_PRESETS.items():
            self._make_sens_card(sens_row, key, preset)

        self._sens_desc = tk.Label(self, text="", bg=BG_APP, fg=TEXT_SEC,
                                    font=(FONT, 9), wraplength=600)
        self._sens_desc.pack(anchor="w", padx=20, pady=(0, 20))
        self._update_sens_desc()

        tk.Frame(self, bg=CLR_BORDER, height=1).pack(fill="x", padx=20, pady=(0, 16))

        # action buttons
        btn_row = tk.Frame(self, bg=BG_APP)
        btn_row.pack(fill="x", padx=20)

        self._start_btn = tk.Button(
            btn_row, text="카메라 모니터 열기", bg=ACCENT, fg="#FFFFFF",
            font=(FONT, 12, "bold"), bd=0, padx=24, pady=12, cursor="hand2",
            activebackground=ACCENT_DRK, activeforeground="#FFFFFF",
            command=self._on_start,
        )
        self._start_btn.pack(side="left", padx=(0, 10))

        self._stop_btn = tk.Button(
            btn_row, text="측정 중지", bg="#FFF5F5", fg=CLR_DANGER,
            font=(FONT, 11, "bold"), bd=0, padx=20, pady=12, cursor="hand2",
            activebackground="#FED7D7", activeforeground=CLR_DANGER,
            command=self._on_stop,
        )

        tk.Label(self, text="캘리브레이션: 처음 5초간 바른 자세로 앉아주세요. 이후 자동으로 백그라운드 측정이 시작됩니다.",
                 bg=BG_APP, fg=TEXT_HINT, font=(FONT, 9)).pack(
            anchor="w", padx=20, pady=(12, 0))

    def _make_sens_card(self, parent, key, preset):
        selected   = key == self.sensitivity_var.get()
        border_col = preset["color"] if selected else CLR_BORDER
        bg_col     = BG_ACTIVE if selected else BG_CARD

        card = tk.Frame(parent, bg=bg_col,
                        highlightbackground=border_col, highlightthickness=2,
                        cursor="hand2", padx=8, pady=12)
        card.pack(side="left", fill="x", expand=True, padx=(0, 10))

        tk.Label(card, text=preset["label"], bg=bg_col, fg=preset["color"],
                 font=(FONT, 13, "bold")).pack()
        tk.Label(card, text=preset["ko"], bg=bg_col, fg=TEXT_PRI,
                 font=(FONT, 10)).pack(pady=(2, 0))
        tk.Label(card, text=preset["desc"], bg=bg_col, fg=TEXT_SEC,
                 font=(FONT, 8), wraplength=140).pack(pady=(2, 0))

        def click(e=None, k=key):
            self.sensitivity_var.set(k)
            self._refresh_sens_cards()
            self._update_sens_desc()

        for w in card.winfo_children() + [card]:
            w.bind("<Button-1>", click)

        self._sens_cards[key] = card

    def _refresh_sens_cards(self):
        sel = self.sensitivity_var.get()
        for key, card in self._sens_cards.items():
            preset = SENSITIVITY_PRESETS[key]
            bc = preset["color"] if key == sel else CLR_BORDER
            bg = BG_ACTIVE if key == sel else BG_CARD
            card.config(highlightbackground=bc, bg=bg)
            for ch in card.winfo_children():
                ch.config(bg=bg)

    def _update_sens_desc(self):
        sel = self.sensitivity_var.get()
        descs = {
            "relaxed": "거북목 감지 기준이 완화됩니다. 옆 기울기는 거의 무시됩니다. 장시간 사용 시 권장.",
            "normal":  "거북목 감지가 강화되고 옆 기울기는 적당히 감지됩니다. 일반 업무에 권장.",
            "strict":  "거북목과 옆 기울기 모두 세밀하게 감지됩니다. 자세 교정 집중 훈련용.",
        }
        self._sens_desc.config(text=descs.get(sel, ""))

    def _on_start(self):
        if self.on_open_camera:
            self.on_open_camera()

    def _on_stop(self):
        if self.on_stop_camera:
            self.on_stop_camera()

    def set_active(self, active: bool, calibrating: bool = False):
        self._active = active
        if calibrating:
            self._status_dot.config(fg=CLR_WARN)
            self._status_title.config(text="캘리브레이션 중")
            self._status_desc.config(text="바른 자세로 5초간 앉아주세요.")
            self._start_btn.config(text="모니터 창 보기", bg="#2D7A5E")
            self._stop_btn.pack(side="left")
        elif active:
            self._status_dot.config(fg=CLR_GOOD)
            self._status_title.config(text="백그라운드 측정 중")
            self._status_desc.config(text="카메라 창을 열어 상세 수치를 확인할 수 있습니다.")
            self._start_btn.config(text="모니터 창 보기", bg="#2D7A5E")
            self._stop_btn.pack(side="left")
        else:
            self._status_dot.config(fg=TEXT_HINT)
            self._status_title.config(text="오프라인")
            self._status_desc.config(text="아래 버튼으로 모니터링을 시작하세요.")
            self._start_btn.config(text="카메라 모니터 열기", bg=ACCENT)
            self._stop_btn.pack_forget()
