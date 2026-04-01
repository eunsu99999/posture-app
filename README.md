# Posture Monitor Pro

실시간 웹캠 자세 모니터링 앱. MediaPipe로 목/어깨 위치를 분석하여 점수를 산출하고, 나쁜 자세가 감지되면 알림을 보냅니다.

## 기능

- 실시간 자세 점수 측정 (0~100점)
- 캘리브레이션: 바른 자세 기준값 자동 설정
- 나쁜 자세 감지 시 데스크탑 알림
- 세션별 점수 기록 (JSON 저장)
- 월별 달력 히스토리 및 날짜별 상세 그래프

## 요구 사항

- Python 3.10
- 웹캠

## 설치

```bash
git clone https://github.com/<your-username>/posture-monitor.git
cd posture-monitor
pip install -r requirements.txt
```

### 필요 라이브러리

| 라이브러리 | 용도 |
|---|---|
| opencv-python | 웹캠 캡처 |
| mediapipe | 신체 랜드마크 감지 |
| numpy | 수치 계산 |
| Pillow | tkinter 이미지 변환 |
| matplotlib | 히스토리 그래프 |
| plyer | 데스크탑 알림 |

## 실행

```bash
py posture.py
```

> 첫 실행 시 MediaPipe 모델 로딩에 약 20초 소요됩니다. 창이 뜨고 "AI 모델 로딩 중..." 상태에서 기다리면 자동으로 캘리브레이션이 시작됩니다.

## 사용법

1. 앱 실행 후 웹캠 앞에 바르게 앉습니다.
2. **캘리브레이션** (5초): 현재 자세를 기준값으로 설정합니다.
3. 모니터링 시작: 점수가 실시간으로 표시됩니다.
4. **Recalibrate** 버튼: 기준 자세 재설정
5. **Calendar / History** 버튼: 날짜별 자세 기록 확인
6. **Quit** 버튼: 앱 종료

### 점수 기준

| 등급 | 점수 | 상태 |
|---|---|---|
| A | 80 이상 | Perfect |
| B | 60~79 | Good |
| C | 40~59 | Warning |
| D | 40 미만 | Danger |

## 데이터 저장 위치

`C:\storage\med\posture_data.json`
