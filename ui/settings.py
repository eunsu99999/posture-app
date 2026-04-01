"""SettingsPage — environment and app settings."""
import tkinter as tk

from config import (
    FONT, BG_APP, BG_CARD, BG_ACTIVE, ACCENT, TEXT_PRI, TEXT_SEC, TEXT_HINT,
    CLR_BORDER, CLR_GOOD, CLR_WARN,
    SENSITIVITY_PRESETS, STRETCH_GOAL,
)


class SettingsPage(tk.Frame):
    def __init__(self, parent, data_manager, sensitivity_var, **kwargs):
        super().__init__(parent, bg=BG_APP, **kwargs)
        self.data_manager    = data_manager
        self.sensitivity_var = sensitivity_var
        self._sens_cards     = {}
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=BG_APP)
        hdr.pack(fill="x", padx=20, pady=(18, 8))
        tk.Label(hdr, text="환경 설정", bg=BG_APP, fg=TEXT_PRI,
                 font=(FONT, 18, "bold")).pack(anchor="w")
        tk.Label(hdr, text="앱 동작과 자세 감지 민감도를 설정합니다.",
                 bg=BG_APP, fg=TEXT_SEC, font=(FONT, 10)).pack(anchor="w")
        tk.Frame(self, bg=CLR_BORDER, height=1).pack(fill="x", padx=20, pady=(4, 16))

        # sensitivity section
        self._section("민감도 설정",
                      "거북목(수직) 및 옆 기울기(수평) 감지 민감도를 선택하세요.")
        sens_row = tk.Frame(self, bg=BG_APP)
        sens_row.pack(fill="x", padx=20, pady=(0, 8))
        for key, preset in SENSITIVITY_PRESETS.items():
            self._make_sens_card(sens_row, key, preset)
        self._sens_desc = tk.Label(self, text="", bg=BG_APP, fg=TEXT_SEC,
                                    font=(FONT, 9), wraplength=700)
        self._sens_desc.pack(anchor="w", padx=20, pady=(0, 20))
        self._update_sens_desc()

        tk.Frame(self, bg=CLR_BORDER, height=1).pack(fill="x", padx=20, pady=(0, 16))

        # alert section
        self._section("알림 설정", "자세 경고 알림 간격을 설정합니다.")
        alert_card = tk.Frame(self, bg=BG_CARD,
                               highlightbackground=CLR_BORDER, highlightthickness=1)
        alert_card.pack(fill="x", padx=20, pady=(0, 20))
        row = tk.Frame(alert_card, bg=BG_CARD)
        row.pack(fill="x", padx=16, pady=14)
        tk.Label(row, text="경고 알림 간격", bg=BG_CARD, fg=TEXT_PRI,
                 font=(FONT, 10)).pack(side="left")
        tk.Label(row, text="30초 (고정)", bg=BG_CARD, fg=TEXT_SEC,
                 font=(FONT, 10)).pack(side="right")

        tk.Frame(self, bg=CLR_BORDER, height=1).pack(fill="x", padx=20, pady=(0, 16))

        # stretching goal section
        self._section("스트레칭 목표",
                       f"하루 스트레칭 목표 횟수: {STRETCH_GOAL}회")
        stretch_card = tk.Frame(self, bg=BG_CARD,
                                 highlightbackground=CLR_BORDER, highlightthickness=1)
        stretch_card.pack(fill="x", padx=20, pady=(0, 20))
        srow = tk.Frame(stretch_card, bg=BG_CARD)
        srow.pack(fill="x", padx=16, pady=14)
        tk.Label(srow, text="일일 스트레칭 목표", bg=BG_CARD, fg=TEXT_PRI,
                 font=(FONT, 10)).pack(side="left")
        tk.Label(srow, text=f"{STRETCH_GOAL}회", bg=BG_CARD, fg=CLR_GOOD,
                 font=(FONT, 10, "bold")).pack(side="right")

        tk.Frame(self, bg=CLR_BORDER, height=1).pack(fill="x", padx=20, pady=(0, 16))

        # about section
        self._section("정보", "")
        about_card = tk.Frame(self, bg=BG_CARD,
                               highlightbackground=CLR_BORDER, highlightthickness=1)
        about_card.pack(fill="x", padx=20)
        for label, val in [
            ("앱 이름",   "바른자세 — Posture Monitor Pro"),
            ("버전",      "2.0"),
            ("저장 경로", r"C:\storage\med\posture_data.json"),
        ]:
            r = tk.Frame(about_card, bg=BG_CARD)
            r.pack(fill="x", padx=16, pady=6)
            tk.Label(r, text=label, bg=BG_CARD, fg=TEXT_SEC,
                     font=(FONT, 9), width=12, anchor="w").pack(side="left")
            tk.Label(r, text=val, bg=BG_CARD, fg=TEXT_PRI,
                     font=(FONT, 9)).pack(side="left")
        tk.Frame(about_card, bg=BG_CARD, height=6).pack()

    def _section(self, title, desc):
        tk.Label(self, text=title, bg=BG_APP, fg=TEXT_PRI,
                 font=(FONT, 13, "bold")).pack(anchor="w", padx=20, pady=(0, 4))
        if desc:
            tk.Label(self, text=desc, bg=BG_APP, fg=TEXT_SEC,
                     font=(FONT, 9)).pack(anchor="w", padx=20, pady=(0, 8))

    def _make_sens_card(self, parent, key, preset):
        selected   = key == self.sensitivity_var.get()
        border_col = preset["color"] if selected else CLR_BORDER
        bg_col     = BG_ACTIVE if selected else BG_CARD

        card = tk.Frame(parent, bg=bg_col,
                        highlightbackground=border_col, highlightthickness=2,
                        cursor="hand2", padx=8, pady=12)
        card.pack(side="left", fill="x", expand=True, padx=(0, 10))

        tk.Label(card, text=preset["label"], bg=bg_col, fg=preset["color"],
                 font=(FONT, 12, "bold")).pack()
        tk.Label(card, text=preset["ko"], bg=bg_col, fg=TEXT_PRI,
                 font=(FONT, 10)).pack(pady=(2, 0))
        tk.Label(card, text=preset["desc"].split("—")[0].strip(),
                 bg=bg_col, fg=TEXT_SEC, font=(FONT, 8)).pack(pady=(2, 0))

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
            "relaxed": "거북목 감지 기준이 완화됩니다. 옆 기울기는 거의 무시됩니다.",
            "normal":  "거북목 감지가 강화되고 옆 기울기는 적당히 감지됩니다.",
            "strict":  "거북목과 옆 기울기 모두 세밀하게 감지됩니다.",
        }
        self._sens_desc.config(text=descs.get(sel, ""))
