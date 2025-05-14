# 바이낸스 실시간 차트 애플리케이션

이 애플리케이션은 바이낸스 (USDⓈ-M 선물) BTC/USDT 1시간 봉 데이터를 실시간 캔들스틱 차트로 표시합니다. 데이터 수집에는 `ccxt`와 `ccxt.pro`를 사용하여 REST API 및 WebSocket을 이용하고, 그래픽 사용자 인터페이스(GUI)에는 `PyQt6`, 차트에는 `pyqtgraph`를 사용합니다.

## 주요 기능

*   바이낸스 USDⓈ-M 선물의 BTC/USDT 1시간 봉 실시간 캔들스틱 차트 표시.
*   REST API를 사용한 초기 차트 데이터 로딩.
*   WebSocket 연결을 통한 실시간 데이터 업데이트.
*   WebSocket 초기화 실패 시 REST API 폴링으로 자동 전환.
*   상호작용 가능한 차트:
    *   마우스 움직임을 따라다니는 십자선 커서.
    *   마우스 커서 아래 캔들의 OHLCV(시가, 고가, 저가, 종가, 거래량) 데이터 및 타임스탬프 표시.
*   타임스탬프를 포함한 애플리케이션 로그를 표시하는 내장 콘솔 창.
*   차트 및 콘솔을 위한 어두운 테마.
*   차트 오른쪽에 가격(Y축) 표시.
*   사용자 친화적인 인터페이스 및 반응형 디자인

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
* asyncio - 비동기 프로그래밍 라이브러리 (Python 3.4 이상 버전에 기본 포함)

다음 명령어를 사용하여 모든 필요한 라이브러리를 한 번에 설치할 수 있습니다:

```bash
pip install PyQt6 pyqtgraph ccxt pandas
```

ccxt.pro를 사용하려면 별도의 라이선스가 필요할 수 있습니다. 자세한 내용은 [ccxt 공식 문서](https://github.com/ccxt/ccxt)를 참조하세요.

## 실행 방법

1.  모든 의존성이 설치되었는지 확인합니다.
2.  터미널에서 프로젝트 디렉토리로 이동합니다.
3.  메인 애플리케이션 파일을 실행합니다:

    ```bash
    python main.py
    ```

## 프로젝트 구조

*   `main.py`: 메인 애플리케이션 진입점. PyQt 애플리케이션을 초기화하고 MainWindow를 생성합니다.
*   `ui_components.py`: `MainWindow` 클래스를 포함하며, 주 UI, 차트 설정 및 다른 구성 요소 통합을 처리합니다. 애플리케이션의 주요 UI 컴포넌트와 레이아웃을 정의합니다.
*   `data_worker.py`: 별도의 스레드에서 WebSocket을 통해 거래소로부터 데이터를 가져오고 처리하는 `Worker` 및 `WorkerSignals` 클래스를 포함합니다. 데이터 수집과 처리 로직이 여기 구현되어 있습니다.
*   `custom_plot_items.py`: 맞춤형 차트 렌더링을 위한 `CandlestickItem`, `DateAxisItem`과 같은 사용자 정의 `pyqtgraph` 아이템을 정의합니다. 캔들스틱 차트와 날짜 축의 시각적 표현을 담당합니다.
*   `utils.py`: 콘솔 출력을 UI로 리디렉션하는 `Stream`과 같은 유틸리티 클래스와 다양한 헬퍼 함수를 포함합니다.

## 기여 방법

1.  이 저장소를 포크합니다.
2.  새 기능 브랜치를 생성합니다 (`git checkout -b feature/amazing-feature`).
3.  변경 사항을 커밋합니다 (`git commit -m 'Add some amazing feature'`).
4.  브랜치에 푸시합니다 (`git push origin feature/amazing-feature`).
5.  Pull Request를 생성합니다.

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 LICENSE 파일을 참조하세요.

## 연락처

질문이나 피드백이 있으시면 이슈를 등록해 주세요.
