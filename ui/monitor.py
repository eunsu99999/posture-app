"""MonitorPage — controls for real-time camera monitoring."""
import tkinter as tk

from config import (
    FONT, BG_APP, BG_CARD, ACCENT, ACCENT_DRK,
    TEXT_PRI, TEXT_SEC, TEXT_HINT, CLR_GOOD, CLR_WARN, CLR_DANGER, CLR_BORDER,
)


class MonitorPage(tk.Frame):
    def __init__(self, parent, data_manager,
                 on_open_camera=None, on_stop_camera=None, **kwargs):
        super().__init__(parent, bg=BG_APP, **kwargs)
        self.data_manager    = data_manager
        self.on_open_camera  = on_open_camera
        self.on_stop_camera  = on_stop_camera
        self._active         = False
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=BG_APP)
        hdr.pack(fill="x", padx=20, pady=(18, 8))
        tk.Label(hdr, text="실시간 모니터링", bg=BG_APP, fg=TEXT_PRI,
                 font=(FONT, 18, "bold")).pack(anchor="w")
        tk.Label(hdr, text="카메라로 실시간 자세를 분석합니다. 기준 설정 후 백그라운드에서 자동 측정됩니다.",
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

        tk.Label(self, text="기준 설정: 처음 5초간 바른 자세로 앉아주세요. 이후 자동으로 백그라운드 측정이 시작됩니다.",
                 bg=BG_APP, fg=TEXT_HINT, font=(FONT, 9)).pack(
            anchor="w", padx=20, pady=(12, 0))

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
            self._status_title.config(text="기준 설정 중")
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
