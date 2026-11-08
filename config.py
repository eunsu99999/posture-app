import os

DATA_DIR        = os.path.join(os.path.expanduser("~"), ".posture_app")
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE       = os.path.join(DATA_DIR, "posture_data_v2.json")
SCORE_INTERVAL  = 5      # seconds between score saves
CAM_DISPLAY_W   = 500    # camera display width px
SESSION_GAP_SEC = 120    # gap (sec) before starting a new session
PSI_MIN         = 1      # 최소 등급 (적정)
PSI_MAX         = 3      # 최대 등급 (부적정)

# 목 굴곡도 선형 보정: 실제각도 = NECK_SLOPE × 앱측정값 + NECK_OFFSET
# 샘플: (5→8), (10→18), (15→28) — 3점 완전 일치
NECK_SLOPE  = 2.0
NECK_OFFSET = -2.0

# 앞돌출 선형 보정: 실제cm = FWDIST_SLOPE × forward_dist_ratio + FWDIST_OFFSET
# 샘플: (0.17→5cm), (0.25→10cm), (0.40→15cm) — 최소제곱 피팅
FWDIST_SLOPE  = 42.12
FWDIST_OFFSET = -1.51

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


def score_color(psi):
    """등급(1~3) → 색상. 낮을수록 좋음. 1=적정 2=주의 3=부적정."""
    if psi is None: return CLR_BORDER
    if psi <= 1: return CLR_GOOD
    if psi <= 2: return CLR_WARN
    return CLR_DANGER


def score_grade(psi):
    """등급(1~3) → (한국어 등급, 영문) 튜플. 1=적정 2=주의 3=부적정."""
    if psi is None: psi = PSI_MAX
    if psi <= 1: return "적정", "Good"
    if psi <= 2: return "주의", "Caution"
    return "부적정", "Poor"


def score_label_ko(psi):
    if psi is None: psi = PSI_MAX
    if psi <= 1: return "적정 자세"
    if psi <= 2: return "주의 필요"
    return "부적정 자세"


def score_desc_ko(psi):
    if psi is None: psi = PSI_MAX
    if psi <= 1: return "4개 축 모두\n적정 범위입니다"
    if psi <= 2: return "일부 축에서\n주의가 필요합니다"
    return "자세 교정이\n필요합니다"


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
