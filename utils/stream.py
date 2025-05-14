"""
콘솔 출력 리디렉션을 위한 스트림 클래스를 정의하는 모듈
"""

from PyQt6.QtCore import QObject, pyqtSignal
import sys
from datetime import datetime

class Stream(QObject):
    """콘솔 출력(stdout/stderr)을 PyQt 신호로 리디렉션하는 클래스"""
    new_text = pyqtSignal(str)
    
    # 연속된 줄바꿈 감지를 위한 클래스 변수
    _last_was_newline = False

    def __init__(self, original_stream=None):
        super().__init__()
        self.original_stream = original_stream
        self._last_was_newline = False  # 각 인스턴스별 초기화

    def write(self, text):
        if self.original_stream:
            try:
                self.original_stream.write(text)
                self.original_stream.flush()  # 터미널에 즉시 출력
            except Exception as e:
                # 원본 스트림 쓰기 에러 시 한 번만 보고
                if not hasattr(self, '_original_stream_error_reported'):
                    sys.__stderr__.write(f"Stream: Error writing to original_stream: {e}\n")
                    self._original_stream_error_reported = True
        
        # 빈 텍스트는 무시
        if not text:
            return
            
        # 줄바꿈 문자만 있는지 확인
        only_newlines = all(c == '\n' for c in text)
        
        # 연속된 줄바꿈 줄이기
        if only_newlines and self._last_was_newline and '\n' in text:
            # 연속 줄바꿈의 경우 한 번의 줄바꿈만 허용
            text = '\n'
            
        self._last_was_newline = text.endswith('\n')
        
        # 실제 내용이 있는 경우 타임스탬프 추가
        if text.strip():
            timestamp = datetime.now().strftime('[%Y-%m-%d %H:%M:%S] ')
            
            # 줄바꿈으로 시작하는 경우, 타임스탬프를 첫 줄바꿈 이후에 추가
            if text.startswith('\n'):
                text = '\n' + timestamp + text[1:]
            else:
                text = timestamp + text
                
        # UI로 텍스트 전송
        self.new_text.emit(text)

    def flush(self):
        if self.original_stream:
            try:
                self.original_stream.flush()
            except Exception:
                pass  # 원본 스트림 플러시 에러는 무시
        # The new_text signal is for the GUI, which handles its own display updates.
        # No separate flush needed for the signal emission part. 