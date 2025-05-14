"""
UI 관련 헬퍼 함수 및 유틸리티 클래스를 제공하는 모듈
"""

from PyQt6.QtCore import QRectF
from PyQt6.QtWidgets import QApplication, QMainWindow

def create_rect_from_range(x_range, y_range):
    """
    X/Y 범위에서 QRectF 생성
    
    Parameters:
    x_range (tuple): X 축 범위 (min, max)
    y_range (tuple): Y 축 범위 (min, max)
    
    Returns:
    QRectF: 지정된 범위에 해당하는 사각형
    """
    return QRectF(
        x_range[0], y_range[0],
        x_range[1] - x_range[0],
        y_range[1] - y_range[0]
    )

def format_ohlcv_info(candle_data):
    """
    OHLCV 데이터로부터 정보 텍스트 포맷팅
    
    Parameters:
    candle_data (dict): OHLCV 데이터가 포함된 딕셔너리
    
    Returns:
    str: 포맷팅된 OHLCV 정보 텍스트
    """
    if not candle_data:
        return ""
    
    info_text = f"Time: {candle_data['timestamp_display']}\n"
    info_text += f"O: {candle_data['open']:.4f}  H: {candle_data['high']:.4f}\n"
    info_text += f"L: {candle_data['low']:.4f}  C: {candle_data['close']:.4f}\n"
    info_text += f"V: {candle_data['volume']:.2f}"
    
    return info_text

def format_cci_info(timestamp_display, cci_value):
    """
    CCI 정보 텍스트 포맷팅
    
    Parameters:
    timestamp_display (str): 타임스탬프 표시 문자열
    cci_value (float): CCI 값
    
    Returns:
    str: 포맷팅된 CCI 정보 텍스트
    """
    if cci_value is None:
        return ""
    
    info_text = f"Time: {timestamp_display}\n"
    info_text += f"CCI: {cci_value:.2f}"
    
    return info_text 