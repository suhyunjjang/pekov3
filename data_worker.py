import ccxt # For initial REST load if ccxt.pro not used for it
import ccxt.pro as ccxtpro # For WebSocket
import asyncio
import threading
import pandas as pd
from PyQt6.QtCore import pyqtSignal, QObject, QThread
import traceback

# WorkerSignals class to emit signals from the WebSocket thread
class WorkerSignals(QObject):
    new_data = pyqtSignal(list)
    error = pyqtSignal(str)
    finished = pyqtSignal() # Ensure finished is defined once properly

class Worker(QObject):
    def __init__(self, exchange, symbol, timeframe):
        super().__init__()
        self.exchange = exchange # This is a ccxtpro exchange instance
        self.symbol = symbol
        self.timeframe = timeframe
        self.signals = WorkerSignals()
        self._is_running = False # Controlled by start_streaming and stop
        self.loop = None # asyncio event loop for this thread

    def start_streaming(self):
        self._is_running = True
        thread_id = threading.get_ident()
        print(f"Worker.start_streaming called for {self.symbol} in thread {thread_id}")
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.watch_ohlcv_loop_async())
        except Exception as e:
            # Catching broad Exception here to ensure any loop setup error is reported
            error_msg = f"Error in Worker.start_streaming for {self.symbol} in thread {thread_id}: {type(e).__name__} - {e}"
            print(error_msg)
            traceback.print_exc() # Print full traceback for debugging
            self.signals.error.emit(error_msg)
        finally:
            # This finally block executes after run_until_complete finishes or if an exception occurs in the try block.
            if self.loop and not self.loop.is_closed():
                print(f"Closing asyncio event loop for {self.symbol} in thread {thread_id} (start_streaming finally block).")
                self.loop.close()
                print(f"Asyncio event loop for {self.symbol} in thread {thread_id} closed.")
            
            # Crucially, emit 'finished' signal so QThread can be properly managed (quit, wait, deleteLater)
            print(f"Worker for {self.symbol} in thread {thread_id} emitting finished signal from start_streaming.")
            self.signals.finished.emit()

    async def watch_ohlcv_loop_async(self):
        thread_id = threading.get_ident()
        print(f"Starting watch_ohlcv_loop_async for {self.symbol} on {self.timeframe} in thread {thread_id}")
        try:
            if not self.exchange or not hasattr(self.exchange, 'watch_ohlcv'):
                error_msg = f"ccxtpro exchange object not initialized or does not support watch_ohlcv."
                print(f"ERROR: {error_msg}")
                self.signals.error.emit(error_msg)
                self._is_running = False # Ensure loop doesn't run
                return

            # Some ccxtpro exchanges might require markets to be loaded before watch_ohlcv
            # It's often handled implicitly, but explicit loading can be safer if issues arise.
            try:
                if hasattr(self.exchange, 'load_markets') and not self.exchange.markets:
                    print(f"Loading markets for {self.exchange.id} in worker thread...")
                    await self.exchange.load_markets()
                    print(f"Markets loaded for {self.exchange.id}.")
            except Exception as e:
                error_msg = f"Error loading markets in worker: {e}"
                print(f"ERROR: {error_msg}")
                self.signals.error.emit(error_msg)
                # Decide if this is fatal for the worker
                # self._is_running = False 
                # return

            while self._is_running:
                try:
                    # print(f"Awaiting watch_ohlcv for {self.symbol}...") # Debug
                    ohlcv_list = await self.exchange.watch_ohlcv(self.symbol, self.timeframe)
                    if self._is_running and ohlcv_list: 
                        # print(f"WebSocket ({self.symbol}): Received {len(ohlcv_list)} candle(s).")
                        self.signals.new_data.emit(ohlcv_list) 
                    elif self._is_running and not self.exchange.is_connected():
                        print(f"Exchange {self.exchange.id} is not connected for {self.symbol} in thread {thread_id}. Stopping worker.")
                        self.signals.error.emit(f"Exchange not connected for {self.symbol}")
                        self._is_running = False # Signal to stop
                        break 
                except asyncio.CancelledError:
                    print(f"watch_ohlcv_loop_async for {self.symbol} in thread {thread_id} was cancelled.")
                    self._is_running = False # Ensure loop terminates
                    break
                except ccxt.NetworkError as ne:
                    if self._is_running:
                        error_msg = f"NetworkError in watch_ohlcv_loop_async ({self.symbol}, thread {thread_id}): {ne}"
                        print(error_msg)
                        self.signals.error.emit(error_msg)
                        await asyncio.sleep(5) # Wait before retrying for network errors
                    else:
                        break
                except ccxt.ExchangeError as e:
                    if not self._is_running: break
                    error_msg = f"Exchange error in watch_ohlcv_loop_async ({self.symbol}): {e}"
                    print(f"WARNING: {error_msg}")
                    self.signals.error.emit(error_msg)
                    await asyncio.sleep(5)
                except Exception as e_inner:
                    if self._is_running: # Only emit error if we were supposed to be running
                        error_msg = f"Error in watch_ohlcv_loop_async ({self.symbol}, thread {thread_id}): {type(e_inner).__name__} - {e_inner}"
                        print(error_msg)
                        traceback.print_exc()
                        self.signals.error.emit(error_msg)
                        # Decide if we should break or continue after an error
                        # For some errors (e.g. network issues), a short sleep and continue might be fine.
                        # For others (e.g. symbol not found), we should break.
                        # For now, let's break on most errors to avoid flooding.
                        self._is_running = False # Stop on error
                    break # Exit while loop on error

        except Exception as e_outer:
            # This catches errors from initial setup, e.g., market loading
            if self._is_running:
                error_msg = f"Outer error in watch_ohlcv_loop_async ({self.symbol}, thread {thread_id}): {type(e_outer).__name__} - {e_outer}"
                print(error_msg)
                traceback.print_exc()
                self.signals.error.emit(error_msg)
                self._is_running = False # Ensure we stop if an outer error occurs
        finally:
            print(f"watch_ohlcv_loop_async for {self.symbol} in thread {thread_id} entering finally block. _is_running: {self._is_running}")
            try:
                # This check is important: exchange might be None or already closed by another path
                if hasattr(self.exchange, 'close') and callable(self.exchange.close):
                    print(f"Attempting to close exchange ({self.symbol}) from watch_ohlcv_loop_async finally block (thread {thread_id}).")
                    await self.exchange.close() # Ensure ccxt.pro cleans up its WebSocket
                    print(f"Exchange ({self.symbol}) closed successfully in watch_ohlcv_loop_async (thread {thread_id}).")
            except Exception as e_close:
                close_error_msg = f"Error closing exchange for {self.symbol} in watch_ohlcv_loop_async (thread {thread_id}): {type(e_close).__name__} - {e_close}"
                print(close_error_msg)
                traceback.print_exc()
                # Optionally emit this error, but be cautious about signals during shutdown
                # self.signals.error.emit(close_error_msg) # Avoid emitting error signal during shutdown if possible
            print(f"Exited watch_ohlcv_loop_async for {self.symbol} in thread {thread_id}.")

    def stop(self):
        thread_id = threading.get_ident()
        print(f"Worker.stop called for {self.symbol} in thread {thread_id}. Current _is_running: {self._is_running}")
        if self._is_running:
            self._is_running = False
            # The watch_ohlcv_loop_async will see _is_running as False and exit,
            # then its finally block will close the exchange.
            # The asyncio loop itself will be closed by start_streaming's finally block.
            print(f"_is_running set to False for {self.symbol} in thread {thread_id}. Loop should terminate gracefully.")
        else:
            print(f"Worker for {self.symbol} in thread {thread_id} was already stopped or not started.")
        # Note: Do not try to directly manipulate or stop self.loop here.
        # Let it finish naturally through run_until_complete in start_streaming.
        print(f"Worker.stop for {self.symbol} in thread {thread_id} finished processing flag.") 