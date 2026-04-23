"""PostureWarningBanner — 자세 불량 시 화면에 고정 표시되는 경고 오버레이."""
import math
import tkinter as tk
import time

from config import FONT, CLR_DANGER, CLR_WARN, CLR_GOOD

GOOD_HOLD_SEC = 3   # 좋은 자세를 이 시간(초)만큼 유지해야 배너 사라짐


class PostureWarningBanner:
    """
    - grade C/D 진입 시 즉시 표시
    - grade A 를 GOOD_HOLD_SEC 초 연속 유지해야 배너 사라짐
    - 카운트다운 중 B/C/D 로 내려가면 즉시 3초 리셋
    """

    def __init__(self, root):
        self._root       = root
        self._win        = None
        self._msg_lbl    = None
        self._sub_lbl    = None
        self._outer      = None
        self._body       = None
        self._is_showing = False
        self._good_since = None   # 좋은 자세로 돌아온 시각
        self._create_window()

    # ── 창 생성 ───────────────────────────────────────────────────────────────
    def _create_window(self):
        self._win = tk.Toplevel(self._root)
        self._win.withdraw()
        self._win.overrideredirect(True)      # 타이틀바 없음
        self._win.attributes("-topmost", True) # 항상 최상단

        sw = self._win.winfo_screenwidth()
        self._win.geometry(f"370x100+{sw - 392}+28")

        self._outer = tk.Frame(self._win, bg=CLR_DANGER)
        self._outer.pack(fill="both", expand=True)

        # 상단 강조 바
        tk.Frame(self._outer, bg="#C53030", height=4).pack(fill="x")

        self._body = tk.Frame(self._outer, bg=CLR_DANGER, padx=16, pady=10)
        self._body.pack(fill="both", expand=True)

        self._msg_lbl = tk.Label(
            self._body, text="", bg=CLR_DANGER, fg="#FFFFFF",
            font=(FONT, 11, "bold"), wraplength=330, justify="left",
        )
        self._msg_lbl.pack(anchor="w")

        self._sub_lbl = tk.Label(
            self._body, text="", bg=CLR_DANGER, fg="#FFD0D0",
            font=(FONT, 9), justify="left",
        )
        self._sub_lbl.pack(anchor="w", pady=(4, 0))

    # ── 매 프레임 호출 ────────────────────────────────────────────────────────
    def update(self, grade, detected, calibrated):
        """
        grade     : "A"/"B"/"C"/"D" 또는 None
        detected  : 사람이 프레임 안에 있는지
        calibrated: 캘리브레이션 완료 여부
        """
        if not calibrated or not detected or grade is None:
            return  # 측정 불가 상태 — 배너 건드리지 않음

        is_bad = grade in ("주의", "경고", "위험")

        if is_bad:
            # 나쁜 자세 → 회복 카운터 리셋 후 즉시 표시
            self._good_since = None
            if grade == "위험":
                msg = "거북목이 감지되었습니다! 즉시 자세를 교정해주세요."
            elif grade == "경고":
                msg = "자세가 많이 나쁩니다. 즉시 교정해주세요."
            else:
                msg = "자세가 나빠지고 있습니다. 바르게 앉아주세요."
            self._show(grade, msg)
        else:
            # 완벽/허용 → 배너가 떠 있으면 카운트다운
            if self._is_showing:
                # 완벽/허용 모두 카운트다운 진행
                if self._good_since is None:
                    self._good_since = time.time()
                remaining = GOOD_HOLD_SEC - (time.time() - self._good_since)
                if remaining <= 0:
                    self._hide()
                else:
                    self._set_recovering(remaining)

    # ── 내부 상태 전환 ────────────────────────────────────────────────────────
    def _show(self, grade, message):
        if grade == "위험":
            bg      = CLR_DANGER
            top_bar = "#C53030"
            fg_sub  = "#FFD0D0"
        elif grade == "경고":
            bg      = CLR_WARN
            top_bar = "#C07820"
            fg_sub  = "#FFF3D0"
        else:  # 주의
            bg      = "#D97706"
            top_bar = "#B45309"
            fg_sub  = "#FEF3C7"

        self._outer.config(bg=bg)
        self._body.config(bg=bg)
        # 상단 바 색상
        for child in self._outer.winfo_children():
            if isinstance(child, tk.Frame) and child != self._body:
                child.config(bg=top_bar)
        self._msg_lbl.config(text=message, bg=bg)
        self._sub_lbl.config(
            text="자세를 바르게 교정해주세요.",
            bg=bg, fg=fg_sub,
        )
        if not self._is_showing:
            self._win.deiconify()
            self._win.lift()
            self._is_showing = True

    def _set_recovering(self, remaining):
        secs = math.ceil(remaining)
        self._sub_lbl.config(
            text=f"자세 개선 중...  {secs}초 후 사라집니다."
        )

    def _hide(self):
        self._win.withdraw()
        self._is_showing = False
        self._good_since = None

    # ── 외부 호출 ─────────────────────────────────────────────────────────────
    def hide_immediately(self):
        """재캘리브레이션 등 강제 숨김."""
        self._hide()

    def destroy(self):
        if self._win and self._win.winfo_exists():
            self._win.destroy()
        self._win = None
