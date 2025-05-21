"# TCP-like UDP over Mininet

This repository implements a reliable and congestion-controlled file transfer protocol over UDP, using Mininet for performance evaluation. The system simulates core TCP features including acknowledgments, retransmissions, and congestion control algorithms such as TCP Reno and TCP Cubic.

## 📦 Features

### ✅ Part 1: Reliability

Implements essential TCP-like mechanisms on top of UDP:

- Cumulative Acknowledgments (ACKs)
- Packet retransmission on timeout or duplicate ACKs
- Fast Recovery on 3 duplicate ACKs
- Sequence numbering for ordered delivery
- Timeout estimation using smoothed RTT and deviation
- JSON-based packet serialization

#### 🔧 How to Run (Part 1)

**Server**
\`\`\`bash
python3 p1_server.py <SERVER_IP> <SERVER_PORT> <FAST_RECOVERY_BOOL>
\`\`\`

**Client**
\`\`\`bash
python3 p1_client.py <SERVER_IP> <SERVER_PORT>
\`\`\`

> FAST_RECOVERY_BOOL: Use 1 to enable fast recovery, 0 to disable it.

#### 📊 Experiments

- **Loss Experiment**: Packet loss varied from 0% to 5% (in 0.5% steps), with/without fast recovery.
- **Delay Experiment**: Fixed loss rate (1%), delay varied from 0 ms to 200 ms (in 20 ms steps).
- **Plots**: Download time vs loss/delay, illustrating performance impact and benefits of fast recovery.

---

### 🚦 Part 2: Congestion Control

Implements TCP Reno-style congestion control on top of the reliability layer:

- Slow Start: Exponential cwnd growth until ssthresh
- Congestion Avoidance: Linear cwnd increase after ssthresh
- Fast Recovery: Halves cwnd on 3 duplicate ACKs
- Timeout: Resets cwnd to 1 MSS and restarts slow start
- AIMD: Additive Increase (1 MSS), Multiplicative Decrease (0.5× cwnd)

Initial window size: 1 MSS (1400 bytes)

#### 🔧 How to Run (Part 2)

**Server**
\`\`\`bash
python3 p2_server.py <SERVER_IP> <SERVER_PORT>
\`\`\`

**Client**
\`\`\`bash
python3 p2_client.py <SERVER_IP> <SERVER_PORT> --pref_outfile <PREF_FILENAME>
\`\`\`

> Server sends a file named \`file.txt\`. Client saves it as \`<PREF_FILENAME>received_file.txt\`.

#### 📊 Experiments

- **Throughput vs Delay**: Delay varied from 0 to 200 ms; throughput inversely proportional to RTT.
- **Throughput vs Loss**: Loss varied from 0% to 5%; results conform with \`Throughput ∝ 1 / (RTT × √p)\`.
- **Fairness**: Dumbbell topology with two client-server pairs; Jain’s fairness index plotted against link delay.

---

### 🚀 Part 3: Bonus – TCP Cubic

Implements the TCP Cubic congestion control algorithm with non-linear growth:

\[
W(t) = C(t - K)^3 + W_{max}, \quad K = \sqrt[3]{W_{max} \cdot \beta / C}
\]

- Parameters:
  - β = 0.5
  - C = 0.4

#### 📊 Experiments

- **Efficiency Comparison**: Compared throughput of TCP Reno and TCP Cubic under varying delay/loss.
- **Fairness Comparison**: Dumbbell topology with Reno on one link, Cubic on another. Cubic shows higher aggressiveness under low delay, impacting fairness at higher delays.

---

## 📁 Repository Structure

- \`p1_client.py\`, \`p1_server.py\`: UDP file transfer with reliability
- \`p2_client.py\`, \`p2_server.py\`: Reliable UDP with TCP Reno congestion control
- \`report.pdf\`: Detailed write-up with analysis and plots
- \`Assignment4.pdf\`: Problem statement and specifications

---

## ⚙️ Requirements

- Python 3.x
- Mininet (with Ryu controller)
- Standard Python libraries: \`socket\`, \`json\`, \`argparse\`, etc.
- Unix/Linux environment (recommended for nohup compatibility)

---

## 📝 Report

See \`report.pdf\` for:

- Description of reliability and congestion control mechanisms
- Experimental setup and configurations
- Analysis of results and comparison of TCP Reno vs TCP Cubic
- Plots: throughput vs loss/delay, fairness indices

---

## 🛡️ License

This repository is intended for academic and educational use. Refer to course policies for permissible use.
"
