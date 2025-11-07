from socket import socket, AF_INET, SOCK_STREAM

def get_free_port():
    with socket(AF_INET, SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

AVAILABLE_PORT = get_free_port()