import logging
import os
import socket
import struct
import threading
import uuid
from config import Config

logger = logging.getLogger(__name__)


class TCPReceiver:
    """TCP file receiver with proper error handling and progress tracking."""

    def __init__(self, socketio=None):
        self.host = '0.0.0.0'
        self.port = Config.TCP_PORT
        self.buffer_size = Config.BUFFER_SIZE
        self.server_socket = None
        self.running = False
        self.socketio = socketio

    def start(self):
        """Start TCP receiver in a background thread."""
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        logger.info(f"TCP Receiver started on port {self.port}")

    def _run(self):
        """Main receiver loop."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True

            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    logger.info(f"Incoming TCP connection from {address}")

                    handler = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, address),
                        daemon=True
                    )
                    handler.start()

                except socket.error as e:
                    if self.running:
                        logger.error(f"TCP accept error: {e}")
                    break

        except Exception as e:
            logger.error(f"TCP Receiver error: {e}")
        finally:
            self.stop()

    def _handle_client(self, client_socket, address):
        """Handle incoming file transfer from a single client."""
        transfer_id = str(uuid.uuid4())[:8]

        try:
            # Receive filename length (4 bytes) + filename
            filename_len_bytes = client_socket.recv(4)
            if len(filename_len_bytes) < 4:
                raise ValueError("Invalid filename header")

            filename_len = struct.unpack('!I', filename_len_bytes)[0]
            filename = client_socket.recv(filename_len).decode('utf-8')

            # Receive file size (8 bytes)
            filesize_bytes = client_socket.recv(8)
            if len(filesize_bytes) < 8:
                raise ValueError("Invalid filesize header")

            file_size = struct.unpack('!Q', filesize_bytes)[0]

            logger.info(f"Receiving: {filename} ({file_size} bytes) from {address}")

            # Notify via SocketIO
            if self.socketio:
                self.socketio.emit('transfer_started', {
                    'filename': filename,
                    'size': file_size,
                    'source': f"{address[0]}:{address[1]}",
                    'transfer_id': transfer_id
                })

            # Receive all bytes into memory first
            os.makedirs(Config.DOWNLOAD_FOLDER, exist_ok=True)
            received = 0
            chunks = []
            while received < file_size:
                chunk_size = min(self.buffer_size, file_size - received)
                data = client_socket.recv(chunk_size)
                if not data:
                    break
                chunks.append(data)
                received += len(data)

                if self.socketio and file_size > 0:
                    progress = round((received / file_size) * 100, 1)
                    self.socketio.emit('transfer_progress', {
                        'transfer_id': transfer_id,
                        'filename': filename,
                        'progress': progress,
                        'received': received,
                        'total': file_size,
                    })

            file_bytes = b''.join(chunks)

            # Save to MinIO (LAN replica) if available, else fallback to disk
            try:
                from services.storage_service import get_storage_service
                storage = get_storage_service()
                if storage.minio:
                    storage._put_object(
                        storage.minio, storage.minio_bucket,
                        f"lan/{filename}", file_bytes,
                        'application/octet-stream', filename
                    )
                    logger.info(f"TCP file saved to MinIO: lan/{filename}")
                else:
                    raise RuntimeError("MinIO not available")
            except Exception:
                # Fallback: save to disk
                save_path = os.path.join(Config.DOWNLOAD_FOLDER, filename)
                with open(save_path, 'wb') as f:
                    f.write(file_bytes)
                logger.info(f"TCP file saved to disk: {save_path}")

            success = received == file_size

            if self.socketio:
                self.socketio.emit('transfer_complete', {
                    'filename': filename,
                    'success': success,
                    'transfer_id': transfer_id
                })

            logger.info(f"Transfer {'complete' if success else 'incomplete'}: {filename} ({received}/{file_size} bytes)")

        except Exception as e:
            logger.error(f"TCP transfer error from {address}: {e}")
            if self.socketio:
                self.socketio.emit('transfer_complete', {
                    'filename': 'unknown',
                    'success': False,
                    'error': str(e),
                    'transfer_id': transfer_id
                })
        finally:
            client_socket.close()

    def stop(self):
        """Stop the TCP receiver."""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        logger.info("TCP Receiver stopped")
