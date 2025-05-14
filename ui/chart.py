"""
차트 관련 기능 및 클래스를 제공하는 모듈
"""

import pyqtgraph as pg
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QColor
import pandas as pd
from plotting.custom_plot_items import CandlestickItem, DateAxisItem
from ui.helpers import create_rect_from_range

class ChartMixin:
    """
    차트 관련 기능을 제공하는 Mixin 클래스
    주 차트와 CCI 차트의 초기화 및 관리를 담당
    """
    
    def init_charts(self):
        """차트 초기화"""
        # 메인 차트와 CCI 차트를 담을 스플리터 생성
        self.chart_splitter = self.create_chart_splitter()
        
        # 메인 차트와 CCI 차트를 위한 개별 위젯 생성
        self.main_chart_widget = pg.GraphicsLayoutWidget()
        self.cci_chart_widget = pg.GraphicsLayoutWidget()
        
        # 스플리터에 차트 위젯 추가
        self.chart_splitter.addWidget(self.main_chart_widget)
        self.chart_splitter.addWidget(self.cci_chart_widget)
        
        # 스플리터 사이즈 비율 설정 (메인 차트 : CCI 차트 = 3:1)
        self.update_chart_splitter_sizes()
        
        # CCI 차트는 기본적으로 표시
        self.cci_chart_widget.setVisible(self.show_cci)
        
        # 메인 캔들차트와 볼린저밴드를 표시할 윗 영역
        self.date_axis = DateAxisItem(orientation='bottom')
        self.chart_widget = self.main_chart_widget.addPlot(row=0, col=0, axisItems={'bottom': self.date_axis})
        self.plot_item = self.chart_widget
        
        # CCI 지표를 위한 아래 위젯
        self.cci_date_axis = DateAxisItem(orientation='bottom')
        self.cci_plot_item = self.cci_chart_widget.addPlot(row=0, col=0, axisItems={'bottom': self.cci_date_axis})
        
        # 차트 간 X축 동기화
        self.cci_plot_item.setXLink(self.chart_widget)  # CCI가 메인 차트와 X축을 공유
        
        self.setup_main_chart()
        self.setup_cci_chart()
        self.setup_crosshairs()
        self.setup_price_line()
        
        # Setup auto-scale functionality
        self.auto_scale_active = False
        self.auto_scale_timer = pg.QtCore.QTimer()
        self.auto_scale_timer.setSingleShot(True)
        self.auto_scale_timer.timeout.connect(self.apply_auto_scale)
        
        # Connect ViewBox range change signals
        view_box = self.plot_item.getViewBox()
        view_box.sigRangeChanged.connect(self.on_range_changed)
        
        # Set up candle info label
        self.setup_candle_info_label(view_box)
        
        # Connect mouse signals - 메인 차트와 CCI 차트 모두 연결
        self.main_chart_widget.scene().sigMouseMoved.connect(self.mouse_moved_on_chart)
        self.cci_chart_widget.scene().sigMouseMoved.connect(self.mouse_moved_on_chart)
    
    def create_chart_splitter(self):
        """차트 스플리터 생성"""
        return pg.QtWidgets.QSplitter(Qt.Orientation.Vertical)
    
    def update_chart_splitter_sizes(self):
        """차트 스플리터 크기 비율 업데이트"""
        total_height = 400  # 예상 총 높이 (실제 값은 나중에 조정됨)
        main_height = int(total_height * 0.75)
        cci_height = total_height - main_height
        self.chart_splitter.setSizes([main_height, cci_height])
    
    def setup_main_chart(self):
        """메인 차트 설정"""
        # 메인 차트 설정
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)

        # Configure axes
        self.plot_item.hideAxis('left')
        self.plot_item.showAxis('right')
        right_axis = self.plot_item.getAxis('right')
        right_axis.setLabel(text='Price', units='USDT')
        right_axis.enableAutoSIPrefix(False) # Disable SI prefix for price axis
        
        # 로그 스케일 모드 비활성화 - 항상 선형 스케일 사용
        self.plot_item.getViewBox().setLogMode(False, False)
        
        self.candlestick_item = None
    
    def setup_cci_chart(self):
        """CCI 차트 설정"""
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
        if hasattr(self, 'cci_info_label'):
            self.cci_info_label.setParentItem(cci_view_box)
            self.cci_info_label.anchor(itemPos=(0,1), parentPos=(0,1), offset=(5, 5))
    
    def setup_crosshairs(self):
        """크로스헤어 설정"""
        # 메인 차트에 크로스헤어 추가
        self.plot_item.addItem(self.crosshair_v, ignoreBounds=True)
        self.plot_item.addItem(self.crosshair_h, ignoreBounds=True)
        
        # CCI 차트에 크로스헤어 추가
        self.cci_plot_item.addItem(self.cci_crosshair_v, ignoreBounds=True)
        self.cci_plot_item.addItem(self.cci_crosshair_h, ignoreBounds=True)
    
    def setup_price_line(self):
        """현재 가격 라인 설정"""
        self.plot_item.addItem(self.current_price_line, ignoreBounds=True)
    
    def setup_candle_info_label(self, view_box):
        """캔들 정보 라벨 설정"""
        self.candle_info_label.setParentItem(view_box)
        # Anchor top-left of label (itemPos=(0,1)) to top-left of ViewBox (parentPos=(0,1))
        # offset by (5 pixels right, 5 pixels down from top edge) to position slightly inside
        self.candle_info_label.anchor(itemPos=(0,1), parentPos=(0,1), offset=(5, 5)) 
    
    def plot_data(self, auto_range=False):
        """데이터를 차트에 표시"""
        if self.data_df.empty:
            print("No data to plot.")
            if self.candlestick_item:
                self.candlestick_item.setData([])
            self.detailed_candle_data = [] # Clear detailed data too
            # Hide any info labels
            self.hide_chart_elements()
            
            # Only auto range if specifically requested, even if empty
            if auto_range:
                self.chart_widget.autoRange()
                print(f"Chart auto-ranged (empty chart).")
            return

        plot_df_copy = self.data_df.copy()
        
        # Ensure 'timestamp' is datetime
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
    
    def hide_chart_elements(self):
        """차트 요소 숨기기 (데이터가 없을 때)"""
        if self.candle_info_label: self.candle_info_label.setVisible(False) 
        if self.current_price_line: self.current_price_line.setVisible(False)
        if self.cci_info_label: self.cci_info_label.setVisible(False)
        
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