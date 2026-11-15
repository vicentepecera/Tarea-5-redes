import socket
import sys
from router import create_packet

def main():
    if len(sys.argv) != 4:
        print('Uso: python3 prueba_router.py "IP;puerto;TTL" IP_router_inicial puerto_router_inicial < archivo.txt')
        sys.exit(1)
    final_router_ip, final_router_port, starting_ttl = sys.argv[1].split(";")
    entry_router_address = (sys.argv[2], int(sys.argv[3]))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender_socket:
        for file_line in sys.stdin:
            file_line = file_line.rstrip("\n")
            outgoing_packet = create_packet({"dst_ip": final_router_ip, "dst_port": int(final_router_port),
                                             "ttl": int(starting_ttl), "payload": file_line})
            sender_socket.sendto(outgoing_packet, entry_router_address)

if __name__ == "__main__":
    main()