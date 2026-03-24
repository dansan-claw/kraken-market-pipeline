#!/bin/bash
# Market Data Collector Startup Script
# Usage: ./start_collector.sh [start|stop|status|restart]

APP_DIR="${APP_DIR:-$(dirname $0)}"
PID_FILE="$APP_DIR/collector.pid"
LOG_FILE="$APP_DIR/collector.log"

start() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "Collector is already running (PID: $(cat $PID_FILE))"
        return 1
    fi
    
    echo "Starting market data collector..."
    cd "$APP_DIR"
    nohup python3 collector.py > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Collector started (PID: $!)"
    echo "Logs: $LOG_FILE"
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Collector is not running"
        return 1
    fi
    
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping collector (PID: $PID)..."
        kill "$PID"
        rm -f "$PID_FILE"
        echo "Collector stopped"
    else
        echo "Process not found, cleaning up..."
        rm -f "$PID_FILE"
    fi
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "Collector is running (PID: $(cat $PID_FILE))"
        echo "Recent log entries:"
        tail -5 "$LOG_FILE" 2>/dev/null || echo "No log file yet"
    else
        echo "Collector is not running"
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 2
        start
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
