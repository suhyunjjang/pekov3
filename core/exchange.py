"""
거래소 연결 및 데이터 요청을 관리하는 모듈
"""

import ccxt
import ccxt.pro as ccxtpro
import traceback
import pandas as pd
from config.settings import DEFAULT_EXCHANGE_ID

class ExchangeManager:
    """
    거래소 연결 및 데이터 요청을 관리하는 클래스
    REST API 및 WebSocket 연결을 모두 처리
    """
    
    def __init__(self, exchange_id=DEFAULT_EXCHANGE_ID):
        self.exchange_id = exchange_id
        self.rest_exchange = None
        self.ws_exchange = None
        self.init_exchanges()
    
    def init_exchanges(self):
        """REST 및 WebSocket 거래소 객체 초기화"""
        # REST API 거래소 초기화
        try:
            rest_exchange_class = getattr(ccxt, self.exchange_id)
            self.rest_exchange = rest_exchange_class({
                'options': { 'defaultType': 'future', },
            })
            self.rest_exchange.load_markets()
            print(f"ccxt: Successfully initialized '{self.exchange_id}' for REST API.")
        except AttributeError:
            print(f"ERROR: ccxt: Exchange ID '{self.exchange_id}' not found in ccxt.")
            self.rest_exchange = None
        except Exception as e:
            print(f"ERROR: ccxt: Failed to initialize '{self.exchange_id}' for REST API: {e}")
            self.rest_exchange = None

        # WebSocket 거래소 초기화
        try:
            print(f"Attempting to initialize ccxtpro.{self.exchange_id} with options for USDⓈ-M futures.")
            self.ws_exchange = getattr(ccxtpro, self.exchange_id)({
                'options': {
                    'defaultType': 'future',  # For USDⓈ-M futures markets
                },
            })
            print(f"ccxtpro: Successfully initialized ccxtpro.{self.exchange_id} with 'future' defaultType for WebSocket.")
        except AttributeError as e_attr:
            print(f"ERROR: ccxtpro: Attribute error during initialization (ccxtpro.{self.exchange_id}): {e_attr}")
            self.ws_exchange = None
        except Exception as e:
            print(f"ERROR: ccxtpro: General exception during initialization: {e}")
            traceback.print_exc()
            self.ws_exchange = None
    
    def fetch_ohlcv(self, symbol, timeframe, limit=500):
        """REST API를 사용하여 OHLCV 데이터 가져오기"""
        if not self.rest_exchange:
            print("ERROR: REST exchange not initialized for fetch_ohlcv.")
            return None
        
        try:
            ohlcv = self.rest_exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if ohlcv:
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col])
                
                return df.sort_values(by='timestamp').reset_index(drop=True)
            else:
                print("No data received from REST API.")
                return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        except Exception as e:
            print(f"Error fetching OHLCV data from REST API: {e}")
            traceback.print_exc()
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    def create_ws_exchange(self):
        """새로운 WebSocket 거래소 인스턴스 생성"""
        try:
            return getattr(ccxtpro, self.exchange_id)({
                'options': {
                    'defaultType': 'future',  # For USDⓈ-M futures markets
                },
            })
        except Exception as e:
            print(f"ERROR: Failed to create new ccxt.pro exchange: {e}")
            traceback.print_exc()
            return None
    
    def get_supported_symbols(self):
        """지원되는 심볼 목록 반환"""
        # 기본 심볼 목록만 반환
        default_symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'SOL/USDT']
        return default_symbols 