import socket
import time
import argparse
import json
import base64
import threading
import random
import math

MSS = 1400
DUP_ACK_THRESHOLD = 3
FILE_PATH = "file.txt"

BETA = 0.5
C = 0.4

ALPHA = 1 / 8
BETA_RTT = 1 / 4
INITIAL_RTO = 1
MIN_RTO = 0.1

DROP = -0.05
MAX_EOF_RETRANSMISSIONS = 5

def send_file(server_ip, server_port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((server_ip, server_port))

    print(f"Server listening on {server_ip}:{server_port}")

    print("Waiting for client connection...")
    data, client_address = server_socket.recvfrom(2048)
    print(f"Connection established with client {client_address}")

    with open(FILE_PATH, 'rb') as file:
        cwnd = MSS
        W_max = cwnd / MSS
        W_last_max = W_max
        ssthresh = float('inf')
        srtt = None
        devrtt = None
        rto = INITIAL_RTO
        seq_num = 0
        base = 0
        next_seq_num = 0
        unacked_packets = {}
        duplicate_ack_count = 0
        last_ack_received = -1
        last_loss_time = time.time()
        epoch_start_time = None
        K = None

        eof = False
        eof_seq = None
        eof_attempts = 1

        lock = threading.RLock()

        def send_packets():
            nonlocal next_seq_num, eof
            with lock:
                while next_seq_num < base + cwnd and not eof:
                    file.seek(next_seq_num)
                    data_chunk = file.read(MSS)
                    if not data_chunk:
                        eof = True
                        packet = create_packet(next_seq_num, b'eof', eof=True)
                        for _ in range(10):
                            if random.random() > DROP:
                                server_socket.sendto(packet, client_address)
                                print("*****")
                        unacked_packets[next_seq_num] = (packet, time.time(), 1)
                        print(f"Sent EOF packet with seq_num {next_seq_num}")
                        break
                    packet = create_packet(next_seq_num, data_chunk)
                    if random.random() > DROP:
                        server_socket.sendto(packet, client_address)
                    unacked_packets[next_seq_num] = (packet, time.time(), len(data_chunk))
                    print(f"Sent packet with seq_num {next_seq_num}, cwnd={cwnd}")
                    if not eof:
                        next_seq_num += len(data_chunk)

        def receive_acks():
            nonlocal base, cwnd, ssthresh, duplicate_ack_count, last_ack_received
            nonlocal srtt, devrtt, rto, W_max, W_last_max, last_loss_time, epoch_start_time, K
            while True:
                try:
                    server_socket.settimeout(rto)
                    ack_packet, _ = server_socket.recvfrom(2048)
                    ack_num = parse_ack_packet(ack_packet)
                    with lock:
                        if ack_num > base:
                            prev_base = base
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

                            current_time = time.time()
                            if epoch_start_time is None:
                                epoch_start_time = current_time
                                K = compute_K(W_max)
                                print(f"Epoch start: W_max={W_max:.4f}, K={K:.4f}")
                            t = current_time - epoch_start_time
                            W_cubic = cubic_function(t, K, W_max)
                            cwnd = max(W_cubic * MSS, MSS)
                            print(f"CUBIC: t={t:.4f}, W_cubic={W_cubic:.4f}, cwnd={cwnd:.2f}")

                            send_packets()
                        elif ack_num == last_ack_received:
                            duplicate_ack_count += 1
                            print(f"Received duplicate ACK for seq_num {ack_num}, count={duplicate_ack_count}")
                            if duplicate_ack_count >= DUP_ACK_THRESHOLD:
                                W_last_max = W_max
                                W_max = cwnd / MSS
                                cwnd = cwnd * BETA
                                print(f"Fast retransmit: W_max={W_max:.4f}, cwnd={cwnd:.2f}")

                                missing_seq = ack_num
                                if missing_seq in unacked_packets:
                                    packet, _, _ = unacked_packets[missing_seq]
                                    if random.random() > DROP:
                                        server_socket.sendto(packet, client_address)
                                    unacked_packets[missing_seq] = (packet, time.time(), unacked_packets[missing_seq][2])
                                    print(f"Retransmitted packet with seq_num {missing_seq}")

                                epoch_start_time = None
                                last_loss_time = time.time()
                        else:
                            pass
                except socket.timeout:
                    with lock:
                        ssthresh = max(cwnd // 2, MSS)
                        cwnd = MSS
                        duplicate_ack_count = 0
                        print(f"Timeout occurred: ssthresh={ssthresh}, cwnd={cwnd}")
                        if len(unacked_packets) == 1 and eof:
                            seq_num_to_retransmit = eof_seq
                            eof_attempts += 1
                            if eof_attempts > MAX_EOF_RETRANSMISSIONS:
                                print("Exceeded maximum EOF retransmissions")
                                return
                        if unacked_packets:
                            packets_to_retransmit = sorted(unacked_packets.keys())[:min(10, len(unacked_packets))]
                            for seq_num_to_retransmit in packets_to_retransmit:
                                packet, _, _ = unacked_packets[seq_num_to_retransmit]
                                if random.random() > DROP:
                                    server_socket.sendto(packet, client_address)
                                unacked_packets[seq_num_to_retransmit] = (packet, time.time(), unacked_packets[seq_num_to_retransmit][2])
                                print(f"Retransmitted packet with seq_num {seq_num_to_retransmit}")
                        rto = min(rto * 2, 60) 
                        print(f"Adjusted RTO to {rto} seconds")
                except Exception as e:
                    print(f"Error: {e}")
                    break
                if base > next_seq_num and eof:
                    break

        send_packets()

        ack_thread = threading.Thread(target=receive_acks)
        ack_thread.start()
        ack_thread.join()

        print("File transfer complete")
        server_socket.close()

def create_packet(seq_num, data, eof=False):
    packet_dict = {
        'seq_num': seq_num,
        'data': base64.b64encode(data).decode('ascii'),
        'eof': eof
    }
    packet_json = json.dumps(packet_dict)
    return packet_json.encode()

def parse_ack_packet(packet):
    ack_packet = json.loads(packet.decode())
    ack_num = ack_packet.get('ack_num')
    return ack_num

def update_rtt(rtt_sample, srtt, devrtt):
    if srtt is None:
        srtt = rtt_sample
        devrtt = rtt_sample / 2
    else:
        srtt = (1 - ALPHA) * srtt + ALPHA * rtt_sample
        devrtt = (1 - BETA_RTT) * devrtt + BETA_RTT * abs(rtt_sample - srtt)
    rto = srtt + 4 * devrtt
    rto = max(rto, MIN_RTO)
    print(f"Updated RTT estimates: srtt={srtt:.4f}, devrtt={devrtt:.4f}, rto={rto:.4f}")
    return srtt, devrtt, rto

def compute_K(W_max):
    K = ((W_max * (BETA)) / C) ** (1/3)
    return K

def cubic_function(t, K, W_max):
    W = C * ((t - K) ** 3) + W_max
    return W

parser = argparse.ArgumentParser(description='Reliable file transfer server over UDP with CUBIC congestion control.')
parser.add_argument('server_ip', help='IP address of the server')
parser.add_argument('server_port', type=int, help='Port number of the server')

args = parser.parse_args()

send_file(args.server_ip, args.server_port)