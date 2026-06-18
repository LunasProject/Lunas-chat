import argparse
import base64
import os
import socket
import struct
import sys
import threading
from dataclasses import dataclass
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


DEFAULT_PORT = 5555
MAX_MESSAGE_SIZE = 1024 * 1024


class Style:
    def __init__(self) -> None:
        self.enabled = supports_color()
        self.reset = "\033[0m" if self.enabled else ""
        self.bold = "\033[1m" if self.enabled else ""
        self.dim = "\033[2m" if self.enabled else ""
        self.cyan = "\033[36m" if self.enabled else ""
        self.green = "\033[32m" if self.enabled else ""
        self.yellow = "\033[33m" if self.enabled else ""
        self.red = "\033[31m" if self.enabled else ""


@dataclass
class ChatConfig:
    mode: str
    port: int
    nickname: str
    host: Optional[str] = None
    key: Optional[bytes] = None


def supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


STYLE = Style()


def line() -> str:
    return f"{STYLE.dim}{'-' * 56}{STYLE.reset}"


def info(message: str) -> None:
    print(f"{STYLE.cyan}[*]{STYLE.reset} {message}")


def success(message: str) -> None:
    print(f"{STYLE.green}[+]{STYLE.reset} {message}")


def warning(message: str) -> None:
    print(f"{STYLE.yellow}[!]{STYLE.reset} {message}")


def error(message: str) -> None:
    print(f"{STYLE.red}[x]{STYLE.reset} {message}")


def get_local_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(("10.255.255.255", 1))
            return sock.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def validate_port(port: int) -> int:
    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535.")
    return port


def parse_key(key_text: str) -> bytes:
    key = key_text.strip().encode("utf-8")
    try:
        decoded = base64.urlsafe_b64decode(key)
    except Exception as exc:
        raise ValueError("The key is not valid base64.") from exc

    if len(decoded) != 32:
        raise ValueError("The key must be a valid Fernet key.")

    Fernet(key)
    return key


