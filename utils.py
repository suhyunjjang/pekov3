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
    
    # 평균 편차 계산 - 트레이딩뷰의 ta.dev() 함수와 동일하게 구현
    # 트레이딩뷰 ta.dev() 함수는 평균으로부터의 절대 편차의 평균을 계산
    mean_deviation = df['tp'].rolling(window=window).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
    
    # CCI 계산: CCI = (TP - SMA(TP)) / (0.015 * 평균편차)
    # 0으로 나누는 오류를 방지하기 위한 처리 추가
    cci = np.where(mean_deviation != 0, deviation / (0.015 * mean_deviation), 0)
    
    return pd.Series(cci, index=df.index)

def detect_cci_signals(df, cci_values, overbought=100, oversold=-100):
    """
    CCI 지표 기반 매매신호 감지
    
    Parameters:
    df (pandas.DataFrame): 가격 데이터가 포함된 DataFrame
    cci_values (pandas.Series): calculate_cci()로 계산된 CCI 값
    overbought (float): 과매수 기준값 (기본값: 100)
    oversold (float): 과매도 기준값 (기본값: -100)
    
    Returns:
    pandas.DataFrame: 매매신호가 포함된 DataFrame
    """
    if df.empty or cci_values is None:
        return df
    
    # DataFrame에 CCI 값 추가
    df_with_signals = df.copy()
    df_with_signals['cci'] = cci_values
    
    # 신호 초기화
    df_with_signals['cci_buy_signal'] = False
    df_with_signals['cci_sell_signal'] = False
    
    # 과매수/과매도 영역 신호
    for i in range(1, len(df_with_signals)):
        # 과매도 영역에서 올라오는 경우 (매수 신호)
        if df_with_signals['cci'].iloc[i-1] < oversold and df_with_signals['cci'].iloc[i] > oversold:
            df_with_signals.loc[df_with_signals.index[i], 'cci_buy_signal'] = True
        
        # 과매수 영역에서 내려오는 경우 (매도 신호)
        if df_with_signals['cci'].iloc[i-1] > overbought and df_with_signals['cci'].iloc[i] < overbought:
            df_with_signals.loc[df_with_signals.index[i], 'cci_sell_signal'] = True
    
    # 0선 돌파 신호
    for i in range(1, len(df_with_signals)):
        # 아래에서 위로 0선 돌파 (매수 신호)
        if df_with_signals['cci'].iloc[i-1] < 0 and df_with_signals['cci'].iloc[i] > 0:
            df_with_signals.loc[df_with_signals.index[i], 'cci_buy_signal'] = True
        
        # 위에서 아래로 0선 돌파 (매도 신호)
        if df_with_signals['cci'].iloc[i-1] > 0 and df_with_signals['cci'].iloc[i] < 0:
            df_with_signals.loc[df_with_signals.index[i], 'cci_sell_signal'] = True
    
    return df_with_signals 