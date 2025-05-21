import socket
import argparse
import json
import base64
from time import sleep
import random
MSS = 1400
MAX_PACKET_SIZE = 2048
ANS = 0
RETRY_LIMIT = 10

DROP = -0.01


def receive_file(server_ip, server_port, pref_out):
    global ANS
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.settimeout(2)

    server_address = (server_ip, server_port)
    expected_seq_num = 0
    output_file_path = pref_out+"received_file.txt"
    # output_file_path = "received_file_abhiram.txt"

    retry_count = 0
    packet_buffer = {}
    eof_req = None

    while True:
        try:
            send_ack(client_socket, server_address, expected_seq_num)
            client_socket.settimeout(2)
            packet, _ = client_socket.recvfrom(MAX_PACKET_SIZE)
            break
        except socket.timeout:
            print("Retrying connection to server...")
            continue

    with open(output_file_path, 'wb') as file:
        while True:
            try:
                seq_num, data, eof = parse_packet(packet)
                ANS += 1
                if eof:
                    eof_req = seq_num

                if seq_num == expected_seq_num:
                    if not eof:
                        file.write(data)
                        expected_seq_num += len(data)
                        print(f"Received in-order packet {seq_num}, wrote {len(data)} bytes to file")

                        while expected_seq_num in packet_buffer and expected_seq_num!= eof_req:
                            buffered_data = packet_buffer.pop(expected_seq_num)
                            file.write(buffered_data)
                            print(f"Writing buffered packet {expected_seq_num}")
                            expected_seq_num += len(buffered_data)

                    if expected_seq_num == eof_req:
                    #     eof = True

                    # if eof:
                        print("Received EOF from server")
                        expected_seq_num += 1
                        for i in range(10):
                            if random.random() > DROP*10:
                                send_ack(client_socket, server_address, expected_seq_num)
                                print("Sending ACK for EOF")
                        break

                    send_ack(client_socket, server_address, expected_seq_num)
                
                elif seq_num > expected_seq_num:
                    if seq_num not in packet_buffer:
                        packet_buffer[seq_num] = data
                        print(f"Buffered out-of-order packet {seq_num}")
                    send_ack(client_socket, server_address, expected_seq_num)
                
                elif seq_num < expected_seq_num:
                    print(f"Received duplicate packet {seq_num}, expected {expected_seq_num}")
                    send_ack(client_socket, server_address, expected_seq_num)

                retry_count = 0
                packet, _ = client_socket.recvfrom(MAX_PACKET_SIZE)
            
            except socket.timeout:
                retry_count += 1
                print("Timeout waiting for data, resending ACK")
                send_ack(client_socket, server_address, expected_seq_num)
                if retry_count >= RETRY_LIMIT:
                    print("Max retries reached, terminating connection.")
                    break
            except Exception as e:
                print(f"Error: {e}")
                break

    print(f"Total packets received: {ANS}")
    print("Closing Client connection")
    client_socket.close()
    

def parse_packet(packet):
    packet_dict = json.loads(packet.decode())
    seq_num = packet_dict.get('seq_num')
    data = base64.b64decode(packet_dict.get('data').encode('ascii'))
    eof = packet_dict.get('eof', False)
    return seq_num, data, eof

def send_ack(client_socket, server_address, ack_num):
    ack_packet = json.dumps({'ack_num': ack_num}).encode()
    if random.random() > DROP:
        client_socket.sendto(ack_packet, server_address)
    else:
        print(f"COOKED")
    print(f"Sent ACK for seq_num {ack_num}")

# Argument parsing for server IP and port
parser = argparse.ArgumentParser(description='Reliable file receiver over UDP.')
parser.add_argument('server_ip', help='IP address of the server')
parser.add_argument('server_port', type=int, help='Port number of the server')
parser.add_argument('--pref_outfile', help='Path to save the received file')

args = parser.parse_args()
receive_file(args.server_ip, args.server_port, args.pref_outfile)
