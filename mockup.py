import random
import json
import socket
import time




def generate_realistic_burst(total_packets=300000, num_clusters=4, eps=0.00005, host="127.0.0.1", port=5000):
    """
    Gera uma rajada realista de pacotes com clusters aleatórios e envia cada pacote via UDP em formato JSON.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    packets = []
    
    for _ in range(num_clusters):
        
        center_lat = random.uniform(-90, 90)
        center_lon = random.uniform(-180, 180)
        
        # Gera 300 pacotes muito próximos do centro
        for _ in range(300):
            packets.append({
                'lat': center_lat + random.uniform(-eps*0.5, eps*0.5),
                'lon': center_lon + random.uniform(-eps*0.5, eps*0.5),
                'error_code': 0
            })

    noise_size = total_packets - len(packets)
    for _ in range(noise_size):
        packets.append({
            'lat': random.uniform(-90, 90),
            'lon': random.uniform(-180, 180),
            'error_code': 0
        })

    random.shuffle(packets)
    total_send_packets = 0

    # Envia cada pacote via UDP como JSON
    for packet in packets:
        data = json.dumps(packet).encode("utf-8")
        sock.sendto(data, (host, port))
        total_send_packets+=1
        print(total_send_packets)
    time.sleep(10)
    sock.close()
    

if __name__ == "__main__":
    generate_realistic_burst()


