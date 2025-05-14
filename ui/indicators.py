"""
기술적 지표(볼린저 밴드, CCI 등) 관련 기능을 제공하는 모듈
"""

import pyqtgraph as pg
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor

from utils.calculations import calculate_bollinger_bands, calculate_cci
from utils.signals import detect_cci_signals
from ui.styles import BOLLINGER_BUTTON_ACTIVE_STYLE, CCI_BUTTON_ACTIVE_STYLE

class IndicatorsMixin:
    """
    기술적 지표 관련 기능을 제공하는 Mixin 클래스
    볼린저 밴드, CCI 등의 지표 관리를 담당
    """
    
    def toggle_bollinger(self):
        """볼린저 밴드 표시/숨김 토글"""
        self.show_bollinger = self.bollinger_button.isChecked()
        
        if self.show_bollinger:
            self.bollinger_button.setStyleSheet(BOLLINGER_BUTTON_ACTIVE_STYLE)
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
            self.cci_button.setStyleSheet(CCI_BUTTON_ACTIVE_STYLE)
            print("CCI 지표를 표시합니다.")
            self.append_log("CCI 지표를 표시합니다.")
        else:
            self.cci_button.setStyleSheet("")
            print("CCI 지표를 숨깁니다.")
            self.append_log("CCI 지표를 숨깁니다.")
            
            # CCI 관련 요소 제거
            self.clear_cci_elements()
        
        # 데이터가 있으면 차트 다시 그리기
        if not self.data_df.empty:
            self.plot_data(auto_range=False)
            
        # 범위가 저장되어 있으면 원래 범위로 복원
        if current_range:
            self.chart_widget.setRange(rect=QRectF(current_range[0][0], current_range[1][0], 
                                       current_range[0][1] - current_range[0][0], 
                                       current_range[1][1] - current_range[1][0]))
    
    def clear_cci_elements(self):
        """CCI 관련 요소 제거"""
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
    
    def plot_indicators(self, df):
        """기술적 지표 계산 및 표시"""
        if self.show_bollinger:
            self.plot_bollinger_bands(df)
        
        if self.show_cci:
            self.plot_cci(df)
    
    def plot_bollinger_bands(self, df):
        """볼린저 밴드 계산 및 표시"""
        if len(df) < self.bollinger_window:
            return
            
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
    
    def plot_cci(self, df):
        """CCI 계산 및 표시"""
        if len(df) < self.cci_window:
            return
            
        # 기존 CCI 곡선 제거
        if self.cci_curve:
            self.cci_plot_item.removeItem(self.cci_curve)
            self.cci_curve = None
        # CCI 현재값 라인 제거
        if self.cci_current_line:
            self.cci_plot_item.removeItem(self.cci_current_line)
            self.cci_current_line = None
        
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
            
            # 현재 CCI 값 표시
            self.display_current_cci(df, cci_values)
            
            # CCI 스케일 자동 조정 - 처음 표시될 때만 또는 새 심볼/타임프레임 로드 시에만 적용
            self.update_cci_scale()
            
            print(f"CCI 지표 계산됨 (주기: {self.cci_window})")
    
    def display_current_cci(self, df, cci_values):
        """현재 CCI 값을 차트에 표시"""
        # 현재 CCI 값이 있는 경우에만 표시
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
            
            # 라벨의 Z값 설정 (다른 아이템보다 위에 표시)
            if hasattr(self.cci_current_line, 'label') and isinstance(self.cci_current_line.label, pg.TextItem):
                self.cci_current_line.label.setZValue(20)
    
    def update_cci_scale(self):
        """CCI 차트 스케일 업데이트"""
        if not hasattr(self, '_cci_scaled') or not self._cci_scaled.get(f"{self.symbol}_{self.timeframe}", False):
            self.cci_plot_item.autoRange()
            if not hasattr(self, '_cci_scaled'):
                self._cci_scaled = {}
            self._cci_scaled[f"{self.symbol}_{self.timeframe}"] = True 