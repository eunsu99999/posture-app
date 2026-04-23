import os

DATA_DIR        = os.path.join(os.path.expanduser("~"), ".posture_app")
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE       = os.path.join(DATA_DIR, "posture_data.json")
SCORE_INTERVAL  = 5      # seconds between score saves
CAM_DISPLAY_W   = 500    # camera display width px
SESSION_GAP_SEC = 120    # gap (sec) before starting a new session
STRETCH_GOAL    = 5      # daily stretching goal count
PSI_MIN         = 5      # 최소 PSI 점수 (완벽한 자세)
PSI_MAX         = 18     # 최대 PSI 점수 (최악의 자세)

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
# lateral_threshold: 기울기 +1점 기준 각도 (degrees)
SENSITIVITY_PRESETS = {
    "relaxed": {
        "lateral_threshold": 15,
        "label": "Relaxed", "ko": "편안하게",
        "color": "#63B3ED", "desc": "느슨한 기준 — 오래 사용할 때 권장",
    },
    "normal": {
        "lateral_threshold": 10,
        "label": "Normal",  "ko": "균형잡힌",
        "color": "#2ECC9A", "desc": "권장 기본값 — 일반 업무 환경",
    },
    "strict": {
        "lateral_threshold": 7,
        "label": "Strict",  "ko": "엄격하게",
        "color": "#F6AD55", "desc": "세밀한 기준 — 자세 교정 집중 훈련용",
    },
}


def score_color(psi):
    """PSI 점수(5~18) → 색상. 낮을수록 좋음."""
    if psi is None: return CLR_BORDER
    if psi <= 5:  return CLR_GOOD
    if psi <= 8:  return CLR_BLUE
    if psi <= 12: return CLR_WARN
    if psi <= 15: return CLR_DANGER
    return CLR_RED


def score_grade(psi):
    """PSI 점수(5~18) → (한국어 등급, 영문) 튜플."""
    if psi is None: psi = PSI_MAX
    if psi <= 5:  return "완벽", "Perfect!"
    if psi <= 8:  return "허용", "Good"
    if psi <= 12: return "주의", "Warning"
    if psi <= 15: return "경고", "Danger"
    return "위험", "Critical!"


def score_label_ko(psi):
    if psi is None: psi = PSI_MAX
    if psi <= 5:  return "완벽한 자세"
    if psi <= 8:  return "허용 가능"
    if psi <= 12: return "주의 필요"
    if psi <= 15: return "즉각 교정"
    return "위험 상태"


def score_desc_ko(psi):
    if psi is None: psi = PSI_MAX
    if psi <= 5:  return "모든 축에서\n완벽한 자세입니다"
    if psi <= 8:  return "약간의 자세 이탈이\n있으나 허용 범위입니다"
    if psi <= 12: return "자세 교정이 필요합니다.\n바르게 앉아주세요"
    if psi <= 15: return "즉각적인 자세 교정이\n필요합니다"
    return "즉시 자세를 교정하세요.\n심각한 자세 불량입니다"


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
