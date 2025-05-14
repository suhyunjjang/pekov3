"""
커스텀 pyqtgraph 플롯 아이템(캔들스틱, 날짜 축 등)을 정의하는 모듈
"""

import pyqtgraph as pg
from PyQt6.QtCore import QRectF, QPointF
from PyQt6.QtGui import QPainter # QBrush, QPen are used via pg.mkBrush/mkPen
from datetime import datetime

# CandlestickItem class
class CandlestickItem(pg.GraphicsObject):
    # Timeframe seconds mapping
    TIMEFRAME_SECONDS = {
        '1m': 60,
        '3m': 180,
        '5m': 300,
        '15m': 900,
        '30m': 1800,
        '1h': 3600,
        '2h': 7200,
        '4h': 14400,
        '6h': 21600,
        '12h': 43200,
        '1d': 86400,
        '3d': 259200,
        '1w': 604800
    }
    
    def __init__(self, data, timeframe='1h'):
        super().__init__()
        self.data = data  # data is a list of dicts: {'time': t, 'open': o, 'high': h, 'low': l, 'close': c}
        self.timeframe = timeframe
        self.update_bar_width()  # Set bar_width_seconds based on timeframe
        self.generatePicture()
    
    def update_bar_width(self):
        """Calculate bar width in seconds based on timeframe"""
        tf_seconds = self.TIMEFRAME_SECONDS.get(self.timeframe, 3600)  # Default to 1h if unknown
        self.bar_width_seconds = tf_seconds * 0.7  # 70% of timeframe period
        return self.bar_width_seconds
    
    def update_timeframe(self, timeframe):
        """Update the timeframe and recalculate bar width"""
        if timeframe != self.timeframe:
            self.timeframe = timeframe
            self.update_bar_width()
            if self.data:  # Only regenerate if we have data
                self.generatePicture()
                self.prepareGeometryChange()
                self.update()
            return True
        return False

    def generatePicture(self):
        picture = pg.QtGui.QPicture()
        p = pg.QtGui.QPainter(picture)
        p.setPen(pg.mkPen('w')) # Default pen for outlines

        if not self.data:
            p.end()
            self.picture = picture
            return

        for d in self.data:
            time_val = d['time'] # Use actual timestamp for x-coordinate
            open_price = d['open']
            high_price = d['high']
            low_price = d['low']
            close_price = d['close']

            # Draw wick (high-low line)
            p.drawLine(QPointF(time_val, low_price), QPointF(time_val, high_price))

            # Draw body (open-close rectangle)
            if open_price < close_price: # Bullish candle
                p.setBrush(pg.mkBrush('g'))
            else: # Bearish candle
                p.setBrush(pg.mkBrush('r'))
            
            body_top = max(open_price, close_price)
            body_bottom = min(open_price, close_price)
            p.drawRect(QRectF(time_val - self.bar_width_seconds / 2, body_bottom, self.bar_width_seconds, body_top - body_bottom))
        
        p.end()
        self.picture = picture

    def paint(self, painter, option, widget=None):
        self.picture.play(painter)

    def boundingRect(self):
        if not self.data:
            return QRectF()
        
        # Ensure data is not empty before trying to access min/max
        if not all(isinstance(d, dict) and all(k in d for k in ('time', 'low', 'high')) for d in self.data):
            # print("Warning: CandlestickItem.boundingRect received malformed data.") # Debugging
            return QRectF() # Return empty if data is malformed or not ready
        
        try:
            min_time = min(d['time'] for d in self.data)
            max_time = max(d['time'] for d in self.data)
            min_low = min(d['low'] for d in self.data)
            max_high = max(d['high'] for d in self.data)
        except (ValueError, TypeError) as e: # Handle cases where data might be temporarily empty or invalid
            # print(f"Warning: CandlestickItem.boundingRect error during min/max: {e}") # Debugging
            return QRectF()

        return QRectF(min_time - self.bar_width_seconds / 2, min_low, 
                      max_time - min_time + self.bar_width_seconds, max_high - min_low)

    def setData(self, data):
        self.data = data
        self.generatePicture()
        self.prepareGeometryChange() # Important for QGraphicsObject when bounds change
        self.update() # Triggers a repaint

# DateAxisItem class
class DateAxisItem(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setLabel(text='Time', units=None)
        self.enableAutoSIPrefix(False)

    def tickStrings(self, values, scale, spacing):
        strings = []
        for v_int in values:
            v = float(v_int) 
            try:
                dt = datetime.fromtimestamp(v)
                strings.append(dt.strftime('%Y-%m-%d\n%H:%M:%S'))
            except Exception as e:
                strings.append('') 
        return strings 