import socket
import sys
from router import create_packet
INITIAL_TTL = 64

def main():
    if len(sys.argv) not in (6, 7):
        print('Uso: python3 enviar.py IP_router_final puerto_router_final "mensaje" IP_envio puerto_envio [TTL]')
        sys.exit(1)
    final_router_ip, final_router_port, text_to_send, entry_router_ip, entry_router_port = sys.argv[1:6]
    starting_ttl = int(sys.argv[6]) if len(sys.argv) == 7 else INITIAL_TTL
    if not 0 <= starting_ttl <= 255:
        print("El TTL debe estar entre 0 y 255")
        sys.exit(1)
    outgoing_packet = create_packet({"dst_ip": final_router_ip, "dst_port": int(final_router_port),
                                     "ttl": starting_ttl, "payload": text_to_send})
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender_socket:
        sender_socket.sendto(outgoing_packet, (entry_router_ip, int(entry_router_port)))

if __name__ == "__main__":
    main()