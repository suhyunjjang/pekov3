"""
메인 애플리케이션 윈도우 클래스를 정의하는 모듈
"""

import pandas as pd
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QLabel, QTextEdit, QComboBox, QPushButton, QHBoxLayout, QSplitter
from PyQt6.QtCore import QTimer, Qt, pyqtSlot, QThread
import pyqtgraph as pg
import sys
import traceback

from core.exchange import ExchangeManager
from core.data_worker import Worker, WorkerSignals
from plotting.custom_plot_items import CandlestickItem, DateAxisItem
from utils.stream import Stream
from ui.chart import ChartMixin
from ui.indicators import IndicatorsMixin
from ui.styles import BOLLINGER_BUTTON_ACTIVE_STYLE, CCI_BUTTON_ACTIVE_STYLE, CONSOLE_STYLE
from config.settings import (
    DEFAULT_EXCHANGE_ID, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME, DEFAULT_LIMIT,
    BOLLINGER_WINDOW, BOLLINGER_STD, CCI_WINDOW,
    SHOW_BOLLINGER, SHOW_CCI
)

class MainWindow(QMainWindow, ChartMixin, IndicatorsMixin):
    """
    애플리케이션의 메인 윈도우 클래스
    ChartMixin과 IndicatorsMixin을 상속받아 차트와 지표 관련 기능 구현
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Binance Chart")
        self.setGeometry(100, 100, 1000, 850)

        # 원본 표준 출력/에러 스트림 저장
        self.original_stdout = sys.__stdout__
        self.original_stderr = sys.__stderr__

        # 데이터 및 상태 초기화
        self.data_df = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        self.detailed_candle_data = []
        
        # 설정값 초기화
        self.symbol = DEFAULT_SYMBOL
        self.timeframe = DEFAULT_TIMEFRAME
        self.limit = DEFAULT_LIMIT
        
        # 지표 설정 초기화
        self.show_bollinger = SHOW_BOLLINGER
        self.show_cci = SHOW_CCI
        self.bollinger_window = BOLLINGER_WINDOW
        self.bollinger_std = BOLLINGER_STD
        self.cci_window = CCI_WINDOW
        
        # 크로스헤어 및 가격선 초기화
        self.init_crosshairs()
        self.init_price_line()
        self.init_info_labels()
        
        # 지표 관련 변수 초기화
        self.init_indicator_variables()
        
        # 거래소 연결 초기화
        self.exchange_manager = ExchangeManager(DEFAULT_EXCHANGE_ID)
        self.rest_exchange = self.exchange_manager.rest_exchange
        self.exchange = self.exchange_manager.ws_exchange
        
        # 차트 초기화 (ChartMixin에서 제공) - UI 초기화 전에 수행
        self.init_charts()
        
        # UI 초기화
        self.init_ui()
        
        # 콘솔 출력 리디렉션
        self.redirect_std_streams()
        
        # 윈도우 제목 업데이트
        self.setWindowTitle(f"{self.symbol} - {self.timeframe} Chart")
        
        # WebSocket 또는 REST API 초기화
        self.init_data_connection()
        
        # 볼린저 밴드와 CCI 버튼 스타일 초기 설정
        if self.show_bollinger:
            self.bollinger_button.setStyleSheet(BOLLINGER_BUTTON_ACTIVE_STYLE)
        
        if self.show_cci:
            self.cci_button.setStyleSheet(CCI_BUTTON_ACTIVE_STYLE)
    
    def init_crosshairs(self):
        """크로스헤어 초기화"""
        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('gray', width=1, style=Qt.PenStyle.DashLine))
        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('gray', width=1, style=Qt.PenStyle.DashLine))
        self.crosshair_v.setVisible(False)
        self.crosshair_h.setVisible(False)
        
        # CCI 차트용 크로스헤어
        self.cci_crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('gray', width=1, style=Qt.PenStyle.DashLine))
        self.cci_crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('gray', width=1, style=Qt.PenStyle.DashLine))
        self.cci_crosshair_v.setVisible(False)
        self.cci_crosshair_h.setVisible(False)
    
    def init_price_line(self):
        """현재 가격 라인 초기화"""
        self.current_price_line = pg.InfiniteLine(
            angle=0, 
            movable=False, 
            pen=pg.mkPen('b', width=1, style=Qt.PenStyle.DashLine),
            label='{value:.4f}',
            labelOpts={
                'position': 0.96, 
                'color': (255, 255, 255),
                'fill': (0, 120, 255, 150),
                'anchor': (1, 0.5),
                'movable': True 
            }
        )
        self.current_price_line.setVisible(False)
    
    def init_info_labels(self):
        """정보 라벨 초기화"""
        # 캔들 정보 라벨
        self.candle_info_label = pg.LabelItem(justify='left', color='white', anchor=(0,1))
        self.candle_info_label.setVisible(False)
        
        # CCI 정보 라벨
        self.cci_info_label = pg.LabelItem(justify='left', color='white', anchor=(0,1))
        self.cci_info_label.setVisible(False)
    
    def init_indicator_variables(self):
        """지표 관련 변수 초기화"""
        # 볼린저 밴드 관련 변수
        self.bollinger_upper_curve = None
        self.bollinger_middle_curve = None
        self.bollinger_lower_curve = None
        
        # CCI 관련 변수
        self.cci_plot_item = None
        self.cci_curve = None
        self.cci_current_line = None
        self.cci_data = []
        self.cci_buy_markers = []
        self.cci_sell_markers = []
    
    def init_ui(self):
        """UI 컴포넌트 초기화"""
        # 중앙 위젯 설정
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 컨트롤 레이아웃
        controls_layout = QHBoxLayout()
        
        # 심볼 콤보박스
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(self.exchange_manager.get_supported_symbols())
        self.symbol_combo.setCurrentText(self.symbol)
        
        # 타임프레임 콤보박스
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '3d', '1w'])
        self.timeframe_combo.setCurrentText(self.timeframe)
        
        # 차트 로드 버튼
        self.load_chart_button = QPushButton("Load Chart")
        self.load_chart_button.clicked.connect(self.handle_load_chart_button)
        
        # 뷰 초기화 버튼
        self.reset_view_button = QPushButton("뷰 초기화")
        self.reset_view_button.clicked.connect(self.reset_chart_view)
        
        # 오토스케일 버튼
        self.auto_scale_button = QPushButton("오토스케일")
        self.auto_scale_button.setCheckable(True)
        self.auto_scale_button.setChecked(False)
        self.auto_scale_button.clicked.connect(self.toggle_auto_scale)
        self.auto_scale_button.setMinimumWidth(100)
        
        # 볼린저 밴드 버튼
        self.bollinger_button = QPushButton("볼린저밴드")
        self.bollinger_button.setCheckable(True)
        self.bollinger_button.setChecked(self.show_bollinger)
        self.bollinger_button.clicked.connect(self.toggle_bollinger)
        
        # CCI 버튼
        self.cci_button = QPushButton("CCI")
        self.cci_button.setCheckable(True)
        self.cci_button.setChecked(self.show_cci)
        self.cci_button.clicked.connect(self.toggle_cci)
        
        # 컨트롤 레이아웃에 위젯 추가
        controls_layout.addWidget(QLabel("Symbol:"))
        controls_layout.addWidget(self.symbol_combo)
        controls_layout.addWidget(QLabel("Timeframe:"))
        controls_layout.addWidget(self.timeframe_combo)
        controls_layout.addWidget(self.load_chart_button)
        controls_layout.addWidget(self.reset_view_button)
        controls_layout.addWidget(self.auto_scale_button)
        controls_layout.addWidget(self.bollinger_button)
        controls_layout.addWidget(self.cci_button)
        controls_layout.addStretch(1)
        
        # 메인 레이아웃에 컨트롤 레이아웃 추가
        main_layout.addLayout(controls_layout)
        
        # 차트와 콘솔을 나누는 메인 스플리터 생성
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 콘솔 텍스트 영역
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        # 최대 높이 제한 제거 (사용자가 조절할 수 있도록)
        # self.console_output.setMaximumHeight(100)
        self.console_output.setStyleSheet(CONSOLE_STYLE)
        self.console_output.setMinimumHeight(50)  # 최소 높이만 설정
        
        # 차트와 콘솔을 스플리터에 추가
        self.main_splitter.addWidget(self.chart_splitter)
        self.main_splitter.addWidget(self.console_output)
        
        # 스플리터 비율 설정 (차트:콘솔 = 9:1)
        self.main_splitter.setSizes([900, 100])
        
        # 메인 레이아웃에 메인 스플리터 추가
        main_layout.addWidget(self.main_splitter, stretch=1)
        
        # 중앙 위젯에 메인 레이아웃 설정
        self.central_widget.setLayout(main_layout)
    
    def redirect_std_streams(self):
        """표준 출력/에러 스트림을 UI로 리디렉션"""
        # 표준 출력 리디렉션
        self.stdout_stream = Stream(original_stream=self.original_stdout)
        self.stdout_stream.new_text.connect(self.append_log)
        sys.stdout = self.stdout_stream
        
        # 표준 에러 리디렉션
        self.stderr_stream = Stream(original_stream=self.original_stderr)
        self.stderr_stream.new_text.connect(self.append_log)
        sys.stderr = self.stderr_stream
        
        print("콘솔이 초기화되었습니다. 표준 출력 및 에러가 콘솔에 리디렉션됩니다.")
    
    def init_data_connection(self):
        """데이터 연결 초기화 (WebSocket 또는 REST)"""
        self.worker = None
        self.thread = None
        self.timer = None
        
        if self.exchange:
            print("WebSocket 연결을 초기화합니다.")
            self.init_worker_thread()
            
            if self.rest_exchange:
                self.initial_load_rest()
            else:
                print("경고: 초기 차트 데이터 로드를 위한 REST API를 사용할 수 없습니다.")
        elif self.rest_exchange:
            print("WebSocket 연결을 초기화할 수 없습니다. REST API로 폴백합니다.")
            self.initial_load_rest()
            
            # REST API 폴링 타이머 설정
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_chart_rest)
            self.timer.start(60000)  # 1분마다 업데이트
            print("REST API 폴링 타이머가 시작되었습니다.")
        else:
            print("치명적 오류: 거래소 연결을 초기화할 수 없습니다.")
            self.append_log("치명적 오류: 거래소 연결을 초기화할 수 없습니다.")
    
    def init_worker_thread(self):
        """WebSocket 워커 스레드 초기화"""
        if not self.exchange:
            print("오류: WebSocket 워커를 초기화할 수 없습니다. 거래소 객체가 초기화되지 않았습니다.")
            return
        
        # 새 WebSocket 인스턴스 생성
        ws_exchange = self.exchange_manager.create_ws_exchange()
        
        # 워커 및 스레드 생성
        self.worker = Worker(ws_exchange, self.symbol, self.timeframe)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        
        # 시그널 연결
        self.worker.signals.new_data.connect(self.update_chart_from_websocket)
        self.worker.signals.error.connect(self.handle_worker_error)
        self.worker.signals.finished.connect(self.thread.quit)
        self.worker.signals.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        # 스레드 시작
        self.thread.started.connect(self.worker.start_streaming)
        self.thread.start()
        print("WebSocket 워커 스레드가 시작되었습니다.")
    
    def initial_load_rest(self):
        """REST API를 사용하여 초기 데이터 로드"""
        print(f"REST API를 사용하여 초기 데이터를 로드합니다: {self.symbol} {self.timeframe}")
        
        if not self.rest_exchange:
            print("오류: REST API를 사용할 수 없습니다.")
            return
        
        try:
            # 데이터 가져오기
            df = self.exchange_manager.fetch_ohlcv(self.symbol, self.timeframe, self.limit)
            
            if df is not None and not df.empty:
                self.data_df = df
                print(f"{len(df)} 개의 캔들 데이터를 로드했습니다.")
                
                # 차트 업데이트
                self.plot_data(auto_range=True)
            else:
                print(f"REST API에서 {self.symbol} {self.timeframe} 데이터를 가져올 수 없습니다.")
        except Exception as e:
            print(f"초기 데이터 로드 중 오류 발생: {e}")
            traceback.print_exc()
    
    @pyqtSlot(list)
    def update_chart_from_websocket(self, kline_data_list):
        """WebSocket으로부터 받은 데이터로 차트 업데이트"""
        if not kline_data_list or len(kline_data_list) == 0:
            return
        
        try:
            # 데이터프레임에 새 캔들 데이터 추가/업데이트
            timestamp_ms = kline_data_list[0][0]  # 첫 번째 데이터의 타임스탬프
            dt = pd.to_datetime(timestamp_ms, unit='ms')
            
            # 기존 데이터프레임에서 같은 타임스탬프를 가진 행 찾기
            existing = self.data_df[self.data_df['timestamp'] == dt]
            
            if not existing.empty:
                # 기존 데이터 업데이트
                self.data_df.loc[self.data_df['timestamp'] == dt, ['open', 'high', 'low', 'close', 'volume']] = [
                    kline_data_list[0][1], kline_data_list[0][2], kline_data_list[0][3], 
                    kline_data_list[0][4], kline_data_list[0][5]
                ]
            else:
                # 새 행 추가
                new_row = pd.DataFrame({
                    'timestamp': [dt],
                    'open': [kline_data_list[0][1]],
                    'high': [kline_data_list[0][2]],
                    'low': [kline_data_list[0][3]],
                    'close': [kline_data_list[0][4]],
                    'volume': [kline_data_list[0][5]]
                })
                self.data_df = pd.concat([self.data_df, new_row], ignore_index=True)
                self.data_df = self.data_df.sort_values(by='timestamp').reset_index(drop=True)
            
            # 차트 업데이트
            self.plot_data(auto_range=False)
        except Exception as e:
            print(f"WebSocket 데이터 처리 중 오류 발생: {e}")
            traceback.print_exc()
    
    def update_chart_rest(self):
        """REST API를 사용하여 차트 업데이트 (WebSocket 대체용)"""
        if not self.rest_exchange:
            print("REST API를 사용할 수 없습니다.")
            return
        
        try:
            # 데이터 가져오기
            df = self.exchange_manager.fetch_ohlcv(self.symbol, self.timeframe, self.limit)
            
            if df is not None and not df.empty:
                self.data_df = df
                print(f"REST API: {len(df)} 개의 캔들 데이터를 업데이트했습니다.")
                
                # 차트 업데이트
                self.plot_data(auto_range=False)
            else:
                print(f"REST API에서 {self.symbol} {self.timeframe} 데이터를 가져올 수 없습니다.")
        except Exception as e:
            print(f"REST API 데이터 업데이트 중 오류 발생: {e}")
            traceback.print_exc()
    
    def handle_worker_error(self, error_message):
        """워커 에러 처리"""
        self.append_log(f"워커 에러: {error_message}")
    
    def closeEvent(self, event):
        """애플리케이션 종료 시 처리"""
        print("애플리케이션을 종료합니다...")
        
        # 워커 스레드 정지
        self.stop_worker_thread()
        
        # REST API 타이머 정지
        if self.timer and self.timer.isActive():
            self.timer.stop()
            print("REST API 타이머가 정지되었습니다.")
        
        print("애플리케이션이 정상적으로 종료되었습니다.")
        event.accept()
    
    def stop_worker_thread(self):
        """워커 스레드 정지"""
        if self.thread and self.thread.isRunning():
            print("워커 스레드를 정지합니다...")
            
            if self.worker:
                self.worker.stop()  # 워커 루프 정지 및 거래소 연결 닫기
            
            self.thread.quit()  # QThread에 종료 요청
            
            # 최대 5초 대기
            if not self.thread.wait(5000):
                print("워커 스레드가 제한 시간 내에 종료되지 않았습니다. 강제 종료합니다.")
                self.thread.terminate()
                self.thread.wait()
            
            print("워커 스레드가 정지되었습니다.")
    
    def handle_load_chart_button(self):
        """차트 로드 버튼 클릭 이벤트 처리"""
        # 기존 연결 정지
        self.stop_worker_thread()
        
        # REST API 타이머 정지
        if self.timer and self.timer.isActive():
            self.timer.stop()
        
        # 새 설정 가져오기
        new_symbol = self.symbol_combo.currentText()
        new_timeframe = self.timeframe_combo.currentText()
        
        # 변경사항이 없으면 그냥 반환
        if new_symbol == self.symbol and new_timeframe == self.timeframe:
            print("심볼과 타임프레임이 변경되지 않았습니다.")
            # 이미 정지된 연결 다시 시작
            self.init_data_connection()
            return
        
        # 설정 업데이트
        self.symbol = new_symbol
        self.timeframe = new_timeframe
        print(f"새 차트 로드: {self.symbol} {self.timeframe}")
        
        # 윈도우 제목 업데이트
        self.setWindowTitle(f"{self.symbol} - {self.timeframe} Chart")
        
        # 데이터 초기화
        self.data_df = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # REST API로 초기 데이터 로드
        self.initial_load_rest()
        
        # WebSocket 또는 REST API 타이머 다시 시작
        self.init_data_connection()
    
    @pyqtSlot(str)
    def append_log(self, text):
        """콘솔에 로그 추가"""
        if self.console_output is None:
            return
        
        self.console_output.append(text)
        self.console_output.ensureCursorVisible()
    
    def mouse_moved_on_chart(self, pos):
        """마우스 이동 이벤트 처리"""
        # 메인 차트 좌표계 변환
        if self.plot_item.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_item.vb.mapSceneToView(pos)
            x, y = mouse_point.x(), mouse_point.y()
            
            # 크로스헤어 위치 업데이트
            self.crosshair_v.setPos(x)
            self.crosshair_h.setPos(y)
            self.crosshair_v.setVisible(True)
            self.crosshair_h.setVisible(True)
            
            # 가장 가까운 캔들 찾기
            self.update_candle_info(x, y)
        elif self.cci_plot_item and self.cci_plot_item.sceneBoundingRect().contains(pos) and self.show_cci:
            # CCI 차트 좌표계 변환
            mouse_point = self.cci_plot_item.vb.mapSceneToView(pos)
            x, y = mouse_point.x(), mouse_point.y()
            
            # CCI 크로스헤어 위치 업데이트
            self.cci_crosshair_v.setPos(x)
            self.cci_crosshair_h.setPos(y)
            self.cci_crosshair_v.setVisible(True)
            self.cci_crosshair_h.setVisible(True)
            
            # 가장 가까운 CCI 데이터 찾기
            self.update_cci_info(x, y)
        else:
            # 차트 영역 밖으로 나가면 크로스헤어 숨기기
            self.hide_crosshairs()
    
    def update_candle_info(self, x, y):
        """캔들 정보 업데이트"""
        if not self.detailed_candle_data:
            return
        
        closest_candle = None
        min_distance = float('inf')
        
        for candle in self.detailed_candle_data:
            distance = abs(candle['time_axis_val'] - x)
            if distance < min_distance:
                min_distance = distance
                closest_candle = candle
        
        if closest_candle:
            # 캔들 정보 표시
            info_text = f"Time: {closest_candle['timestamp_display']}\n"
            info_text += f"O: {closest_candle['open']:.4f}  H: {closest_candle['high']:.4f}\n"
            info_text += f"L: {closest_candle['low']:.4f}  C: {closest_candle['close']:.4f}\n"
            info_text += f"V: {closest_candle['volume']:.2f}"
            
            self.candle_info_label.setText(info_text)
            self.candle_info_label.setVisible(True)
    
    def update_cci_info(self, x, y):
        """CCI 정보 업데이트"""
        if not self.cci_data:
            return
        
        closest_cci = None
        min_distance = float('inf')
        
        for time_val, cci_val in self.cci_data:
            distance = abs(time_val - x)
            if distance < min_distance:
                min_distance = distance
                closest_cci = (time_val, cci_val)
        
        if closest_cci:
            # 해당 시간의 캔들 찾기
            matching_candle = next((c for c in self.detailed_candle_data if c['time_axis_val'] == closest_cci[0]), None)
            
            if matching_candle:
                # CCI 정보 표시
                info_text = f"Time: {matching_candle['timestamp_display']}\n"
                info_text += f"CCI: {closest_cci[1]:.2f}"
                
                self.cci_info_label.setText(info_text)
                self.cci_info_label.setVisible(True)
    
    def hide_crosshairs(self):
        """크로스헤어 숨기기"""
        # 메인 차트 크로스헤어 숨기기
        self.crosshair_v.setVisible(False)
        self.crosshair_h.setVisible(False)
        self.candle_info_label.setVisible(False)
        
        # CCI 차트 크로스헤어 숨기기
        self.cci_crosshair_v.setVisible(False)
        self.cci_crosshair_h.setVisible(False)
        self.cci_info_label.setVisible(False) 