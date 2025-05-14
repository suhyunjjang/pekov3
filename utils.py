from PyQt6.QtCore import QObject, pyqtSignal
import sys

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