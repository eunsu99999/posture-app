"""SettingsPage — environment and app settings."""
import tkinter as tk

from config import (
    FONT, BG_APP, BG_CARD, BG_ACTIVE, ACCENT, TEXT_PRI, TEXT_SEC, TEXT_HINT,
    CLR_BORDER, CLR_GOOD, CLR_WARN, CLR_DANGER,
)


class SettingsPage(tk.Frame):
    def __init__(self, parent, data_manager, app_settings, **kwargs):
        super().__init__(parent, bg=BG_APP, **kwargs)
        self.data_manager = data_manager
        self.app_settings = app_settings
        self._stretch_var    = tk.IntVar(value=app_settings.stretch_goal)

        self._build_scroll_container()
        self._build(self._inner)

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
                          lambda e: self._canvas.itemconfig(self._win, width=e.width))
        self._canvas.bind("<Enter>", lambda e: self._canvas.bind_all(
            "<MouseWheel>",
            lambda ev: self._canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")))
        self._canvas.bind("<Leave>", lambda e: self._canvas.unbind_all("<MouseWheel>"))

    # ── 전체 레이아웃 ─────────────────────────────────────────────────────────
    def _build(self, root):
        hdr = tk.Frame(root, bg=BG_APP)
        hdr.pack(fill="x", padx=20, pady=(18, 8))
        tk.Label(hdr, text="환경 설정", bg=BG_APP, fg=TEXT_PRI,
                 font=(FONT, 18, "bold")).pack(anchor="w")
        tk.Label(hdr, text="앱 동작을 설정합니다.",
                 bg=BG_APP, fg=TEXT_SEC, font=(FONT, 10)).pack(anchor="w")
        tk.Frame(root, bg=CLR_BORDER, height=1).pack(fill="x", padx=20, pady=(4, 16))

        # ── 알림 간격 (호버 드롭다운) ─────────────────────────────────────────
        self._section(root, "알림 설정",
                      "자세 불량이 감지될 때 배너를 보낼 최소 간격입니다.")
        HoverDropdown(
            root,
            options=[
                (5,  "5초",  "(추천)"),
                (10, "10초"),
                (15, "15초"),
                (30, "30초"),
                (60, "1분"),
            ],
            selected=self.app_settings.alert_interval,
            on_change=lambda v: setattr(self.app_settings, "alert_interval", v),
        ).pack(anchor="w", padx=20, pady=(0, 6))

        tk.Frame(root, bg=CLR_BORDER, height=1).pack(fill="x", padx=20, pady=(10, 16))

        # ── 스트레칭 목표 ─────────────────────────────────────────────────────
        self._section(root, "스트레칭 목표",
                      "하루에 달성할 스트레칭 횟수 목표를 설정합니다.")
        stretch_card = tk.Frame(root, bg=BG_CARD,
                                 highlightbackground=CLR_BORDER, highlightthickness=1)
        stretch_card.pack(fill="x", padx=20, pady=(0, 6))

        sr = tk.Frame(stretch_card, bg=BG_CARD)
        sr.pack(fill="x", padx=16, pady=16)
        tk.Label(sr, text="일일 스트레칭 목표", bg=BG_CARD, fg=TEXT_PRI,
                 font=(FONT, 10)).pack(side="left")
        tk.Label(sr, text="(1 ~ 20회)", bg=BG_CARD, fg=TEXT_HINT,
                 font=(FONT, 8)).pack(side="left", padx=(8, 0))

        self._stepper(
            stretch_card,
            var=self._stretch_var,
            min_val=1, max_val=20, step=1,
            unit="회",
            on_change=lambda v: setattr(self.app_settings, "stretch_goal", v),
        )

        tk.Frame(root, bg=CLR_BORDER, height=1).pack(fill="x", padx=20, pady=(10, 16))

        # ── 정보 ──────────────────────────────────────────────────────────────
        self._section(root, "정보", "")
        about_card = tk.Frame(root, bg=BG_CARD,
                               highlightbackground=CLR_BORDER, highlightthickness=1)
        about_card.pack(fill="x", padx=20, pady=(0, 24))
        for label, val in [
            ("앱 이름", "바른자세  —  Posture Monitor Pro"),
            ("버전",    "2.1"),
            ("데이터",  r"C:\storage\med\posture_data.json"),
            ("설정",    r"C:\storage\med\app_settings.json"),
        ]:
            r = tk.Frame(about_card, bg=BG_CARD)
            r.pack(fill="x", padx=16, pady=6)
            tk.Label(r, text=label, bg=BG_CARD, fg=TEXT_SEC,
                     font=(FONT, 9), width=10, anchor="w").pack(side="left")
            tk.Label(r, text=val, bg=BG_CARD, fg=TEXT_PRI,
                     font=(FONT, 9)).pack(side="left")
        tk.Frame(about_card, bg=BG_CARD, height=6).pack()

    # ── 헬퍼 ──────────────────────────────────────────────────────────────────
    def _section(self, root, title, desc):
        tk.Label(root, text=title, bg=BG_APP, fg=TEXT_PRI,
                 font=(FONT, 13, "bold")).pack(anchor="w", padx=20, pady=(0, 4))
        if desc:
            tk.Label(root, text=desc, bg=BG_APP, fg=TEXT_SEC,
                     font=(FONT, 9)).pack(anchor="w", padx=20, pady=(0, 8))

    def _stepper(self, parent, var, min_val, max_val, step, unit, on_change):
        row = tk.Frame(parent, bg=BG_CARD)
        row.pack(anchor="w", padx=16, pady=(0, 16))

        def minus():
            v = var.get()
            if v - step >= min_val:
                var.set(v - step); on_change(var.get()); _upd()

        def plus():
            v = var.get()
            if v + step <= max_val:
                var.set(v + step); on_change(var.get()); _upd()

        def _upd():
            v = var.get()
            lbl.config(text=f"{v}{unit}")
            btn_m.config(fg=TEXT_HINT if v <= min_val else TEXT_PRI)
            btn_p.config(fg=TEXT_HINT if v >= max_val else TEXT_PRI)

        btn_m = tk.Button(row, text="  -  ", bg=BG_APP, fg=TEXT_PRI,
                           font=(FONT, 13, "bold"), bd=0, cursor="hand2",
                           highlightbackground=CLR_BORDER, highlightthickness=1,
                           padx=6, pady=4, command=minus)
        btn_m.pack(side="left")
        lbl = tk.Label(row, text=f"{var.get()}{unit}", bg=BG_CARD, fg=ACCENT,
                        font=(FONT, 14, "bold"), width=7)
        lbl.pack(side="left", padx=12)
        btn_p = tk.Button(row, text="  +  ", bg=BG_APP, fg=TEXT_PRI,
                           font=(FONT, 13, "bold"), bd=0, cursor="hand2",
                           highlightbackground=CLR_BORDER, highlightthickness=1,
                           padx=6, pady=4, command=plus)
        btn_p.pack(side="left")
        _upd()



# ══════════════════════════════════════════════════════════════════════════════
# HoverDropdown — 평소엔 선택값만, 호버 시 Toplevel 오버레이로 전체 옵션 표시
# (레이아웃 밀림 없음, 가로 확장 없음, 선택 항목 위치 고정)
# ══════════════════════════════════════════════════════════════════════════════
class HoverDropdown(tk.Frame):
    """
    options : [(value, label) | (value, label, badge), ...]
    selected: 초기 선택 value
    on_change: fn(value)
    """
    _ITEM_PAD_Y = 9
    _ITEM_PAD_X = 18
    _WIDTH      = 220

    def __init__(self, parent, options, selected, on_change, **kwargs):
        super().__init__(parent, bg=BG_APP, **kwargs)
        self._items     = options
        self._selected  = selected
        self._on_change = on_change
        self._popup     = None
        self._after_id  = None

        self._build_trigger()

    # ── 트리거 (항상 보이는 선택 행) ─────────────────────────────────────────
    def _build_trigger(self):
        self._trigger = tk.Frame(self, bg=BG_CARD,
                                  highlightbackground=CLR_BORDER,
                                  highlightthickness=1)
        self._trigger.pack(anchor="w")

        inner = tk.Frame(self._trigger, bg=BG_CARD,
                          pady=self._ITEM_PAD_Y, padx=self._ITEM_PAD_X)
        inner.pack(fill="x")

        self._trig_lbl = tk.Label(inner, text="", bg=BG_CARD, fg=ACCENT,
                                   font=(FONT, 10, "bold"), anchor="w")
        self._trig_lbl.pack(side="left")

        self._trig_badge = tk.Label(inner, text="", bg=BG_ACTIVE, fg=ACCENT,
                                     font=(FONT, 8, "bold"), padx=5, pady=1)

        self._trig_arrow = tk.Label(inner, text="v", bg=BG_CARD, fg=TEXT_HINT,
                                     font=(FONT, 8))
        self._trig_arrow.pack(side="right", padx=(0, 2))

        self._update_trigger()

        for w in (self._trigger, inner, self._trig_lbl, self._trig_arrow,
                  self._trig_badge):
            w.bind("<Enter>", lambda e: (self._cancel_collapse(), self._expand()))
            w.bind("<Leave>", lambda e: self._schedule_collapse())

    def _update_trigger(self):
        for opt in self._items:
            if opt[0] == self._selected:
                self._trig_lbl.config(text=opt[1])
                badge = opt[2] if len(opt) > 2 else ""
                if badge:
                    self._trig_badge.config(text=badge)
                    self._trig_badge.pack(side="left", padx=(8, 0))
                else:
                    self._trig_badge.pack_forget()
                break

    # ── 팝업 (Toplevel 오버레이) ──────────────────────────────────────────────
    def _expand(self):
        if self._popup is not None:
            return

        self._popup = tk.Toplevel(self)
        self._popup.overrideredirect(True)
        self._popup.config(bg=BG_CARD)

        container = tk.Frame(self._popup, bg=BG_CARD,
                              highlightbackground=CLR_BORDER,
                              highlightthickness=1)
        container.pack(fill="both", expand=True)

        self._popup_rows = {}
        for i, opt in enumerate(self._items):
            value   = opt[0]
            label   = opt[1]
            badge   = opt[2] if len(opt) > 2 else None
            is_last = (i == len(self._items) - 1)

            row = tk.Frame(container, bg=BG_CARD, cursor="hand2")
            row.pack(fill="x")

            inner = tk.Frame(row, bg=BG_CARD,
                              pady=self._ITEM_PAD_Y, padx=self._ITEM_PAD_X)
            inner.pack(fill="x")

            lbl = tk.Label(inner, text=label, bg=BG_CARD, fg=TEXT_PRI,
                            font=(FONT, 10), anchor="w")
            lbl.pack(side="left")

            check = tk.Label(inner, text="", bg=BG_CARD, fg=ACCENT,
                              font=(FONT, 10, "bold"))
            check.pack(side="right")

            if not is_last:
                tk.Frame(container, bg=CLR_BORDER, height=1).pack(fill="x")

            self._popup_rows[value] = (row, inner, lbl, check)

            def _click(e=None, v=value):
                self._select(v)
                self._collapse()

            for w in (row, inner, lbl, check):
                w.bind("<Button-1>", _click)
                w.bind("<Enter>",    lambda e: self._cancel_collapse())
                w.bind("<Leave>",    lambda e: self._schedule_collapse())

        self._popup.bind("<Enter>", lambda e: self._cancel_collapse())
        self._popup.bind("<Leave>", lambda e: self._schedule_collapse())

        self._apply_popup_selection()

        # 팝업 위치: 선택 항목이 트리거와 같은 y 좌표에 오도록 정렬
        self._popup.update_idletasks()
        popup_h  = self._popup.winfo_reqheight()
        sel_idx  = next((i for i, o in enumerate(self._items)
                         if o[0] == self._selected), 0)
        row_h    = popup_h / len(self._items)
        bx       = self._trigger.winfo_rootx()
        by       = self._trigger.winfo_rooty()
        bw       = self._trigger.winfo_width()
        py       = int(by - sel_idx * row_h)
        self._popup.geometry(f"{bw}x{popup_h}+{bx}+{py}")

    def _collapse(self):
        if self._popup:
            self._popup.destroy()
            self._popup = None

    def _schedule_collapse(self):
        self._cancel_collapse()
        self._after_id = self.after(200, self._collapse)

    def _cancel_collapse(self):
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None

    # ── 선택 처리 ─────────────────────────────────────────────────────────────
    def _select(self, value):
        self._selected = value
        self._update_trigger()
        if self._on_change:
            self._on_change(value)

    def _apply_popup_selection(self):
        for value, (row, inner, lbl, check) in self._popup_rows.items():
            is_sel = (value == self._selected)
            bg = BG_ACTIVE if is_sel else BG_CARD
            row.config(bg=bg)
            inner.config(bg=bg)
            lbl.config(bg=bg,
                        fg=ACCENT if is_sel else TEXT_PRI,
                        font=(FONT, 10, "bold") if is_sel else (FONT, 10))
            check.config(bg=bg, text="v" if is_sel else "")
