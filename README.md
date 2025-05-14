# 바이낸스 실시간 차트 애플리케이션

이 애플리케이션은 바이낸스 (USDⓈ-M 선물) 실시간 데이터를 캔들스틱 차트로 표시하고 다양한 기술적 지표를 제공합니다. 데이터 수집에는 `ccxt`와 `ccxt.pro`를 사용하여 REST API 및 WebSocket을 이용하고, 그래픽 사용자 인터페이스(GUI)에는 `PyQt6`, 차트에는 `pyqtgraph`를 사용합니다.

## 주요 기능

* 바이낸스 USDⓈ-M 선물의 실시간 캔들스틱 차트 표시 (BTC/USDT, ETH/USDT, XRP/USDT, SOL/USDT 지원)
* 다양한 시간대 지원 (1분, 5분, 15분, 1시간, 4시간, 1일 등)
* 기술적 지표 지원:
  * 볼린저 밴드 (Bollinger Bands) - 활성화/비활성화 가능
  * CCI (Commodity Channel Index) - 활성화/비활성화 가능
* 차트 기능:
  * 자동 스케일링 옵션
  * 뷰 초기화 기능 (최근 150개 캔들로 확대)
  * 시작 시 자동으로 최근 150개 캔들만 표시
  * 마우스 움직임을 따라다니는 십자선 커서
  * 마우스 커서 아래 캔들의 OHLCV 및 CCI 데이터 표시
* 사용자 인터페이스:
  * 높이 조절 가능한 콘솔 창
  * 타임스탬프가 있는 로그 출력
  * 차트와 CCI 지표 간의 조절 가능한 분할 뷰
  * 좌측 차트 영역과 우측 메시지 영역의 분할 레이아웃
* 데이터 연결:
  * REST API를 사용한 초기 차트 데이터 로딩
  * WebSocket 연결을 통한 실시간 데이터 업데이트
  * WebSocket 초기화 실패 시 REST API 폴링으로 자동 전환

## 설치 방법

### 필수 요구사항
* Python 3.8 이상
* pip (Python 패키지 관리자)

### 의존성 설치

이 프로젝트는 다음 라이브러리를 사용합니다:
* PyQt6 - GUI 프레임워크
* pyqtgraph - 데이터 시각화 라이브러리
* ccxt - 암호화폐 거래소 API 통합 라이브러리
* pandas - 데이터 분석 및 처리 라이브러리
* numpy - 수치 계산 라이브러리
* asyncio - 비동기 프로그래밍 라이브러리 (Python 3.4 이상 버전에 기본 포함)

다음 명령어를 사용하여 모든 필요한 라이브러리를 한 번에 설치할 수 있습니다:

```bash
pip install PyQt6 pyqtgraph ccxt pandas numpy
```

ccxt.pro를 사용하려면 별도의 라이선스가 필요할 수 있습니다. 자세한 내용은 [ccxt 공식 문서](https://github.com/ccxt/ccxt)를 참조하세요.

## 실행 방법

1. 모든 의존성이 설치되었는지 확인합니다.
2. 터미널에서 프로젝트 디렉토리로 이동합니다.
3. 메인 애플리케이션 파일을 실행합니다:

```bash
python main.py
```

## 프로젝트 구조

모듈화된 구조로 코드가 재구성되었습니다:

* `main.py`: 메인 애플리케이션 진입점. PyQt 애플리케이션을 초기화하고 MainWindow를 생성합니다.

* `config/`: 전역 설정값을 관리하는 패키지
  * `settings.py`: 애플리케이션 전역 설정값 정의 (거래소, 차트, 지표 설정 등)

* `core/`: 데이터 처리 및 거래소 연결 관련 핵심 모듈
  * `data_worker.py`: WebSocket 데이터 수집을 위한 워커 클래스
  * `exchange.py`: 거래소 연결 및 데이터 요청 관리

* `plotting/`: 차트 및 시각화 관련 모듈
  * `custom_plot_items.py`: 캔들스틱 차트와 날짜 축을 위한 사용자 정의 플롯 아이템

* `ui/`: 사용자 인터페이스 관련 모듈
  * `app.py`: MainWindow 클래스 정의
  * `chart.py`: 차트 관련 기능을 제공하는 ChartMixin 클래스
  * `indicators.py`: 기술적 지표 관련 기능을 제공하는 IndicatorsMixin 클래스
  * `helpers.py`: UI 관련 헬퍼 함수
  * `styles.py`: UI 스타일 정의

* `utils/`: 유틸리티 함수 및 헬퍼 클래스
  * `stream.py`: 콘솔 출력 리디렉션을 위한 Stream 클래스
  * `calculations.py`: 기술적 지표 계산 함수 (볼린저 밴드, CCI 등)
  * `signals.py`: 매매 신호 감지 함수

## 기술적 지표

### 볼린저 밴드 (Bollinger Bands)
볼린저 밴드는 가격의 변동성을 시각화하는 지표로, 중간 밴드(20일 이동평균선)와 상/하단 밴드(중간 밴드에서 표준편차의 2배)로 구성됩니다. 이 지표는 가격의 과매수/과매도 상태를 판단하는 데 도움이 됩니다.

### CCI (Commodity Channel Index)
CCI는 가격이 평균 가격으로부터 얼마나 멀리 벗어났는지를 측정하는 지표입니다. 일반적으로 +100 이상이면 과매수, -100 이하면 과매도 상태로 간주합니다. 이 애플리케이션에서는 CCI 지표를 별도의 차트 영역에 표시합니다.

## 기여 방법

1. 이 저장소를 포크합니다.
2. 새 기능 브랜치를 생성합니다 (`git checkout -b feature/amazing-feature`).
3. 변경 사항을 커밋합니다 (`git commit -m 'Add some amazing feature'`).
4. 브랜치에 푸시합니다 (`git push origin feature/amazing-feature`).
5. Pull Request를 생성합니다.

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 LICENSE 파일을 참조하세요.

## 연락처

질문이나 피드백이 있으시면 이슈를 등록해 주세요.
