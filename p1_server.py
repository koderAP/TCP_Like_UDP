import socket
import time
import argparse
import json
import base64
import threading
import random

MSS = 1400 
DUP_ACK_THRESHOLD = 3  
FILE_PATH = "file.txt"  
ALPHA = 1 / 8  
BETA = 1 / 4   
INITIAL_RTO = 1  
MIN_RTO = 0.1 

INITIAL_SSTHRESH = 128 * MSS
DESIRED_BANDWIDTH = 50_000_000  
DESIRED_RATE = DESIRED_BANDWIDTH / 8  
DROP = -1

def send_file(server_ip, server_port, enable_fast_recovery):
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((server_ip, server_port))

    print(f"Server listening on {server_ip}:{server_port}")

    print("Waiting for client connection...")
    data, client_address = server_socket.recvfrom(2048)
    print(f"Connection established with client {client_address}")

    with open(FILE_PATH, 'rb') as file:
        cwnd = MSS
        ssthresh = INITIAL_SSTHRESH
        srtt = None
        devrtt = None
        rto = INITIAL_RTO
        seq_num = 0
        base = 0
        next_seq_num = 0
        unacked_packets = {} 
        duplicate_ack_count = 0
        last_ack_received = -1
        total_data_sent = 0

        eof = False
        start_time = time.time()  

        lock = threading.RLock()

        def send_packets():
            nonlocal next_seq_num, eof, total_data_sent
            with lock:
                while next_seq_num < base + cwnd and not eof:
                    file.seek(next_seq_num)
                    data_chunk = file.read(MSS)
                    if not data_chunk:
                        eof = True
                        packet = create_packet(next_seq_num, b'eof', eof=True)
                        total_data_sent += len(packet)
                        enforce_bandwidth_limit(total_data_sent, start_time)
                        if random.random() > DROP:
                            server_socket.sendto(packet, client_address)
                        unacked_packets[next_seq_num] = (packet, time.time(), 1)
                        print(f"Sent EOF packet with seq_num {next_seq_num}")
                        break
                    packet = create_packet(next_seq_num, data_chunk)
                    total_data_sent += len(packet)
                    enforce_bandwidth_limit(total_data_sent, start_time)
                    if random.random() > DROP:
                        server_socket.sendto(packet, client_address)
                    unacked_packets[next_seq_num] = (packet, time.time(), len(data_chunk))
                    print(f"Sent packet with seq_num {next_seq_num}")
                    if not eof:
                        next_seq_num += len(data_chunk)

        def receive_acks():
            nonlocal base, cwnd, ssthresh, duplicate_ack_count, last_ack_received, srtt, devrtt, rto, total_data_sent
            while True:
                try:
                    server_socket.settimeout(rto)
                    ack_packet, _ = server_socket.recvfrom(2048)
                    ack_num = parse_ack_packet(ack_packet)
                    with lock:
                        if ack_num > base:
                            base = ack_num
                            duplicate_ack_count = 0
                            last_ack_received = ack_num

                            acknowledged_packets = [seq for seq in unacked_packets if seq + unacked_packets[seq][2] <= ack_num]
                            if acknowledged_packets:
                                earliest_seq = min(acknowledged_packets)
                                rtt_sample = time.time() - unacked_packets[earliest_seq][1]
                                srtt, devrtt, rto = update_rtt(rtt_sample, srtt, devrtt)

                            keys_to_delete = [seq for seq in unacked_packets if seq + unacked_packets[seq][2] <= ack_num]
                            for seq in keys_to_delete:
                                del unacked_packets[seq]
                            if cwnd < ssthresh:
                                cwnd *= 2
                                print(f"Slow start: Increased cwnd to {cwnd}")
                            else:
                                cwnd += (MSS * MSS) // cwnd
                                print(f"Congestion avoidance: Increased cwnd to {cwnd}")
                            send_packets()
                        elif ack_num == last_ack_received:
                            duplicate_ack_count += 1
                            print(f"Received duplicate ACK for seq_num {ack_num}, count={duplicate_ack_count}")
                            if duplicate_ack_count >= DUP_ACK_THRESHOLD and enable_fast_recovery:
                                ssthresh = max(cwnd // 2, MSS)
                                cwnd = ssthresh + 3 * MSS
                                print(f"Fast retransmit: ssthresh={ssthresh}, cwnd={cwnd}")
                                duplicate_ack_count = 0
                                missing_seq = ack_num
                                if missing_seq in unacked_packets:
                                    packet, _, _ = unacked_packets[missing_seq]
                                    if random.random() > DROP:
                                        server_socket.sendto(packet, client_address)
                                    unacked_packets[missing_seq] = (packet, time.time(), unacked_packets[missing_seq][2])
                                    print(f"Retransmitted packet with seq_num {missing_seq}")
                        else:
                            pass
                except socket.timeout:
                    with lock:
                        ssthresh = max(cwnd // 2, MSS)
                        cwnd = MSS
                        duplicate_ack_count = 0
                        print(f"Timeout occurred: ssthresh={ssthresh}, cwnd={cwnd}")
                        if unacked_packets:
                            seq_num_to_retransmit = min(unacked_packets.keys())
                            packet, _, _ = unacked_packets[seq_num_to_retransmit]
                            if random.random() > DROP:
                                server_socket.sendto(packet, client_address)
                            unacked_packets[seq_num_to_retransmit] = (packet, time.time(), unacked_packets[seq_num_to_retransmit][2])
                            print(f"Retransmitted packet with seq_num {seq_num_to_retransmit}")
                        rto = min(rto * 2, 60) 
                        print(f"Adjusted RTO to {rto} seconds")
                if base > next_seq_num and eof:
                    break

        send_packets()

        ack_thread = threading.Thread(target=receive_acks)
        ack_thread.start()
        ack_thread.join()

        print("File transfer complete")
        print(f"Total data sent: {total_data_sent / (1024 * 1024) * 8:.2f} Mb")
        print(f"Total time taken: {time.time() - start_time:.4f} seconds")
        server_socket.close()

def create_packet(seq_num, data, eof=False):
    """
    Create a packet with the sequence number and data.
    """
    packet_dict = {
        'seq_num': seq_num,
        'data': base64.b64encode(data).decode('ascii'),
        'eof': eof
    }
    packet_json = json.dumps(packet_dict)
    return packet_json.encode()

def parse_ack_packet(packet):
    """
    Parse the acknowledgment packet to extract the ack number.
    """
    ack_packet = json.loads(packet.decode())
    ack_num = ack_packet.get('ack_num')
    return ack_num

def fast_recovery(server_socket, client_address, unacked_packets, ack_seq_num):
    """
    Retransmit the earliest unacknowledged packet (fast recovery).
    """
    if ack_seq_num in unacked_packets:
        packet, _ , _= unacked_packets[ack_seq_num]
        server_socket.sendto(packet, client_address)
        unacked_packets[ack_seq_num] = (packet, time.time(), len(packet))
        print(f"Fast recovery: retransmitted packet with seq_num {ack_seq_num}")

def enforce_bandwidth_limit(total_data_sent, start_time):
    """
    Enforce the bandwidth limit by sleeping if we're sending data too quickly.
    """
    expected_duration = total_data_sent / DESIRED_RATE
    actual_duration = time.time() - start_time
    if actual_duration < expected_duration:
        sleep_time = expected_duration - actual_duration
        time.sleep(sleep_time)

def update_rtt(rtt_sample, srtt, devrtt):
    if srtt is None:
        srtt = rtt_sample
        devrtt = rtt_sample / 2
    else:
        srtt = (1 - ALPHA) * srtt + ALPHA * rtt_sample
        devrtt = (1 - BETA) * devrtt + BETA * abs(rtt_sample - srtt)
    rto = srtt + 4 * devrtt
    rto = max(rto, MIN_RTO)
    print(f"Updated RTT estimates: srtt={srtt:.4f}, devrtt={devrtt:.4f}, rto={rto:.4f}")
    return srtt, devrtt, rto

parser = argparse.ArgumentParser(description='Reliable file transfer server over UDP.')
parser.add_argument('server_ip', help='IP address of the server')
parser.add_argument('server_port', type=int, help='Port number of the server')
parser.add_argument('fast_recovery', type=int, help='Enable fast recovery (1 or 0)')

args = parser.parse_args()

enable_fast_recovery = bool(args.fast_recovery)

send_file(args.server_ip, args.server_port, enable_fast_recovery)