import logging
import socket
import struct
from config import Config

logger = logging.getLogger(__name__)


class TCPSender:
    """TCP file sender with proper binary protocol."""

    def __init__(self, receiver_ip: str, receiver_port: int = None):
        self.receiver_ip = receiver_ip
        self.receiver_port = receiver_port or Config.TCP_PORT
        self.buffer_size = Config.BUFFER_SIZE

    def send_file(self, filename: str, file_data: bytes) -> dict:
        """Send file data to receiver via TCP.

        Protocol:
        - 4 bytes: filename length (big-endian unsigned int)
        - N bytes: filename (UTF-8)
        - 8 bytes: file size (big-endian unsigned long)
        - M bytes: file content (in chunks)
        """
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)
            sock.connect((self.receiver_ip, self.receiver_port))

            # Send filename
            filename_bytes = filename.encode('utf-8')
            sock.sendall(struct.pack('!I', len(filename_bytes)))
            sock.sendall(filename_bytes)

            # Send file size
            file_size = len(file_data)
            sock.sendall(struct.pack('!Q', file_size))

            # Send file content in chunks
            sent = 0
            while sent < file_size:
                chunk = file_data[sent:sent + self.buffer_size]
                sock.sendall(chunk)
                sent += len(chunk)

            logger.info(f"File sent: {filename} ({file_size} bytes) to {self.receiver_ip}:{self.receiver_port}")

            return {
                'success': True,
                'filename': filename,
                'size': file_size,
                'receiver': f"{self.receiver_ip}:{self.receiver_port}"
            }

        except socket.timeout:
            logger.error(f"TCP send timeout to {self.receiver_ip}:{self.receiver_port}")
            return {'success': False, 'error': 'Connection timed out'}
        except ConnectionRefusedError:
            logger.error(f"TCP connection refused by {self.receiver_ip}:{self.receiver_port}")
            return {'success': False, 'error': 'Connection refused. Is the receiver running?'}
        except Exception as e:
            logger.error(f"TCP send error: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            if sock:
                sock.close()
