"""
SSE Handler - Quản lý Server-Sent Events cho realtime updates
"""
import queue
import threading

# Queue để chứa events
_event_queue = queue.Queue()
_lock = threading.Lock()

def broadcast_event(event_type, data):
    """
    Broadcast event tới tất cả SSE clients
    
    Args:
        event_type: "fire" hoặc "safe"
        data: dict chứa thông tin (có thể None)
    """
    try:
        _event_queue.put({
            'type': event_type,
            'data': data
        })
        print(f"📡 SSE Broadcast: {event_type}")
    except Exception as e:
        print(f"❌ SSE Broadcast failed: {e}")

def get_event_stream():
    """
    Generator function cho SSE stream
    Yield events khi có state changes
    """
    # Send initial heartbeat
    yield f"data: safe\n\n"
    
    while True:
        try:
            # Đợi event mới (blocking với timeout)
            event = _event_queue.get(timeout=30)
            
            # Format SSE message
            event_type = event.get('type', 'safe')
            yield f"data: {event_type}\n\n"
            
        except queue.Empty:
            # Heartbeat mỗi 30s để giữ connection
            yield f": heartbeat\n\n"
        except Exception as e:
            print(f"⚠️ SSE stream error: {e}")
            break