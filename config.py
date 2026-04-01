import os

DATA_DIR        = r"C:\storage\med"
DATA_FILE       = os.path.join(DATA_DIR, "posture_data.json")
SCORE_INTERVAL  = 5      # seconds between score saves
CAM_DISPLAY_W   = 500    # camera display width px
SESSION_GAP_SEC = 120    # gap (sec) before starting a new session
STRETCH_GOAL    = 5      # daily stretching goal count

FONT = "Malgun Gothic"

# ── Light theme palette (matches mockup) ─────────────────────────────────────
BG_APP     = "#F7F8FA"
BG_SIDEBAR = "#FFFFFF"
BG_CARD    = "#FFFFFF"
BG_ACTIVE  = "#EEF9F5"
BG_HOVER   = "#F0FAF6"
ACCENT     = "#2ECC9A"
ACCENT_DRK = "#27AE86"
TEXT_PRI   = "#1A202C"
TEXT_SEC   = "#718096"
TEXT_HINT  = "#A0AEC0"
CLR_GOOD   = "#2ECC9A"
CLR_WARN   = "#F6AD55"
CLR_DANGER = "#FC8181"
CLR_BLUE   = "#63B3ED"
CLR_BORDER = "#E2E8F0"
CLR_RED    = "#E53E3E"

# ── Sensitivity presets ───────────────────────────────────────────────────────
# v_mult: neck/vertical sensitivity (higher = more sensitive to forward lean)
# l_mult: lateral sensitivity (lower = less sensitive to side tilt)
SENSITIVITY_PRESETS = {
    "relaxed": {
        "v_mult": 2.5, "l_mult": 1.0,
        "label": "Relaxed", "ko": "편안하게",
        "color": "#63B3ED", "desc": "느슨한 기준 — 오래 사용할 때 권장",
    },
    "normal": {
        "v_mult": 4.0, "l_mult": 1.5,
        "label": "Normal",  "ko": "균형잡힌",
        "color": "#2ECC9A", "desc": "권장 기본값 — 일반 업무 환경",
    },
    "strict": {
        "v_mult": 6.0, "l_mult": 2.5,
        "label": "Strict",  "ko": "엄격하게",
        "color": "#F6AD55", "desc": "세밀한 기준 — 자세 교정 집중 훈련용",
    },
}


def score_color(score):
    if score >= 80: return CLR_GOOD
    if score >= 60: return CLR_BLUE
    if score >= 40: return CLR_WARN
    return CLR_DANGER


def score_grade(score):
    if score >= 80: return "A", "Perfect!"
    if score >= 60: return "B", "Good"
    if score >= 40: return "C", "Warning"
    return "D", "Danger!"


def score_label_ko(score):
    if score >= 80: return "양호한 상태"
    if score >= 60: return "보통 상태"
    if score >= 40: return "주의 필요"
    return "자세 위험"


def score_desc_ko(score):
    if score >= 80: return "목 기울기와 허리 각도가\n전반적으로 안정적입니다"
    if score >= 60: return "약간의 자세 교정이\n필요합니다"
    if score >= 40: return "자세가 많이 흐트러졌습니다.\n바르게 앉아주세요"
    return "즉시 자세를 교정해주세요.\n거북목 위험 상태입니다"


def fmt_duration(seconds):
    mins = seconds // 60
    if mins >= 60:
        return f"{mins // 60}h {mins % 60}m"
    return f"{mins}m"


def fmt_duration_ko(seconds):
    mins = seconds // 60
    if mins >= 60:
        return f"{mins // 60}시간 {mins % 60}분"
    return f"{mins}분"
