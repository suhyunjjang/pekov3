"""
기술적 지표 기반 매매신호 감지 함수를 제공하는 모듈

현재 애플리케이션에서는 매매 신호 기능이 비활성화되어 있으며,
이 모듈의 함수들은 나중에 매매 신호 기능을 구현할 때 사용될 예정입니다.
"""

import pandas as pd

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