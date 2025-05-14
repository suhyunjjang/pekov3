import pandas as pd
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QTextEdit, QLineEdit, QComboBox, QPushButton, QHBoxLayout, QSplitter
from PyQt6.QtCore import QTimer, QDateTime, Qt, QRectF, QPointF, pyqtSignal, QObject, pyqtSlot, QThread
from PyQt6.QtGui import QPainter, QBrush, QPen, QColor
from datetime import datetime
import pyqtgraph as pg
import ccxt # For initial REST load if ccxt.pro not used for it
import ccxt.pro as ccxtpro # For WebSocket
import asyncio
import threading
import traceback
import sys # For stdout/stderr redirection

from data_worker import WorkerSignals, Worker
from custom_plot_items import CandlestickItem, DateAxisItem # Import from new module
from utils import Stream # Import from new utils module

# Stream class to redirect stdout/stderr to a PyQt signal
# class Stream(QObject):
#     new_text = pyqtSignal(str)
#
#     def write(self, text):
#         self.new_text.emit(str(text))
#
#     def flush(self): # pragma: no cover
#         # This flush method is needed for file-like object compatibility.
#         pass

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Binance Chart") # Initial generic title
        self.setGeometry(100, 100, 1000, 850) # Adjusted height for console and controls

        # Store original stdout/stderr before redirection
        self.original_stdout = sys.__stdout__
        self.original_stderr = sys.__stderr__

        self.data_df = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        self.exchange = None  # For ccxtpro (WebSocket)
        self.rest_exchange = None # For ccxt (REST API)
        
        # Default values, will be updated from UI or initial settings
        self.symbol = 'BTC/USDT' # Default symbol
        self.timeframe = '1h'    # Default timeframe
        self.limit = 500 
        self.rest_exchange_id = 'binanceusdm' 
        self.ccxtpro_exchange_id = 'binanceusdm'

        self.worker = None # WebSocket worker
        self.thread = None # QThread for worker
        self.timer = None  # Timer for REST polling fallback

        self.detailed_candle_data = [] # For hover info

        # Crosshair lines
        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('gray', width=1, style=Qt.PenStyle.DashLine))
        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('gray', width=1, style=Qt.PenStyle.DashLine))
        self.crosshair_v.setVisible(False)
        self.crosshair_h.setVisible(False)
        
        # Crosshair lines for CCI chart
        self.cci_crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('gray', width=1, style=Qt.PenStyle.DashLine))
        self.cci_crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('gray', width=1, style=Qt.PenStyle.DashLine))
        self.cci_crosshair_v.setVisible(False)
        self.cci_crosshair_h.setVisible(False)

        # Current Price Line and Label
        self.current_price_line = pg.InfiniteLine(
            angle=0, 
            movable=False, 
            pen=pg.mkPen(QColor(0, 120, 255, 200), width=1, style=Qt.PenStyle.DashLine),
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
        # Set Z-value for the label of current_price_line to be drawn on top
        if hasattr(self.current_price_line, 'label') and isinstance(self.current_price_line.label, pg.TextItem):
            self.current_price_line.label.setZValue(20) # Higher Z-value to draw on top of axis items

        # Candle info label for hover
        self.candle_info_label = pg.LabelItem(justify='left', color='white', anchor=(0,1)) # Anchor label's top-left
        self.candle_info_label.setVisible(False)
        
        # CCI 정보 라벨 추가
        self.cci_info_label = pg.LabelItem(justify='left', color='white', anchor=(0,1))
        self.cci_info_label.setVisible(False)
        
        # 기술적 지표 관련 속성 초기화
        self.show_bollinger = True  # 볼린저 밴드 표시 여부
        self.show_cci = True        # CCI 지표 표시 여부
        self.bollinger_window = 20   # 볼린저 밴드 계산 기간
        self.bollinger_std = 2.0     # 볼린저 밴드 표준편차 계수
        self.cci_window = 20         # CCI 계산 기간
        
        # 지표를 그릴 때 사용할 플롯 아이템
        self.bollinger_upper_curve = None
        self.bollinger_middle_curve = None
        self.bollinger_lower_curve = None
        self.cci_plot_item = None    # CCI를 그릴 별도의 플롯 아이템
        self.cci_curve = None        # CCI 곡선
        self.cci_current_line = None # CCI 현재값 표시선
        self.cci_data = []           # CCI 데이터 저장용
        self.cci_buy_markers = []    # CCI 매수 신호 마커
        self.cci_sell_markers = []   # CCI 매도 신호 마커

        self.init_ui()
        self.setWindowTitle(f"{self.symbol} - {self.timeframe} Chart") # Set initial title based on defaults
        self.redirect_std_streams() # Redirect print statements to console
        self.init_exchanges() 

        if self.exchange: 
            print("ccxtpro exchange initialized. Starting WebSocket worker...")
            self.init_worker_thread() # Start with default/initial symbol/timeframe
            if self.rest_exchange:
                self.initial_load_rest()
            else:
                print("WARNING: REST exchange not available for initial chart population.")
        elif self.rest_exchange: 
            print("ccxtpro exchange FAILED to initialize. Falling back to REST API polling.")
            self.initial_load_rest() # This will now use self.data_df and self.plot_data()
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_chart_rest)
            self.timer.start(60000) 
            print("REST API polling timer started.")
        else: 
            print("FATAL: Both ccxtpro and ccxt exchanges FAILED to initialize. No data can be fetched.")
            self.append_log("FATAL: Both ccxtpro and ccxt exchanges FAILED to initialize. No data can be fetched.")

        # 볼린저 밴드 버튼 스타일 초기 설정 (활성화 상태로)
        self.bollinger_button.setStyleSheet("""
            QPushButton {
                background-color: #4080C0;
                color: white;
                font-weight: bold;
            }
        """)
        
        # CCI 버튼 스타일 초기 설정 (활성화 상태로)
        self.cci_button.setStyleSheet("""
            QPushButton {
                background-color: #40A040;
                color: white;
                font-weight: bold;
            }
        """)

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0,0,0,0)

        # Controls Layout
        controls_layout = QHBoxLayout()
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(['BTC/USDT', 'XRP/USDT', 'ETH/USDT', 'SOL/USDT'])
        self.symbol_combo.setCurrentText(self.symbol) # Set default selection

        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '3d', '1w'])
        self.timeframe_combo.setCurrentText(self.timeframe)
        self.load_chart_button = QPushButton("Load Chart")
        self.load_chart_button.clicked.connect(self.handle_load_chart_button)
        
        # Add reset view button
        self.reset_view_button = QPushButton("뷰 초기화")
        self.reset_view_button.clicked.connect(self.reset_chart_view)
        
        # Add auto-scale button
        self.auto_scale_button = QPushButton("오토스케일")
        self.auto_scale_button.setCheckable(True)  # Make it toggleable
        self.auto_scale_button.setChecked(False)   # Off by default
        self.auto_scale_button.clicked.connect(self.toggle_auto_scale)
        self.auto_scale_button.setMinimumWidth(100)
        
        # 지표 버튼 추가
        self.bollinger_button = QPushButton("볼린저밴드")
        self.bollinger_button.setCheckable(True)   # 토글 가능하게 설정
        self.bollinger_button.setChecked(True)     # 기본적으로 켜진 상태로 변경
        self.bollinger_button.clicked.connect(self.toggle_bollinger)
        
        self.cci_button = QPushButton("CCI")
        self.cci_button.setCheckable(True)         # 토글 가능하게 설정
        self.cci_button.setChecked(True)           # 기본적으로 켜진 상태로 변경
        self.cci_button.clicked.connect(self.toggle_cci)

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
        
        # Add controls layout to the main layout
        main_layout.addLayout(controls_layout)

        # 메인 차트와 CCI 차트를 담을 스플리터 생성
        self.chart_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 메인 차트와 CCI 차트를 위한 개별 위젯 생성
        self.main_chart_widget = pg.GraphicsLayoutWidget()
        self.cci_chart_widget = pg.GraphicsLayoutWidget()
        
        # 스플리터에 차트 위젯 추가
        self.chart_splitter.addWidget(self.main_chart_widget)
        self.chart_splitter.addWidget(self.cci_chart_widget)
        
        # 스플리터 사이즈 비율 설정 (메인 차트 : CCI 차트 = 3:1)
        # 여기서 초기 크기를 설정합니다
        total_height = 400  # 예상 총 높이 (실제 값은 나중에 조정됨)
        main_height = int(total_height * 0.75)
        cci_height = total_height - main_height
        self.chart_splitter.setSizes([main_height, cci_height])
        
        # CCI 차트는 기본적으로 표시
        self.cci_chart_widget.setVisible(True)
        
        # 메인 캔들차트와 볼린저밴드를 표시할 윗 영역
        self.date_axis = DateAxisItem(orientation='bottom')
        self.chart_widget = self.main_chart_widget.addPlot(row=0, col=0, axisItems={'bottom': self.date_axis})
        self.plot_item = self.chart_widget
        
        # CCI 지표를 위한 아래 위젯
        self.cci_date_axis = DateAxisItem(orientation='bottom')
        self.cci_plot_item = self.cci_chart_widget.addPlot(row=0, col=0, axisItems={'bottom': self.cci_date_axis})
        
        # 차트 간 X축 동기화
        self.cci_plot_item.setXLink(self.chart_widget)  # CCI가 메인 차트와 X축을 공유
        
        # 메인 차트 설정
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)

        # Configure axes
        self.plot_item.hideAxis('left')
        self.plot_item.showAxis('right')
        right_axis = self.plot_item.getAxis('right')
        right_axis.setLabel(text='Price', units='USDT')
        right_axis.enableAutoSIPrefix(False) # Disable SI prefix for price axis
        
        # CCI 차트 설정
        self.cci_plot_item.showGrid(x=True, y=True, alpha=0.3)
        self.cci_plot_item.hideAxis('left')
        self.cci_plot_item.showAxis('right')
        cci_right_axis = self.cci_plot_item.getAxis('right')
        cci_right_axis.setLabel(text='CCI')
        
        # CCI X축 라벨 숨기기 (메인 차트와 공유하므로 중복 표시 방지)
        self.cci_plot_item.getAxis('bottom').setStyle(showValues=False)
        
        # CCI 정보 라벨 설정
        cci_view_box = self.cci_plot_item.getViewBox()
        self.cci_info_label.setParentItem(cci_view_box)
        self.cci_info_label.anchor(itemPos=(0,1), parentPos=(0,1), offset=(5, 5))
        
        # 로그 스케일 모드 비활성화 - 항상 선형 스케일 사용
        self.plot_item.getViewBox().setLogMode(False, False)
        
        self.candlestick_item = None
        
        self.plot_item.addItem(self.crosshair_v, ignoreBounds=True)
        self.plot_item.addItem(self.crosshair_h, ignoreBounds=True)
        self.plot_item.addItem(self.current_price_line, ignoreBounds=True)
        
        # CCI 차트에 크로스헤어 추가
        self.cci_plot_item.addItem(self.cci_crosshair_v, ignoreBounds=True)
        self.cci_plot_item.addItem(self.cci_crosshair_h, ignoreBounds=True)

        # Setup auto-scale functionality
        self.auto_scale_active = False
        self.auto_scale_timer = QTimer()
        self.auto_scale_timer.setSingleShot(True)
        self.auto_scale_timer.timeout.connect(self.apply_auto_scale)
        
        # Connect ViewBox range change signals
        view_box = self.plot_item.getViewBox()
        view_box.sigRangeChanged.connect(self.on_range_changed)
        
        # Add candle info label
        self.candle_info_label.setParentItem(view_box)
        # Anchor top-left of label (itemPos=(0,1)) to top-left of ViewBox (parentPos=(0,1))
        # offset by (5 pixels right, -5 pixels down from top edge) to position slightly inside
        self.candle_info_label.anchor(itemPos=(0,1), parentPos=(0,1), offset=(5, 5)) 
        # Note: Y offset for anchor is typically positive for down, negative for up from parent anchor.
        # For parentPos=(0,1) which is top-left of viewbox, positive Y offset moves it DOWN from the top.
        # So offset=(5,5) should put it 5px right and 5px down from the top-left corner.
        
        # Console Output QTextEdit
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setFixedHeight(200) # Set a fixed height for the console
        # Apply dark theme to console
        self.console_output.setStyleSheet("""
            QTextEdit {
                background-color: #2E2E2E; /* Dark gray background */
                color: #F0F0F0; /* Light gray text */
                font-family: Consolas, Courier New, monospace;
                font-size: 9pt;
                border: 1px solid #555555;
            }
        """)

        main_layout.addWidget(self.chart_splitter) # 차트 레이아웃이 남은 공간을 차지
        main_layout.addWidget(self.console_output) # Console at the bottom

        container = QWidget() 
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Connect mouse signals - 메인 차트와 CCI 차트 모두 연결
        self.main_chart_widget.scene().sigMouseMoved.connect(self.mouse_moved_on_chart)
        self.cci_chart_widget.scene().sigMouseMoved.connect(self.mouse_moved_on_chart)

    def redirect_std_streams(self):
        # Redirect stdout
        self.stdout_stream = Stream(original_stream=self.original_stdout)
        self.stdout_stream.new_text.connect(self.append_log)
        sys.stdout = self.stdout_stream

        # Redirect stderr
        self.stderr_stream = Stream(original_stream=self.original_stderr)
        self.stderr_stream.new_text.connect(self.append_log) # Also send errors to the same console
        sys.stderr = self.stderr_stream
        
        print("Console initialized. Standard output and errors are now redirected to this console and terminal.")

    def init_exchanges(self):
        try:
            rest_exchange_class = getattr(ccxt, self.rest_exchange_id)
            self.rest_exchange = rest_exchange_class({
                'options': { 'defaultType': 'future', },
            })
            self.rest_exchange.load_markets()
            print(f"ccxt: Successfully initialized '{self.rest_exchange_id}' for REST API.")
        except AttributeError:
            print(f"ERROR: ccxt: Exchange ID '{self.rest_exchange_id}' not found in ccxt.")
            self.rest_exchange = None
        except Exception as e:
            print(f"ERROR: ccxt: Failed to initialize '{self.rest_exchange_id}' for REST API: {e}")
            self.rest_exchange = None

        try:
            print(f"Attempting to initialize ccxtpro.binance with options for USDⓈ-M futures.")
            self.exchange = ccxtpro.binance({
                'options': {
                    'defaultType': 'future', # For USDⓈ-M futures markets
                },
                # 'newUpdates': False, # Default is False, returns the whole list. True for only new updates.
            })
            # For ccxtpro, load_markets might be needed explicitly for some exchanges or methods
            # It's an async function. If needed, it should be run in the worker's async loop.
            # For watch_ohlcv, it often loads markets implicitly.
            print(f"ccxtpro: Successfully initialized ccxtpro.binance with 'future' defaultType for WebSocket.")
        except AttributeError as e_attr:
            print(f"ERROR: ccxtpro: Attribute error during initialization (ccxtpro.binance): {e_attr}")
            self.exchange = None
        except Exception as e:
            print(f"ERROR: ccxtpro: General exception during initialization: {e}")
            traceback.print_exc()
            self.exchange = None

    def init_worker_thread(self):
        if not self.exchange:
            print("ERROR: Cannot init_worker_thread, ccxtpro exchange is not initialized.")
            return

        # Assuming Worker is imported from data_worker
        self.worker = Worker(self.exchange, self.symbol, self.timeframe)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)

        self.worker.signals.new_data.connect(self.update_chart_from_websocket)
        self.worker.signals.error.connect(self.handle_worker_error)
        # Connect finished signal to quit the thread and clean up
        self.worker.signals.finished.connect(self.thread.quit)
        self.worker.signals.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.started.connect(self.worker.start_streaming)
        self.thread.start()
        print("WebSocket worker thread started.")
        

    def initial_load_rest(self):
        try:
            print(f"Attempting to fetch initial OHLCV data for {self.symbol} ({self.timeframe}) from {self.rest_exchange_id} (REST)...")
            if not self.rest_exchange:
                print("ERROR: REST exchange not initialized for initial_load_rest.")
                return

            if not self.rest_exchange.markets:
                 print(f"Loading markets for {self.rest_exchange_id}...")
                 self.rest_exchange.load_markets()

            ohlcv = self.rest_exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=self.limit)
            if ohlcv:
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col])
                
                self.data_df = df.sort_values(by='timestamp').reset_index(drop=True)
                self.plot_data(auto_range=True) # Auto-range on initial load
                print(f"Initial chart PLOTTED with REST API data. {len(self.data_df)} candles.")
            else:
                print("No data received from REST API for initial load.")
                self.data_df = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']) # Ensure empty df
                self.append_log(f"No initial data for {self.symbol} ({self.timeframe}) via REST.")
                self.plot_data(auto_range=True) # Still auto-range even if empty
        except Exception as e:
            print(f"Error fetching initial OHLCV data from REST API for {self.symbol} ({self.timeframe}): {e}")
            self.append_log(f"REST Error for {self.symbol}: {str(e)[:100]}...") # Log a snippet
            traceback.print_exc()
            self.data_df = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            self.plot_data(auto_range=True) # Auto-range even on error

    @pyqtSlot(list)
    def update_chart_from_websocket(self, kline_data_list):
        if not kline_data_list:
            # print("WebSocket: Received empty kline_data_list.")
            return

        # print(f"WebSocket: Received klines: {len(kline_data_list)}")

        new_data_df = pd.DataFrame(kline_data_list, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        new_data_df['timestamp'] = pd.to_datetime(new_data_df['timestamp'], unit='ms')
        
        # Ensure data types are correct for merging and plotting
        for col in ['open', 'high', 'low', 'close', 'volume']:
            new_data_df[col] = pd.to_numeric(new_data_df[col])

        if self.data_df.empty:
            self.data_df = new_data_df
        else:
            # Make sure self.data_df['timestamp'] is also datetime
            if not pd.api.types.is_datetime64_any_dtype(self.data_df['timestamp']):
                self.data_df['timestamp'] = pd.to_datetime(self.data_df['timestamp'], unit='ms')

            self.data_df = pd.concat([self.data_df, new_data_df])
            self.data_df.drop_duplicates(subset=['timestamp'], keep='last', inplace=True)
        
        self.data_df.sort_values('timestamp', inplace=True)
        self.data_df = self.data_df.tail(self.limit + 50) # Keep a bit more than limit for smoother updates
        self.data_df.reset_index(drop=True, inplace=True)
        
        self.plot_data(auto_range=False) # No auto-range on WebSocket updates
        # print(f"Chart updated via WebSocket. Candles: {len(self.data_df)}. Last: {self.data_df['timestamp'].iloc[-1] if not self.data_df.empty else 'N/A'}")

    def update_chart_rest(self):
        try:
            print(f"Updating chart with REST data for {self.symbol} ({self.timeframe})...")
            if not self.rest_exchange:
                print("ERROR: REST exchange not available for update_chart_rest.")
                return
            
            ohlcv_list = self.rest_exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=10) 
            
            if not ohlcv_list:
                print("No new data received from REST exchange for update.")
                return

            new_data_df = pd.DataFrame(ohlcv_list, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            new_data_df['timestamp'] = pd.to_datetime(new_data_df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                new_data_df[col] = pd.to_numeric(new_data_df[col])

            if self.data_df.empty:
                self.data_df = new_data_df.sort_values(by='timestamp').reset_index(drop=True)
            else:
                if not pd.api.types.is_datetime64_any_dtype(self.data_df['timestamp']):
                    self.data_df['timestamp'] = pd.to_datetime(self.data_df['timestamp'], unit='ms', errors='coerce')
                
                self.data_df = pd.concat([self.data_df, new_data_df])
                self.data_df.drop_duplicates(subset=['timestamp'], keep='last', inplace=True)
                self.data_df.sort_values('timestamp', inplace=True)
            
            self.data_df = self.data_df.tail(self.limit + 50) 
            self.data_df.reset_index(drop=True, inplace=True)
            self.plot_data(auto_range=False) # No auto-range on regular REST updates
            print(f"Chart updated with REST data. Total candles: {len(self.data_df)}")
        except Exception as e:
            print(f"Error updating chart with REST data: {e}")
            traceback.print_exc()

    def plot_data(self, auto_range=False):
        if self.data_df.empty:
            print("No data to plot.")
            if self.candlestick_item:
                self.candlestick_item.setData([])
            self.detailed_candle_data = [] # Clear detailed data too
            # Potentially hide info label as well if it was visible
            if self.candle_info_label: self.candle_info_label.setVisible(False) 
            if self.current_price_line: self.current_price_line.setVisible(False) # Hide current price line
            if self.cci_info_label: self.cci_info_label.setVisible(False) # Hide CCI info label
            
            # 지표 그래프 초기화
            if self.bollinger_upper_curve:
                self.plot_item.removeItem(self.bollinger_upper_curve)
                self.bollinger_upper_curve = None
            if self.bollinger_middle_curve:
                self.plot_item.removeItem(self.bollinger_middle_curve)
                self.bollinger_middle_curve = None
            if self.bollinger_lower_curve:
                self.plot_item.removeItem(self.bollinger_lower_curve)
                self.bollinger_lower_curve = None
            if self.cci_curve:
                self.cci_plot_item.removeItem(self.cci_curve)
                self.cci_curve = None
            
            # Only auto range if specifically requested, even if empty
            if auto_range:
                self.chart_widget.autoRange()
                print(f"Chart auto-ranged (empty chart).")
            return

        plot_df_copy = self.data_df.copy()
        
        # Ensure 'timestamp' is datetime (should be handled by data loading methods)
        if not pd.api.types.is_datetime64_any_dtype(plot_df_copy['timestamp']):
            # Attempt conversion if it's numeric (e.g., ms from WebSocket not yet converted)
            if pd.api.types.is_numeric_dtype(plot_df_copy['timestamp']):
                plot_df_copy['timestamp'] = pd.to_datetime(plot_df_copy['timestamp'], unit='ms', errors='coerce')
            else:
                print("Error: Timestamp column is not in a recognized datetime format.")
                if self.current_price_line: self.current_price_line.setVisible(False)
                return
        plot_df_copy.dropna(subset=['timestamp'], inplace=True) # Drop rows where conversion failed
        
        # This 'time_axis_val' is what CandlestickItem uses as 'time' (center of candle visual)
        plot_df_copy['time_axis_val'] = plot_df_copy['timestamp'].apply(lambda dt: dt.timestamp())
        plot_df_copy['timestamp_display'] = plot_df_copy['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')

        for col in ['open', 'high', 'low', 'close', 'volume']:
            plot_df_copy[col] = pd.to_numeric(plot_df_copy[col], errors='coerce')
        plot_df_copy.dropna(subset=['open', 'high', 'low', 'close', 'volume', 'time_axis_val'], inplace=True) # Ensure no NaNs for critical data

        self.detailed_candle_data = plot_df_copy[[
            'time_axis_val', 'open', 'high', 'low', 'close', 'volume', 'timestamp_display'
        ]].to_dict('records')

        candlestick_item_input_data = [
            {'time': d['time_axis_val'], 'open': d['open'], 'high': d['high'], 'low': d['low'], 'close': d['close']}
            for d in self.detailed_candle_data
        ]

        if not self.candlestick_item:
            if candlestick_item_input_data:
                # Pass the current timeframe to CandlestickItem
                self.candlestick_item = CandlestickItem(candlestick_item_input_data, timeframe=self.timeframe)
                self.plot_item.addItem(self.candlestick_item)
                print(f"CandlestickItem created and added to chart with timeframe {self.timeframe}.")
                auto_range = True  # Force auto-range when creating chart for the first time
            else:
                print("No records to create CandlestickItem for the first time.")
                return 
        else:
            # Check if timeframe needs to be updated
            if hasattr(self.candlestick_item, 'timeframe') and self.candlestick_item.timeframe != self.timeframe:
                self.candlestick_item.update_timeframe(self.timeframe)
                print(f"Updated candlestick timeframe to {self.timeframe}")
            self.candlestick_item.setData(candlestick_item_input_data)
        
        if not plot_df_copy.empty and 'close' in plot_df_copy.columns:
            latest_close_price = plot_df_copy['close'].iloc[-1]
            if pd.notna(latest_close_price):
                self.current_price_line.setValue(latest_close_price)
                self.current_price_line.setVisible(True)
            else:
                if self.current_price_line: self.current_price_line.setVisible(False)
        else:
            if self.current_price_line: self.current_price_line.setVisible(False)
        
        # 기술적 지표 계산 및 표시
        self.plot_indicators(plot_df_copy)
        
        # Only auto-range when explicitly requested (new symbol or reset view)
        # 그리고 오토스케일 기능이 켜져 있지 않은 경우에만 적용
        if auto_range and not self.auto_scale_active:
            self.chart_widget.autoRange()
            # CCI는 항상 자체적으로 크기 조정
            if self.show_cci and hasattr(self, '_cci_scaled') and not self._cci_scaled.get(f"{self.symbol}_{self.timeframe}", False):
                self.cci_plot_item.autoRange()
                if not hasattr(self, '_cci_scaled'):
                    self._cci_scaled = {}
                self._cci_scaled[f"{self.symbol}_{self.timeframe}"] = True
            print(f"Chart updated and auto-ranged to fit {self.symbol} price range.")

    def handle_worker_error(self, error_message):
        print(f"WebSocket Worker Error for {self.symbol} ({self.timeframe}): {error_message}")
        self.append_log(f"WS Error ({self.symbol}): {error_message}")
        # Optionally, attempt to restart the worker or switch to REST polling
        # For now, just print the error.
        # If worker stops, we might want to explicitly stop the QThread if it's still running
        # Consider if some errors should trigger fallback to REST polling.
        # For example, if symbol is invalid for WebSocket on this exchange.
        # self.stop_worker_thread() # Stop it to prevent repeated errors for a bad symbol/timeframe
        # print("Switching to REST polling due to WebSocket error.")
        # if self.rest_exchange and (not self.timer or not self.timer.isActive()):
        #     self.timer = QTimer(self)
        #     self.timer.timeout.connect(self.update_chart_rest)
        #     self.timer.start(60000)
        #     print("REST API polling timer started after WebSocket error.")

    def closeEvent(self, event):
        print("Closing application...")
        
        self.stop_worker_thread() # Use the helper method
        
        # if self.thread and self.thread.isRunning():
        #     print("Stopping worker thread...")
        #     if self.worker:
        #         self.worker.stop() # Signal worker to stop its loop and close exchange
        #     self.thread.quit()    # Ask the QThread to quit
        #     if not self.thread.wait(5000): # Wait up to 5 seconds
        #         print("Worker QThread did not quit in time. Terminating.")
        #         self.thread.terminate() # Force terminate if necessary
        #         self.thread.wait() # Wait again after termination
        #     print("Worker thread stopped.")
        if self.timer and self.timer.isActive(): # REST API timer
             self.timer.stop()
             print("REST API timer stopped.")
        
        # Explicitly close REST exchange if it was used and has a close method (rarely needed for ccxt sync)
        if self.rest_exchange and hasattr(self.rest_exchange, 'close'):
            try:
                print("Closing REST exchange connection (if applicable).")
                # For synchronous ccxt, close() is usually not needed unless it's managing persistent connections.
                # self.rest_exchange.close() 
            except Exception as e:
                print(f"Error closing REST exchange: {e}")
        
        print("Exiting application.")
        event.accept() 

    def stop_worker_thread(self):
        if self.thread and self.thread.isRunning():
            print("Stopping existing worker thread...")
            if self.worker:
                self.worker.stop()
            self.thread.quit()
            if not self.thread.wait(5000):
                print("Worker QThread did not quit in time. Terminating.")
                self.thread.terminate()
                self.thread.wait()
            print("Worker thread stopped.")
        self.worker = None
        self.thread = None

    def handle_load_chart_button(self):
        new_symbol = self.symbol_combo.currentText()
        new_timeframe = self.timeframe_combo.currentText()

        if not new_symbol: # Should not happen with QComboBox if items are present
            self.append_log("ERROR: Symbol cannot be empty.")
            return

        if new_symbol == self.symbol and new_timeframe == self.timeframe and not self.data_df.empty:
            print(f"Chart for {new_symbol} ({new_timeframe}) is already loaded.")
            return

        print(f"Load Chart button clicked. New Symbol: {new_symbol}, New Timeframe: {new_timeframe}")

        # Stop existing worker/timer
        self.stop_worker_thread()
        if self.timer and self.timer.isActive():
            print("Stopping REST API polling timer.")
            self.timer.stop()
            self.timer = None # Clear the timer

        # Check if we need to update the date_axis for a different timeframe
        timeframe_changed = new_timeframe != self.timeframe
        
        # Update symbol and timeframe
        self.symbol = new_symbol
        self.timeframe = new_timeframe
        self.setWindowTitle(f"{self.symbol} - {self.timeframe} Chart")
        
        # 새로운 심볼/타임프레임에 대한 CCI 스케일 초기화
        if hasattr(self, '_cci_scaled'):
            self._cci_scaled[f"{self.symbol}_{self.timeframe}"] = False

        # If timeframe changed, recreate date_axis for better tick spacing
        if timeframe_changed:
            print(f"Timeframe changed from {self.timeframe} to {new_timeframe}, updating X-axis...")
            # If candlestick_item exists, update its timeframe directly
            if self.candlestick_item:
                print(f"Updating candlestick timeframe to {self.timeframe}")
                self.candlestick_item.update_timeframe(self.timeframe)
            
            # Update X-axis by recreating DateAxisItem
            old_date_axis = self.date_axis
            self.date_axis = DateAxisItem(orientation='bottom')
            self.chart_widget.setAxisItems({'bottom': self.date_axis})
            print(f"X-axis updated for {self.timeframe} timeframe.")

        # Clear old data and chart items
        self.data_df = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        self.detailed_candle_data = []
        
        # 기술적 지표 관련 아이템 초기화
        if self.bollinger_upper_curve:
            self.plot_item.removeItem(self.bollinger_upper_curve)
            self.bollinger_upper_curve = None
        if self.bollinger_middle_curve:
            self.plot_item.removeItem(self.bollinger_middle_curve)
            self.bollinger_middle_curve = None
        if self.bollinger_lower_curve:
            self.plot_item.removeItem(self.bollinger_lower_curve)
            self.bollinger_lower_curve = None
        if self.cci_curve:
            self.cci_plot_item.removeItem(self.cci_curve)
            self.cci_curve = None
        
        # Only remove the candlestick_item if we're changing symbols or it doesn't exist
        if self.candlestick_item and new_symbol != self.symbol:
            self.plot_item.removeItem(self.candlestick_item)
            self.candlestick_item = None # Crucial to re-create it later
        
        # Also hide/clear crosshair, candle info label, current price line
        self.crosshair_v.setVisible(False)
        self.crosshair_h.setVisible(False)
        self.candle_info_label.setVisible(False)
        self.candle_info_label.setText("")
        self.current_price_line.setVisible(False)

        # Create a new ccxt.pro exchange instance for each symbol change to avoid event loop issues
        print("Creating new ccxt.pro exchange instance for new symbol/timeframe...")
        try:
            # Properly close existing exchange if it exists
            if self.exchange:
                print(f"Cleaning up old ccxt.pro exchange for new symbol...")
                self.exchange = None # Allow garbage collection
            
            # Create a new exchange instance
            self.exchange = ccxtpro.binance({
                'options': {
                    'defaultType': 'future', # For USDⓈ-M futures markets
                },
            })
            print(f"New ccxt.pro exchange instance created for {self.symbol}.")
        except Exception as e:
            print(f"ERROR: Failed to create new ccxt.pro exchange: {e}")
            traceback.print_exc()
            self.exchange = None

        # Re-initialize data fetching
        print("Re-initializing data fetching for new symbol/timeframe...")

        if self.rest_exchange: # Always try REST first for initial load
            self.initial_load_rest() # This will plot with auto_range=True
        else:
            print("WARNING: REST exchange not available for initial chart population.")
            self.append_log(f"Cannot load {self.symbol}, REST exchange not initialized.")
            self.plot_data(auto_range=True) # Auto-range even if just clearing the chart

        # Restart WebSocket if ccxtpro is available and REST load was attempted
        if self.exchange: 
            print("Attempting to restart WebSocket worker for new symbol/timeframe...")
            self.init_worker_thread()
        elif self.rest_exchange and not self.exchange: # If only REST is available, restart polling timer
            print("ccxtpro not available. Restarting REST API polling timer for new symbol/timeframe.")
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_chart_rest)
            self.timer.start(60000)
            print("REST API polling timer restarted.")
        else:
            print(f"Cannot start data fetching for {self.symbol}. No exchanges available.")
            self.append_log(f"No exchange available to fetch data for {self.symbol}.")

    @pyqtSlot(str)
    def append_log(self, text):
        stripped_text = text.strip()
        if not stripped_text: # Only append if there is actual content
            return
        
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        formatted_message = f"[{timestamp}] {stripped_text}"
        self.console_output.append(formatted_message)
        self.console_output.verticalScrollBar().setValue(self.console_output.verticalScrollBar().maximum()) # Auto-scroll 

    def mouse_moved_on_chart(self, pos): # pos is from scene().sigMouseMoved
        # Check if mouse is within the plot area (scene coordinates)
        plot_item_rect = self.chart_widget.sceneBoundingRect()
        cci_plot_item_rect = self.cci_plot_item.sceneBoundingRect() if self.show_cci else None
        
        is_in_main_chart = plot_item_rect.contains(pos)
        is_in_cci_chart = cci_plot_item_rect and cci_plot_item_rect.contains(pos) and self.show_cci
        
        if not (is_in_main_chart or is_in_cci_chart):
            # 둘 다 아닌 영역에 마우스가 있으면 모든 크로스헤어 숨김
            if self.crosshair_v.isVisible():
                self.crosshair_v.setVisible(False)
                self.crosshair_h.setVisible(False)
                self.candle_info_label.setVisible(False)
                self.candle_info_label.setText("")
            if self.show_cci and self.cci_crosshair_v.isVisible():
                self.cci_crosshair_v.setVisible(False)
                self.cci_crosshair_h.setVisible(False)
                self.cci_info_label.setVisible(False)
                self.cci_info_label.setText("")
            return

        # 마우스가 메인 차트에 있는 경우
        if is_in_main_chart:
            mouse_point = self.chart_widget.vb.mapSceneToView(pos)
            self.crosshair_v.setPos(mouse_point.x())
            self.crosshair_h.setPos(mouse_point.y())
            
            if not self.crosshair_v.isVisible():
                self.crosshair_v.setVisible(True)
                self.crosshair_h.setVisible(True)
            
            # CCI 차트도 표시 중이면 X 위치 동기화
            if self.show_cci:
                self.cci_crosshair_v.setPos(mouse_point.x())
                if not self.cci_crosshair_v.isVisible():
                    self.cci_crosshair_v.setVisible(True)
        
        # 마우스가 CCI 차트에 있는 경우
        elif is_in_cci_chart:
            mouse_point = self.cci_plot_item.vb.mapSceneToView(pos)
            self.cci_crosshair_v.setPos(mouse_point.x())
            self.cci_crosshair_h.setPos(mouse_point.y())
            
            if not self.cci_crosshair_v.isVisible():
                self.cci_crosshair_v.setVisible(True)
                self.cci_crosshair_h.setVisible(True)
            
            # 메인 차트 X 위치도 동기화
            self.crosshair_v.setPos(mouse_point.x())
            if not self.crosshair_v.isVisible():
                self.crosshair_v.setVisible(True)
                self.crosshair_h.setVisible(False)  # Y 위치는 동기화하지 않음

        # 공통 X 위치 기준으로 캔들 찾기
        current_x = self.crosshair_v.value()
        found_candle = None
        if self.candlestick_item and self.candlestick_item.data and self.detailed_candle_data:
            candle_visual_width_on_plot = self.candlestick_item.bar_width_seconds 
            min_dist = float('inf')
            
            for candle_data in self.detailed_candle_data:
                if abs(candle_data['time_axis_val'] - current_x) < candle_visual_width_on_plot / 2.0:
                    dist = abs(candle_data['time_axis_val'] - current_x)
                    if dist < min_dist:
                        min_dist = dist
                        found_candle = candle_data

        # 메인 차트의 캔들 정보 표시
        if found_candle:
            info_text = f"Time: {found_candle['timestamp_display']}\n"
            info_text += f"O: {found_candle['open']:.4f}  H: {found_candle['high']:.4f}\n"
            info_text += f"L: {found_candle['low']:.4f}  C: {found_candle['close']:.4f}\n"
            info_text += f"V: {found_candle['volume']:.2f}"
            self.candle_info_label.setText(info_text)
            if not self.candle_info_label.isVisible():
                self.candle_info_label.setVisible(True)
                
            # 같은 캔들의 CCI 값 찾기 (CCI 차트가 표시된 경우)
            if self.show_cci and self.cci_curve and found_candle:
                # CCI 값이 있는지 확인
                if hasattr(self, 'cci_data') and len(self.cci_data) > 0:
                    # 현재 캔들에 해당하는 CCI 값 찾기
                    timestamp = found_candle['time_axis_val']
                    cci_value = None
                    
                    # 정확히 같은 timestamp가 있는지 확인
                    for idx, (ts, val) in enumerate(self.cci_data):
                        if abs(ts - timestamp) < 0.001:  # 작은 오차 허용
                            cci_value = val
                            break
                    
                    if cci_value is not None:
                        cci_info_text = f"Time: {found_candle['timestamp_display']}\n"
                        cci_info_text += f"CCI: {cci_value:.2f}"
                        self.cci_info_label.setText(cci_info_text)
                        self.cci_info_label.setVisible(True)
                    else:
                        self.cci_info_label.setVisible(False)
                        self.cci_info_label.setText("")
        else:
            if self.candle_info_label.isVisible():
                self.candle_info_label.setVisible(False)
                self.candle_info_label.setText("")
            if self.cci_info_label.isVisible():
                self.cci_info_label.setVisible(False)
                self.cci_info_label.setText("")

    def mouse_left_chart(self): # This method might become redundant or be called by mouse_moved_on_chart
        # This logic is now handled at the beginning of mouse_moved_on_chart
        # Keeping it separate for now in case direct leave event is found/needed later for ViewBox specifically
        # However, for current approach, it's not directly connected to a signal.
        if self.crosshair_v.isVisible():
            self.crosshair_v.setVisible(False)
            self.crosshair_h.setVisible(False)
            self.candle_info_label.setVisible(False)
            self.candle_info_label.setText("")
        if self.cci_crosshair_v and self.cci_crosshair_v.isVisible():
            self.cci_crosshair_v.setVisible(False)
            self.cci_crosshair_h.setVisible(False)
            self.cci_info_label.setVisible(False)
            self.cci_info_label.setText("")

    def reset_chart_view(self):
        """Reset the chart view to automatically fit all data"""
        # 로그 스케일 모드 비활성화 - 항상 선형 스케일 사용
        self.plot_item.getViewBox().setLogMode(False, False)
        
        self.chart_widget.autoRange()
        if self.show_cci:
            self.cci_plot_item.autoRange()
        print(f"차트 뷰가 초기화되었습니다.")
        self.append_log("차트 뷰가 초기화되었습니다.")

    def toggle_auto_scale(self):
        """Toggle between auto-scale mode (visible candles only) and default scaling"""
        self.auto_scale_active = self.auto_scale_button.isChecked()
        
        if self.auto_scale_active:
            # Set button style to highlight active state
            self.auto_scale_button.setStyleSheet("""
                QPushButton {
                    background-color: #40A040;
                    color: white;
                    font-weight: bold;
                }
            """)
            self.apply_auto_scale()  # Apply immediately when activated
            print("오토스케일 활성화: 보이는 영역만 자동 조정됩니다.")
            self.append_log("오토스케일 활성화: 보이는 영역만 자동 조정됩니다.")
        else:
            # Reset button style
            self.auto_scale_button.setStyleSheet("")
            self.reset_chart_view()  # Reset to show all data when deactivated
            print("오토스케일 비활성화: 전체 데이터가 표시됩니다.")
            self.append_log("오토스케일 비활성화: 전체 데이터가 표시됩니다.")
    
    def on_range_changed(self, view_box, range_rect):
        """Called when the user pans or zooms the chart"""
        if self.auto_scale_active:
            # Use a timer to throttle updates when continuously panning/zooming
            if not self.auto_scale_timer.isActive():
                self.auto_scale_timer.start(200)  # Apply auto-scale after 200ms without panning/zooming
    
    def apply_auto_scale(self):
        """Apply auto-scale to adjust Y-axis to fit only the visible candles"""
        if not self.auto_scale_active or not self.candlestick_item or not self.detailed_candle_data:
            return
            
        view_box = self.plot_item.getViewBox()
        view_range = view_box.viewRange()
        
        # 로그 스케일 모드 설정 코드가 있다면 제거
        # 아래와 같이 로그 스케일 모드를 강제로 해제 (로그 스케일 기능 제거와 관련)
        view_box.setLogMode(False, False)  # 선형 스케일로 강제 설정 (x=False, y=False)
        
        # Get current visible X range (timestamps)
        x_min, x_max = view_range[0]
        
        # Find candles within this range
        visible_candles = [
            d for d in self.detailed_candle_data 
            if x_min <= d['time_axis_val'] <= x_max
        ]
        
        if not visible_candles:
            print("오토스케일: 보이는 영역에 데이터가 없습니다.")
            return
            
        # Find min and max prices in visible area
        min_price = min(min(d['low'] for d in visible_candles), min(d['open'] for d in visible_candles))
        max_price = max(max(d['high'] for d in visible_candles), max(d['close'] for d in visible_candles))
        
        # Add some padding (5% above and below)
        price_range = max_price - min_price
        min_price = min_price - price_range * 0.05
        max_price = max_price + price_range * 0.05
        
        # Set Y range to visible candles (keep X range unchanged)
        view_box.setYRange(min_price, max_price, padding=0)
        
        # Make sure current price line is visible if it's in the X range
        if (self.current_price_line and self.current_price_line.isVisible() and 
            min_price <= self.current_price_line.value() <= max_price):
            self.current_price_line.setValue(self.current_price_line.value())
            
        print(f"오토스케일 적용: 보이는 캔들 {len(visible_candles)}개에 맞게 Y축을 조정했습니다.")

    def toggle_bollinger(self):
        """볼린저 밴드 표시/숨김 토글"""
        self.show_bollinger = self.bollinger_button.isChecked()
        
        if self.show_bollinger:
            self.bollinger_button.setStyleSheet("""
                QPushButton {
                    background-color: #4080C0;
                    color: white;
                    font-weight: bold;
                }
            """)
            print("볼린저 밴드를 표시합니다.")
            self.append_log("볼린저 밴드를 표시합니다.")
            
            # 전에 보여진 적이 있는 경우, 현재 차트 범위 유지
            current_range = None
            if self.chart_widget:
                current_range = self.chart_widget.viewRange()
        else:
            self.bollinger_button.setStyleSheet("")
            print("볼린저 밴드를 숨깁니다.")
            self.append_log("볼린저 밴드를 숨깁니다.")
            
            # 볼린저 밴드 곡선 제거
            if self.bollinger_upper_curve:
                self.plot_item.removeItem(self.bollinger_upper_curve)
                self.bollinger_upper_curve = None
            if self.bollinger_middle_curve:
                self.plot_item.removeItem(self.bollinger_middle_curve)
                self.bollinger_middle_curve = None
            if self.bollinger_lower_curve:
                self.plot_item.removeItem(self.bollinger_lower_curve)
                self.bollinger_lower_curve = None
        
        # 데이터가 있으면 차트 다시 그리기
        if not self.data_df.empty:
            self.plot_data(auto_range=False)
            
        # 범위가 저장되어 있으면 원래 범위로 복원
        if self.show_bollinger and current_range:
            self.chart_widget.setRange(rect=QRectF(current_range[0][0], current_range[1][0], 
                                               current_range[0][1] - current_range[0][0], 
                                               current_range[1][1] - current_range[1][0]))
    
    def toggle_cci(self):
        """CCI 지표 표시/숨김 토글"""
        self.show_cci = self.cci_button.isChecked()
        
        # 현재 차트 범위 저장
        current_range = None
        if self.chart_widget:
            current_range = self.chart_widget.viewRange()
        
        # CCI 차트 위젯 표시/숨김
        self.cci_chart_widget.setVisible(self.show_cci)
        
        if self.show_cci:
            # 스플리터 사이즈 재조정 (메인:CCI = 3:1 비율)
            total_height = sum(self.chart_splitter.sizes())
            main_height = int(total_height * 0.75)
            cci_height = total_height - main_height
            self.chart_splitter.setSizes([main_height, cci_height])
            
            self.cci_button.setStyleSheet("""
                QPushButton {
                    background-color: #40A040;
                    color: white;
                    font-weight: bold;
                }
            """)
            print("CCI 지표를 표시합니다.")
            self.append_log("CCI 지표를 표시합니다.")
        else:
            self.cci_button.setStyleSheet("")
            print("CCI 지표를 숨깁니다.")
            self.append_log("CCI 지표를 숨깁니다.")
            
            # CCI 곡선 제거
            if self.cci_curve:
                self.cci_plot_item.removeItem(self.cci_curve)
                self.cci_curve = None
            # CCI 현재값 라인 제거
            if self.cci_current_line:
                self.cci_plot_item.removeItem(self.cci_current_line)
                self.cci_current_line = None
            # CCI 크로스헤어 숨기기
            if self.cci_crosshair_v and self.cci_crosshair_v.isVisible():
                self.cci_crosshair_v.setVisible(False)
                self.cci_crosshair_h.setVisible(False)
            # CCI 정보 라벨 숨기기
            if self.cci_info_label:
                self.cci_info_label.setVisible(False)
                self.cci_info_label.setText("")
            # CCI 데이터 초기화
            self.cci_data = []
            
            # 매매신호 마커 제거
            if hasattr(self, 'cci_buy_markers') and self.cci_buy_markers:
                for marker in self.cci_buy_markers:
                    self.plot_item.removeItem(marker)
                self.cci_buy_markers = []
            if hasattr(self, 'cci_sell_markers') and self.cci_sell_markers:
                for marker in self.cci_sell_markers:
                    self.plot_item.removeItem(marker)
                self.cci_sell_markers = []
        
        # 데이터가 있으면 차트 다시 그리기
        if not self.data_df.empty:
            self.plot_data(auto_range=False)
            
        # 범위가 저장되어 있으면 원래 범위로 복원
        if current_range:
            self.chart_widget.setRange(rect=QRectF(current_range[0][0], current_range[1][0], 
                                           current_range[0][1] - current_range[0][0], 
                                           current_range[1][1] - current_range[1][0]))

    def plot_indicators(self, df):
        """기술적 지표 계산 및 표시"""
        from utils import calculate_bollinger_bands, calculate_cci, detect_cci_signals
        
        # 볼린저 밴드 표시
        if self.show_bollinger and len(df) >= self.bollinger_window:
            # 기존 볼린저 밴드 제거
            if self.bollinger_upper_curve:
                self.plot_item.removeItem(self.bollinger_upper_curve)
            if self.bollinger_middle_curve:
                self.plot_item.removeItem(self.bollinger_middle_curve)
            if self.bollinger_lower_curve:
                self.plot_item.removeItem(self.bollinger_lower_curve)
                
            # 볼린저 밴드 계산
            middle_band, upper_band, lower_band = calculate_bollinger_bands(
                df, window=self.bollinger_window, num_std=self.bollinger_std
            )
            
            if middle_band is not None:
                # X값으로 timestamp 사용
                x_values = df['time_axis_val'].values
                
                # 중간 밴드 (SMA)
                self.bollinger_middle_curve = pg.PlotDataItem(
                    x_values, middle_band.values,
                    pen=pg.mkPen(color='w', width=1),
                    name="BB Middle"
                )
                self.plot_item.addItem(self.bollinger_middle_curve)
                
                # 상단 밴드
                self.bollinger_upper_curve = pg.PlotDataItem(
                    x_values, upper_band.values,
                    pen=pg.mkPen(color='b', width=1, style=Qt.PenStyle.DashLine),
                    name="BB Upper"
                )
                self.plot_item.addItem(self.bollinger_upper_curve)
                
                # 하단 밴드
                self.bollinger_lower_curve = pg.PlotDataItem(
                    x_values, lower_band.values,
                    pen=pg.mkPen(color='b', width=1, style=Qt.PenStyle.DashLine),
                    name="BB Lower"
                )
                self.plot_item.addItem(self.bollinger_lower_curve)
                
                print(f"볼린저 밴드 계산됨 (주기: {self.bollinger_window})")
        
        # CCI 지표 표시
        if self.show_cci and len(df) >= self.cci_window:
            # 기존 CCI 곡선 제거
            if self.cci_curve:
                self.cci_plot_item.removeItem(self.cci_curve)
                self.cci_curve = None
            # CCI 현재값 라인 제거
            if self.cci_current_line:
                self.cci_plot_item.removeItem(self.cci_current_line)
                self.cci_current_line = None
            
            # 기존 매매신호 마커 제거
            if hasattr(self, 'cci_buy_markers') and self.cci_buy_markers:
                for marker in self.cci_buy_markers:
                    self.plot_item.removeItem(marker)
            if hasattr(self, 'cci_sell_markers') and self.cci_sell_markers:
                for marker in self.cci_sell_markers:
                    self.plot_item.removeItem(marker)
            
            # 매매신호 마커 리스트 초기화
            self.cci_buy_markers = []
            self.cci_sell_markers = []
            
            # CCI 계산
            cci_values = calculate_cci(df, window=self.cci_window)
            
            if cci_values is not None:
                # X값으로 timestamp 사용
                x_values = df['time_axis_val'].values
                
                # CCI 데이터 저장 (mouse_moved_on_chart에서 사용하기 위함)
                self.cci_data = list(zip(x_values, cci_values.values))
                
                # CCI 곡선
                self.cci_curve = pg.PlotDataItem(
                    x_values, cci_values.values,
                    pen=pg.mkPen(color='y', width=1),
                    name="CCI"
                )
                self.cci_plot_item.addItem(self.cci_curve)
                
                # 0선 추가
                zero_line = pg.InfiniteLine(
                    pos=0, angle=0,
                    pen=pg.mkPen(color='w', width=1, style=Qt.PenStyle.DotLine)
                )
                self.cci_plot_item.addItem(zero_line)
                
                # +100, -100 선 추가 (CCI의 과매수/과매도 기준선)
                plus_100_line = pg.InfiniteLine(
                    pos=100, angle=0,
                    pen=pg.mkPen(color='r', width=1, style=Qt.PenStyle.DotLine)
                )
                minus_100_line = pg.InfiniteLine(
                    pos=-100, angle=0,
                    pen=pg.mkPen(color='g', width=1, style=Qt.PenStyle.DotLine)
                )
                self.cci_plot_item.addItem(plus_100_line)
                self.cci_plot_item.addItem(minus_100_line)
                
                # 매매신호 감지 및 표시
                df_with_signals = detect_cci_signals(df, cci_values)
                
                # 매수/매도 신호를 차트에 표시
                for idx, row in df_with_signals.iterrows():
                    if row['cci_buy_signal']:
                        # 매수 신호 (초록색 삼각형)
                        buy_marker = pg.ScatterPlotItem(
                            [row['time_axis_val']], [row['low'] * 0.999],  # 가격 약간 아래에 표시
                            symbol='t', size=10, pen=pg.mkPen(None), brush=pg.mkBrush('g')
                        )
                        self.plot_item.addItem(buy_marker)
                        self.cci_buy_markers.append(buy_marker)
                        
                    if row['cci_sell_signal']:
                        # 매도 신호 (빨간색 역삼각형)
                        sell_marker = pg.ScatterPlotItem(
                            [row['time_axis_val']], [row['high'] * 1.001],  # 가격 약간 위에 표시
                            symbol='t1', size=10, pen=pg.mkPen(None), brush=pg.mkBrush('r')
                        )
                        self.plot_item.addItem(sell_marker)
                        self.cci_sell_markers.append(sell_marker)
                
                # 현재 CCI 값 표시
                # 최신 데이터가 있는 경우 현재 CCI 값을 가져옴
                if len(cci_values) > 0:
                    latest_cci = cci_values.values[-1]
                    
                    # 기존 CCI 현재값 라인 제거
                    if self.cci_current_line:
                        self.cci_plot_item.removeItem(self.cci_current_line)
                    
                    # 새 CCI 현재값 라인 생성
                    self.cci_current_line = pg.InfiniteLine(
                        angle=0, 
                        movable=False, 
                        pen=pg.mkPen(QColor(0, 120, 255, 200), width=1, style=Qt.PenStyle.DashLine),
                        label=f'CCI: {latest_cci:.2f}',
                        labelOpts={
                            'position': 0.97, 
                            'color': (255, 255, 255),
                            'fill': (0, 120, 255, 150),
                            'anchor': (1, 0.5),
                            'movable': True 
                        }
                    )
                    self.cci_current_line.setPos(latest_cci)
                    self.cci_current_line.setVisible(True)
                    self.cci_plot_item.addItem(self.cci_current_line)
                    
                    # 최근 매매신호 확인
                    latest_idx = df_with_signals.index[-1]
                    if df_with_signals.loc[latest_idx, 'cci_buy_signal']:
                        self.append_log("🔼 CCI 매수 신호 발생!")
                    if df_with_signals.loc[latest_idx, 'cci_sell_signal']:
                        self.append_log("🔽 CCI 매도 신호 발생!")
                    
                    # 라벨의 Z값 설정 (다른 아이템보다 위에 표시)
                    if hasattr(self.cci_current_line, 'label') and isinstance(self.cci_current_line.label, pg.TextItem):
                        self.cci_current_line.label.setZValue(20)
                
                # CCI 스케일 자동 조정 - 처음 표시될 때만 또는 새 심볼/타임프레임 로드 시에만 적용
                if not hasattr(self, '_cci_scaled') or not self._cci_scaled.get(f"{self.symbol}_{self.timeframe}", False):
                    self.cci_plot_item.autoRange()
                    if not hasattr(self, '_cci_scaled'):
                        self._cci_scaled = {}
                    self._cci_scaled[f"{self.symbol}_{self.timeframe}"] = True
                
                print(f"CCI 지표 계산됨 (주기: {self.cci_window})")