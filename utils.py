from PyQt6.QtCore import QObject, pyqtSignal
import sys
import pandas as pd
import numpy as np

# Stream class to redirect stdout/stderr to a PyQt signal
class Stream(QObject):
    new_text = pyqtSignal(str)

    def __init__(self, original_stream=None):
        super().__init__()
        self.original_stream = original_stream

    def write(self, text):
        if self.original_stream:
            try:
                self.original_stream.write(text)
                self.original_stream.flush() # Ensure it's written immediately to terminal
            except Exception as e:
                # If original stream writing fails (e.g., if it was closed),
                # try to report this to sys.__stderr__ directly once.
                # This is a failsafe and might not always work if __stderr__ itself is problematic.
                if not hasattr(self, '_original_stream_error_reported'):
                    sys.__stderr__.write(f"Stream: Error writing to original_stream: {e}\n")
                    self._original_stream_error_reported = True
        self.new_text.emit(str(text))

    def flush(self):
        if self.original_stream:
            try:
                self.original_stream.flush()
            except Exception:
                pass # Ignore flush errors on original stream if write worked
        # The new_text signal is for the GUI, which handles its own display updates.
        # No separate flush needed for the signal emission part. 

def calculate_bollinger_bands(df, window=20, num_std=2):
    """
    볼린저 밴드 계산
    
    Parameters:
    df (pandas.DataFrame): 'close' 컬럼이 있는 DataFrame
    window (int): 이동 평균 기간
    num_std (float): 표준편차 승수
    
    Returns:
    tuple: (중간 밴드, 상단 밴드, 하단 밴드) - 각각 시리즈 형태
    """
    if df.empty or 'close' not in df.columns:
        return None, None, None
        
    # 종가 데이터로 이동 평균 계산
    middle_band = df['close'].rolling(window=window).mean()
    
    # 종가의 표준편차 계산
    std_dev = df['close'].rolling(window=window).std()
    
    # 상단 밴드 = 중간 밴드 + (표준편차 * num_std)
    upper_band = middle_band + (std_dev * num_std)
    
    # 하단 밴드 = 중간 밴드 - (표준편차 * num_std)
    lower_band = middle_band - (std_dev * num_std)
    
    return middle_band, upper_band, lower_band

def calculate_cci(df, window=20):
    """
    CCI(Commodity Channel Index) 계산
    
    Parameters:
    df (pandas.DataFrame): 'high', 'low', 'close' 컬럼이 있는 DataFrame
    window (int): CCI 계산 기간
    
    Returns:
    pandas.Series: CCI 값
    """
    if df.empty or 'high' not in df.columns or 'low' not in df.columns or 'close' not in df.columns:
        return None
    
    # Typical Price 계산 (TP = (high + low + close) / 3)
    df['tp'] = (df['high'] + df['low'] + df['close']) / 3
    
    # TP의 이동 평균
    ma_tp = df['tp'].rolling(window=window).mean()
    
    # TP와 MA 간의 편차 계산
    deviation = df['tp'] - ma_tp
    
    # 평균 편차 계산
    mean_deviation = np.abs(deviation).rolling(window=window).mean()
    
    # CCI 계산: CCI = (TP - SMA(TP)) / (0.015 * 평균편차)
    # 0으로 나누는 오류를 방지하기 위한 처리 추가
    cci = np.where(mean_deviation != 0, deviation / (0.015 * mean_deviation), 0)
    
    return pd.Series(cci, index=df.index) 