def recv_exact(conn: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = conn.recv(size - len(chunks))
        if not chunk:
            raise ConnectionError("The remote peer closed the connection.")
        chunks.extend(chunk)
    return bytes(chunks)


def send_encrypted(conn: socket.socket, cipher: Fernet, nickname: str, message: str) -> None:
    plaintext = f"{nickname}: {message}".encode("utf-8")
    encrypted = cipher.encrypt(plaintext)
    header = struct.pack("!I", len(encrypted))
    conn.sendall(header + encrypted)


def receive_encrypted(conn: socket.socket, cipher: Fernet) -> str:
    header = recv_exact(conn, 4)
    message_size = struct.unpack("!I", header)[0]

    if message_size <= 0 or message_size > MAX_MESSAGE_SIZE:
        raise ValueError("Received an invalid message size.")

    encrypted = recv_exact(conn, message_size)
    try:
        return cipher.decrypt(encrypted).decode("utf-8")
    except InvalidToken as exc:
        raise InvalidToken("Unable to decrypt the incoming message.") from exc


def receiver_loop(conn: socket.socket, cipher: Fernet, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            message = receive_encrypted(conn, cipher)
            sys.stdout.write(f"\r\033[K{STYLE.green}{message}{STYLE.reset}\n> ")
            sys.stdout.flush()
        except (ConnectionError, OSError):
            if not stop_event.is_set():
                warning("The other user disconnected.")
                stop_event.set()
            break
        except InvalidToken:
            error("A message could not be decrypted. The shared key may be wrong.")
            stop_event.set()
            break
        except Exception as exc:
            error(f"Connection error: {exc}")
            stop_event.set()
            break


def create_server(port: int) -> tuple[socket.socket, tuple[str, int]]:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(("0.0.0.0", port))
        server.listen(1)
        info(f"Waiting for a peer on port {port}...")
        conn, addr = server.accept()
        return conn, addr
    finally:
        server.close()


def create_client(host: str, port: int) -> socket.socket:
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.settimeout(15)
    conn.connect((host, port))
    conn.settimeout(None)
    return conn


def ask_with_default(prompt: str, default: str) -> str:
    value = input(f"{prompt} [{default}]: ").strip()
    return value or default


def ask_port(default: int = DEFAULT_PORT) -> int:
    while True:
        value = ask_with_default("Port", str(default))
        try:
            return validate_port(int(value))
        except ValueError as exc:
            warning(str(exc))


def ask_key() -> bytes:
    while True:
        key_text = input("Secret key: ").strip()
        try:
            return parse_key(key_text)
        except ValueError as exc:
            warning(str(exc))


def interactive_config() -> ChatConfig:
    print(f"{STYLE.bold}Terminal Chat E2EE{STYLE.reset}")
    print(line())
    print("1. Create a room (Host)")
    print("2. Join a room (Client)")

    while True:
        choice = input("Choose 1 or 2: ").strip()
        if choice in {"1", "2"}:
            break
        warning("Please choose 1 or 2.")

    nickname = ask_with_default("Nickname", "Host" if choice == "1" else "Client")
    port = ask_port()

    if choice == "1":
        return ChatConfig(mode="host", port=port, nickname=nickname)

    host = input("Host IP or hostname: ").strip()
    while not host:
        warning("Host cannot be empty.")
        host = input("Host IP or hostname: ").strip()

    key = ask_key()
    return ChatConfig(mode="client", port=port, nickname=nickname, host=host, key=key)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Encrypted peer-to-peer terminal chat.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--host", action="store_true", help="Create a room and wait for one peer.")
    mode.add_argument("--connect", metavar="ADDRESS", help="Connect to a host address.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"TCP port (default: {DEFAULT_PORT}).")
    parser.add_argument("--nickname", default=None, help="Name shown next to your messages.")
    parser.add_argument("--key", help="Secret Fernet key provided by the host.")
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> Optional[ChatConfig]:
    if not args.host and not args.connect:
        return None

    try:
        port = validate_port(args.port)
    except ValueError as exc:
        error(str(exc))
        sys.exit(2)

    if args.host:
        return ChatConfig(mode="host", port=port, nickname=args.nickname or "Host")

    if not args.key:
        error("--key is required when using --connect.")
        sys.exit(2)

    try:
        key = parse_key(args.key)
    except ValueError as exc:
        error(str(exc))
        sys.exit(2)

    return ChatConfig(
        mode="client",
        port=port,
        nickname=args.nickname or "Client",
        host=args.connect,
        key=key,
    )


def print_host_instructions(port: int, key: bytes) -> None:
    local_ip = get_local_ip()
    print()
    success(f"Local IP: {local_ip}")
    warning(f"For WAN connections, forward TCP port {port} to this machine.")
    print(line())
    print(f"{STYLE.bold}Secret key - share it through a trusted channel:{STYLE.reset}")
    print(key.decode("utf-8"))
    print(line())
    print()


def open_connection(config: ChatConfig) -> tuple[socket.socket, Fernet]:
    if config.mode == "host":
        key = Fernet.generate_key()
        cipher = Fernet(key)
        print_host_instructions(config.port, key)
        conn, addr = create_server(config.port)
        success(f"Connected to {addr[0]}:{addr[1]}.")
        return conn, cipher

    assert config.host is not None
    assert config.key is not None
    cipher = Fernet(config.key)
    info(f"Connecting to {config.host}:{config.port}...")
    conn = create_client(config.host, config.port)
    success("Connected.")
    return conn, cipher


def print_help() -> None:
    print(line())
    print("/help   Show available commands")
    print("/clear  Clear the terminal")
    print("/exit   Close the chat")
    print(line())


def close_socket(conn: socket.socket) -> None:
    try:
        conn.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    conn.close()


def chat_loop(conn: socket.socket, cipher: Fernet, nickname: str) -> None:
    stop_event = threading.Event()
    receiver = threading.Thread(target=receiver_loop, args=(conn, cipher, stop_event), daemon=True)
    receiver.start()

    print()
    success("Chat is active and end-to-end encrypted.")
    print("Type /help for commands.")
    print()

    try:
        while not stop_event.is_set():
            try:
                message = input("> ")
            except EOFError:
                break

            command = message.strip().lower()
            if command in {"/exit", "exit", "quit"}:
                break
            if command == "/help":
                print_help()
                continue
            if command == "/clear":
                os.system("cls" if os.name == "nt" else "clear")
                continue
            if not message.strip():
                continue

            try:
                send_encrypted(conn, cipher, nickname, message)
            except OSError as exc:
                error(f"Unable to send message: {exc}")
                break
    except KeyboardInterrupt:
        print()
        warning("Closing chat...")
    finally:
        stop_event.set()
        close_socket(conn)
        receiver.join(timeout=1)
        success("Chat closed.")


def main() -> int:
    args = parse_args()
    config = config_from_args(args) or interactive_config()

    try:
        conn, cipher = open_connection(config)
    except OSError as exc:
        error(f"Connection failed: {exc}")
        return 1

    chat_loop(conn, cipher, config.nickname)
    return 0


if __name__ == "__main__":
    sys.exit(main())
