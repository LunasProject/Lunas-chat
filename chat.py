import socket
import threading
import sys
import os
from cryptography.fernet import Fernet

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def receive_messages(conn, cipher):
    while True:
        try:
            encrypted_data = conn.recv(4096)
            if not encrypted_data:
                print("\n[!] The other user has logged out.")
                os._exit(0)

            message = cipher.decrypt(encrypted_data).decode('utf-8')

            sys.stdout.write(f"\r\033[K[Friend]: {message}\n> ")
            sys.stdout.flush()
        except Exception as e:
            print(f"\n[!] Decryption error or lost connection. ({e})")
            os._exit(1)

def main():
    print("=== TERMINAL CHAT E2EE ===")
    print("1. Create a room (Host)")
    print("2. Join a room (Client)")
    choice = input("Choose (1 o 2): ")

##
    port = 5555 # you can change the port
##

    if choice == '1':
        key = Fernet.generate_key()
        cipher = Fernet(key)

        local_ip = get_ip()
        print(f"\n[+] Your local ip is: {local_ip}")
        print("[!] MAKE SURE you have opened the TCP port", port, "on your router to this IP.")
        print("\n" + "="*50)
        print("SECRET KEY (Share it with the Client):")
        print(key.decode('utf-8'))
        print("="*50 + "\n")

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('0.0.0.0', port))
        server.listen(1)

        print(f"[*] Waiting for connection on port {port}...")
        conn, addr = server.accept()
        print(f"[+] Connected to {addr[0]}!")

    elif choice == '2':
        host_ip = input("\nEnter the (public) IP of the Host: ")
        key_input = input("Enter the SECRET KEY provided by the Host: ")

        try:
            cipher = Fernet(key_input.encode('utf-8'))
        except Exception:
            print("[!] Invalid key.")
            sys.exit(1)

        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"[*] Connecting to {host_ip}:{port} in progress...")
        try:
            conn.connect((host_ip, port))
            print("[+] Successfully connected!")
        except Exception as e:
            print(f"[!] Unable to connect: {e}")
            sys.exit(1)
    else:
        print("[!] Invalid choice.")
        sys.exit(1)

    print("\n[+] The chat is active and E2EE encrypted. Write a message and press Enter. (Type 'exit' to exit)\n")

    recv_thread = threading.Thread(target=receive_messages, args=(conn, cipher))
    recv_thread.daemon = True
    recv_thread.start()

    while True:
        try:
            msg = input("> ")
            if msg.strip().lower() == 'exit':
                print("[*] Closing in progress...")
                conn.close()
                os._exit(0)

            if msg.strip():
                encrypted_msg = cipher.encrypt(msg.encode('utf-8'))
                conn.send(encrypted_msg)
        except KeyboardInterrupt:
            print("\n[*] Forced closure...")
            conn.close()
            os._exit(0)

if __name__ == "__main__":
    main()
