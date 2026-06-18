# Terminal Chat E2EE

A lightweight peer-to-peer terminal chat written in Python. It lets two computers communicate directly on a LAN or over the Internet, with messages encrypted before they leave each machine.

## Features

- Peer-to-peer connection with no central server.
- End-to-end encrypted messages using `cryptography` and Fernet.
- Robust TCP message framing, so messages are not corrupted when packets are split or merged.
- Interactive host/client setup plus optional command-line arguments.
- Configurable port and nickname.
- Clean shutdown on `/exit`, peer disconnect, or `Ctrl+C`.
- Simple terminal commands: `/help`, `/clear`, and `/exit`.

## Requirements

- Python 3.10 or newer.
- The `cryptography` package.

Install the dependency with:

```bash
pip install cryptography
```

## Quick Start

Run the chat:

```bash
python chat.py
```

Choose one machine as the host and the other as the client.

### Host

1. Choose `1. Create a room (Host)`.
2. Enter a nickname and port, or press Enter to use the defaults.
3. Copy the generated secret key.
4. Share the key and the host IP address through a trusted channel.
5. Wait for the client to connect.

### Client

1. Choose `2. Join a room (Client)`.
2. Enter a nickname and port.
3. Enter the host IP address or hostname.
4. Paste the secret key provided by the host.
5. Start chatting.

## Command-Line Usage

You can skip the interactive menu with arguments.

Start a host:

```bash
python chat.py --host --nickname Alice --port 5555
```

Connect as a client:

```bash
python chat.py --connect 192.168.1.10 --nickname Bob --port 5555 --key YOUR_SECRET_KEY
```

Show all options:

```bash
python chat.py --help
```

## Chat Commands

- `/help` shows the available commands.
- `/clear` clears the terminal.
- `/exit` closes the chat.

The words `exit` and `quit` also close the chat.

## Internet Connections

For connections outside the same LAN, the host usually needs to configure port forwarding on the router:

1. Forward TCP port `5555`, or the custom port you selected, to the host machine.
2. Give the client your public IP address instead of your local LAN address.
3. Keep the secret key private and send it only through a trusted channel.

Firewall rules may also need to allow inbound TCP connections on the selected port.

## Security Notes

Messages are encrypted locally with a shared Fernet key. The key exchange still happens outside the program, so the security of the chat depends on sharing that key through a trusted channel.

If someone obtains the secret key, they can decrypt messages for that session.

## Troubleshooting

- `Address already in use`: choose another port or close the program using that port.
- `Connection refused`: verify that the host is running and the IP/port are correct.
- `Timed out`: check firewall rules, router port forwarding, and network reachability.
- `A message could not be decrypted`: both peers are not using the same secret key.

## License

This project is licensed under the MIT License.
