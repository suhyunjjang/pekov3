"""
애플리케이션 전역 설정값을 정의하는 모듈
"""

# 거래소 설정
DEFAULT_EXCHANGE_ID = 'binanceusdm'
DEFAULT_SYMBOL = 'BTC/USDT'
DEFAULT_TIMEFRAME = '1h'
DEFAULT_LIMIT = 500

# 차트 설정
CHART_DEFAULT_HEIGHT = 400
CHART_SPLITTER_RATIO = 0.75  # 메인 차트 : CCI 차트 = 3:1

# 기술적 지표 설정
BOLLINGER_WINDOW = 20
BOLLINGER_STD = 2.0
CCI_WINDOW = 20

# 초기 지표 상태
SHOW_BOLLINGER = True
SHOW_CCI = True

# 스타일 설정
ACTIVE_BUTTON_STYLE = """
    QPushButton {
        background-color: #40A040;
        color: white;
        font-weight: bold;
    }
"""

ACTIVE_BOLLINGER_BUTTON_STYLE = """
    QPushButton {
        background-color: #4080C0;
        color: white;
        font-weight: bold;
    }
"""

CONSOLE_STYLE = """
    QTextEdit {
        background-color: #2E2E2E; /* Dark gray background */
        color: #F0F0F0; /* Light gray text */
        font-family: Consolas, Courier New, monospace;
        font-size: 9pt;
        border: 1px solid #555555;
    }
""" 