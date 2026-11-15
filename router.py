import ipaddress
import socket
import sys
IP_HEADER_LENGTH = 7
MAX_UDP_DATAGRAM = 65535
next_hop_turn_by_area = {}

def parse_packet(IP_packet: bytes) -> dict:
    if len(IP_packet) < IP_HEADER_LENGTH:
        raise ValueError("Paquete demasiado corto: {} bytes".format(len(IP_packet)))
    dst_ip = ".".join(str(octet) for octet in IP_packet[0:4])
    dst_port = int.from_bytes(IP_packet[4:6], byteorder="big")
    remaining_ttl = IP_packet[6]
    payload_text = IP_packet[IP_HEADER_LENGTH:].decode("utf-8")
    return {"dst_ip": dst_ip, "dst_port": dst_port, "ttl": remaining_ttl, "payload": payload_text}

def create_packet(parsed_IP_packet: dict) -> bytes:
    ip_octets = bytes(int(octet) for octet in parsed_IP_packet["dst_ip"].split("."))
    if len(ip_octets) != 4:
        raise ValueError("IP inválida: {}".format(parsed_IP_packet["dst_ip"]))
    port_field = int(parsed_IP_packet["dst_port"]).to_bytes(2, byteorder="big")
    ttl_field = int(parsed_IP_packet["ttl"]).to_bytes(1, byteorder="big")
    payload_field = parsed_IP_packet["payload"].encode("utf-8")
    return ip_octets + port_field + ttl_field + payload_field

def describe_packet(parsed_IP_packet: dict) -> str:
    return "[{},{},{},{}]".format(parsed_IP_packet["dst_ip"], parsed_IP_packet["dst_port"],
                                  parsed_IP_packet["ttl"], parsed_IP_packet["payload"])

def load_routing_table(routes_file_name: str) -> list:
    table_entries = []
    with open(routes_file_name, "r") as table_file:
        for table_line in table_file:
            table_line = table_line.strip()
            if not table_line or table_line.startswith("#"):
                continue
            cidr_block, port_range_start, port_range_end, gateway_ip, gateway_port = table_line.split()
            table_entries.append({
                "subnet": ipaddress.ip_network(cidr_block, strict=False),
                "port_start": int(port_range_start),
                "port_end": int(port_range_end),
                "gateway": (gateway_ip, int(gateway_port)),
            })
    return table_entries

def entry_covers_destination(table_entry: dict, destination_address: tuple) -> bool:
    target_ip, target_port = destination_address
    return (ipaddress.ip_address(target_ip) in table_entry["subnet"]
            and table_entry["port_start"] <= target_port <= table_entry["port_end"])

def check_routes(routes_file_name: str, destination_address: tuple):
    table_entries = load_routing_table(routes_file_name)
    first_covering_entry = None
    for table_entry in table_entries:
        if entry_covers_destination(table_entry, destination_address):
            first_covering_entry = table_entry
            break
    if first_covering_entry is None:
        return None
    destination_area = (first_covering_entry["subnet"], first_covering_entry["port_start"],
                        first_covering_entry["port_end"])
    gateway_options = [entry["gateway"] for entry in table_entries
                       if (entry["subnet"], entry["port_start"], entry["port_end"]) == destination_area]
    turn_key = (routes_file_name, destination_area)
    current_turn = next_hop_turn_by_area.get(turn_key, 0) % len(gateway_options)
    next_hop_turn_by_area[turn_key] = (current_turn + 1) % len(gateway_options)
    return gateway_options[current_turn]

def start_router(listen_ip: str, listen_port: int, routing_table_path: str) -> None:
    local_address = (listen_ip, listen_port)
    router_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    router_socket.bind(local_address)
    print("Router escuchando en {} con tabla {}".format(local_address, routing_table_path), flush=True)
    while True:
        raw_datagram, _ = router_socket.recvfrom(MAX_UDP_DATAGRAM)
        try:
            received_packet = parse_packet(raw_datagram)
        except (ValueError, UnicodeDecodeError) as decode_error:
            print("Paquete mal formado descartado: {}".format(decode_error), flush=True)
            continue
        packet_description = describe_packet(received_packet)
        final_destination = (received_packet["dst_ip"], received_packet["dst_port"])
        if received_packet["ttl"] <= 0:
            print("Se recibió paquete {} con TTL 0".format(packet_description), flush=True)
            continue
        if final_destination == local_address:
            print(received_packet["payload"], flush=True)
            continue
        chosen_gateway = check_routes(routing_table_path, final_destination)
        if chosen_gateway is None:
            print("No hay rutas hacia {} para paquete {}".format(final_destination, packet_description), flush=True)
            continue
        received_packet["ttl"] -= 1
        print("redirigiendo paquete {} con destino final {} desde {} hacia {}".format(
            packet_description, final_destination, local_address, chosen_gateway), flush=True)
        router_socket.sendto(create_packet(received_packet), chosen_gateway)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python3 router.py router_IP router_puerto router_rutas.txt")
        sys.exit(1)
    start_router(sys.argv[1], int(sys.argv[2]), sys.argv[3])