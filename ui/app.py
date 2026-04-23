"""MainApp — root window with sidebar navigation and page switching."""
import tkinter as tk
import threading
from datetime import datetime

from config import (
    FONT, BG_APP, BG_SIDEBAR, BG_ACTIVE, ACCENT, ACCENT_DRK,
    TEXT_PRI, TEXT_SEC, TEXT_HINT, CLR_GOOD, CLR_WARN, CLR_BORDER,
)
from ui.dashboard      import DashboardPage
from ui.monitor        import MonitorPage
from ui.history        import HistoryPage
from ui.report         import ReportPage
from ui.settings       import SettingsPage
from ui.camera_window  import CameraMonitorWindow


NAV_ITEMS = [
    ("메인", None),
    ("대시보드",      "dashboard"),
    ("실시간 모니터링", "monitor"),
    ("리포트",        "report"),
    ("기록", None),
    ("히스토리",      "history"),
    ("알림 기록",     "alerts"),
    ("설정", None),
    ("환경 설정",     "settings"),
]


class MainApp:
    def __init__(self, root, data_manager, app_settings):
        self.root            = root
        self.data_manager    = data_manager
        self.app_settings    = app_settings
        self.sensitivity_var = tk.StringVar(value=app_settings.sensitivity)
        self.cam_window      = None
        self._current_page   = None
        self._nav_btns       = {}
        self._pages          = {}

        # sensitivity 변경 시 자동 저장
        self.sensitivity_var.trace_add(
            "write",
            lambda *_: app_settings.set("sensitivity", self.sensitivity_var.get())
        )

        self._preloaded_analyzer = None
        threading.Thread(target=self._preload_analyzer, daemon=True).start()

        self._build()
        self._show_page("dashboard")
        self._refresh_loop()

    def _preload_analyzer(self):
        from analyzer import PostureAnalyzer
        self._preloaded_analyzer = PostureAnalyzer(
            sensitivity=self.sensitivity_var.get()
        )

    # ── layout ────────────────────────────────────────────────────────────────
    def _build(self):
        self.root.configure(bg=BG_SIDEBAR)

        # sidebar (fixed width)
        self.sidebar = tk.Frame(self.root, bg=BG_SIDEBAR, width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # vertical divider
        tk.Frame(self.root, bg=CLR_BORDER, width=1).pack(side="left", fill="y")

        # content area
        self.content = tk.Frame(self.root, bg=BG_APP)
        self.content.pack(side="left", fill="both", expand=True)

        self._build_sidebar()
        self._build_pages()

    def _build_sidebar(self):
        sb = self.sidebar

        # logo area
        logo_frame = tk.Frame(sb, bg=BG_SIDEBAR, pady=20)
        logo_frame.pack(fill="x")

        logo_icon = tk.Label(logo_frame, text="  P", bg=ACCENT, fg="#FFFFFF",
                              font=(FONT, 14, "bold"), width=3, height=1)
        logo_icon.pack(side="left", padx=(16, 8))
        tk.Label(logo_frame, text="바른자세", bg=BG_SIDEBAR, fg=TEXT_PRI,
                 font=(FONT, 14, "bold")).pack(side="left")

        tk.Frame(sb, bg=CLR_BORDER, height=1).pack(fill="x", padx=16, pady=(0, 8))

        # nav items
        nav_scroll = tk.Frame(sb, bg=BG_SIDEBAR)
        nav_scroll.pack(fill="both", expand=True, padx=0)

        for label, page_key in NAV_ITEMS:
            if page_key is None:
                # section header
                tk.Label(nav_scroll, text=label, bg=BG_SIDEBAR, fg=TEXT_HINT,
                         font=(FONT, 8, "bold"), anchor="w",
                         padx=18).pack(fill="x", pady=(12, 2))
            else:
                btn = self._make_nav_btn(nav_scroll, label, page_key)
                self._nav_btns[page_key] = btn

        # status indicator
        self._status_frame = tk.Frame(sb, bg=BG_SIDEBAR)
        self._status_frame.pack(fill="x", padx=16, pady=8)
        self._status_dot   = tk.Label(self._status_frame, text="●", bg=BG_SIDEBAR,
                                       fg=TEXT_HINT, font=(FONT, 10))
        self._status_dot.pack(side="left")
        self._status_lbl   = tk.Label(self._status_frame, text="오프라인",
                                       bg=BG_SIDEBAR, fg=TEXT_SEC, font=(FONT, 9))
        self._status_lbl.pack(side="left", padx=(4, 0))

        tk.Frame(sb, bg=CLR_BORDER, height=1).pack(fill="x", padx=16, pady=(4, 8))

        # user profile card
        profile = tk.Frame(sb, bg=BG_SIDEBAR, pady=12)
        profile.pack(fill="x", side="bottom")
        tk.Frame(sb, bg=CLR_BORDER, height=1).pack(fill="x", padx=16, side="bottom")

        avatar = tk.Label(profile, text="  나  ", bg=ACCENT, fg="#FFFFFF",
                           font=(FONT, 11, "bold"), padx=4, pady=4)
        avatar.pack(side="left", padx=(16, 10))
        info = tk.Frame(profile, bg=BG_SIDEBAR)
        info.pack(side="left")
        tk.Label(info, text="사용자", bg=BG_SIDEBAR, fg=TEXT_PRI,
                 font=(FONT, 10, "bold")).pack(anchor="w")
        tk.Label(info, text="무료 플랜", bg=BG_SIDEBAR, fg=TEXT_HINT,
                 font=(FONT, 8)).pack(anchor="w")

    def _make_nav_btn(self, parent, label, page_key):
        btn = tk.Frame(parent, bg=BG_SIDEBAR, cursor="hand2", pady=0)
        btn.pack(fill="x")

        lbl = tk.Label(btn, text=f"  {label}", bg=BG_SIDEBAR, fg=TEXT_SEC,
                        font=(FONT, 10), anchor="w", padx=10, pady=10)
        lbl.pack(fill="x")

        def on_enter(e):
            if self._current_page != page_key:
                btn.config(bg="#F7F8FA")
                lbl.config(bg="#F7F8FA")

        def on_leave(e):
            if self._current_page != page_key:
                btn.config(bg=BG_SIDEBAR)
                lbl.config(bg=BG_SIDEBAR)

        def on_click(e=None):
            self._show_page(page_key)

        for w in (btn, lbl):
            w.bind("<Enter>",    on_enter)
            w.bind("<Leave>",    on_leave)
            w.bind("<Button-1>", on_click)

        btn._lbl = lbl
        return btn

    def _build_pages(self):
        def make(PageClass, *args, **kwargs):
            page = PageClass(self.content, *args, **kwargs)
            page.place(relx=0, rely=0, relwidth=1, relheight=1)
            return page

        self._pages["dashboard"] = make(
            DashboardPage,
            self.data_manager,
            self.app_settings,
            on_start_monitoring=self._open_camera,
            on_stop_monitoring=self._stop_measurement,
        )
        self._pages["monitor"] = make(
            MonitorPage,
            self.data_manager,
            self.sensitivity_var,
            on_open_camera=self._open_camera,
            on_stop_camera=self._stop_measurement,
        )
        self._pages["history"] = make(
            HistoryPage,
            self.data_manager,
        )
        self._pages["report"] = make(
            ReportPage,
            self.data_manager,
            self.app_settings,
        )
        self._pages["settings"] = make(
            SettingsPage,
            self.data_manager,
            self.sensitivity_var,
            self.app_settings,
        )
        # stubs
        for key, title in [("alerts", "알림 기록")]:
            page = tk.Frame(self.content, bg=BG_APP)
            page.place(relx=0, rely=0, relwidth=1, relheight=1)
            tk.Label(page, text=title, bg=BG_APP, fg=TEXT_PRI,
                     font=(FONT, 20, "bold")).pack(expand=True)
            tk.Label(page, text="준비 중입니다.", bg=BG_APP, fg=TEXT_HINT,
                     font=(FONT, 12)).pack()
            self._pages[key] = page

        # hide all
        for page in self._pages.values():
            page.place_forget()

    # ── navigation ────────────────────────────────────────────────────────────
    def _show_page(self, page_key):
        if page_key not in self._pages:
            return

        # hide current
        if self._current_page and self._current_page in self._pages:
            self._pages[self._current_page].place_forget()

        # deactivate old nav btn
        if self._current_page in self._nav_btns:
            old_btn = self._nav_btns[self._current_page]
            old_btn.config(bg=BG_SIDEBAR)
            old_btn._lbl.config(bg=BG_SIDEBAR, fg=TEXT_SEC,
                                 font=(FONT, 10))

        self._current_page = page_key

        # activate new nav btn
        if page_key in self._nav_btns:
            btn = self._nav_btns[page_key]
            btn.config(bg=BG_ACTIVE)
            btn._lbl.config(bg=BG_ACTIVE, fg=ACCENT, font=(FONT, 10, "bold"))

        self._pages[page_key].place(relx=0, rely=0, relwidth=1, relheight=1)

        # 리포트 페이지 진입 시 즉시 갱신
        if page_key == "report":
            self._pages["report"].refresh()

    # ── camera / monitoring ───────────────────────────────────────────────────
    def _open_camera(self):
        if self.cam_window and self.cam_window.winfo_exists():
            self.cam_window.deiconify()
            self.cam_window.lift()
            return
        self._set_status("캘리브레이션 중", CLR_WARN)
        self._pages["dashboard"].set_monitoring_active(True)
        self._pages["monitor"].set_active(True, calibrating=True)

        preloaded = self._preloaded_analyzer
        self._preloaded_analyzer = None
        self.cam_window = CameraMonitorWindow(
            self.root,
            self.data_manager,
            self.sensitivity_var,
            self.app_settings,
            on_close_cb=self._on_cam_close,
            preloaded_analyzer=preloaded,
        )

    def _stop_measurement(self):
        if self.cam_window and self.cam_window.winfo_exists():
            self.cam_window.stop()

    def _on_cam_close(self, minimized=False):
        if minimized:
            self._set_status("백그라운드 측정 중", CLR_GOOD)
            self._pages["dashboard"].set_monitoring_active(True)
            self._pages["monitor"].set_active(True, calibrating=False)
            self._pages["dashboard"].refresh()
            return
        # fully stopped
        self.cam_window = None
        self._set_status("오프라인", TEXT_HINT)
        self._pages["dashboard"].set_monitoring_active(False)
        self._pages["monitor"].set_active(False)
        self._pages["dashboard"].refresh()
        if "history" in self._pages:
            self._pages["history"].refresh()

    def _set_status(self, text, color):
        self._status_dot.config(fg=color)
        self._status_lbl.config(text=text)

    # ── periodic refresh ──────────────────────────────────────────────────────
    def _refresh_loop(self):
        if self._current_page == "dashboard":
            self._pages["dashboard"].refresh()
        self.root.after(15000, self._refresh_loop)
