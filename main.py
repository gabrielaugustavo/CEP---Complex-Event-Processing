import numpy as np
from sklearn.cluster import DBSCAN
from concurrent.futures import ThreadPoolExecutor
import time
from collections import defaultdict
import random
import threading
import socket
from collections import defaultdict as _dd
import queue
import json

class RealTimeClusterDetector:

    def __init__(self, eps=0.003, min_samples=15, min_cluster_size=50):
        """
        Inicializa o detector de clusters em tempo real.
        
        Args:
            eps (float): Distância máxima em graus para considerar pontos vizinhos (~300m)
            min_samples (int): Número mínimo de pontos para formar um núcleo de cluster
            min_cluster_size (int): Tamanho mínimo para considerar um cluster válido
        """
        self.eps = eps
        self.min_samples = min_samples
        self.min_cluster_size = min_cluster_size
        self.metric = 'haversine'
        self.error_stats = defaultdict(int)
    
    def process_packet_burst(self, packets):
        """
        Processa uma rajada de pacotes e retorna clusters densos encontrados.
        
        Args:
            packets (list): Lista de dicionários com 'lat', 'lon' e 'error_code'
            
        Returns:
            list: Lista de clusters, cada um com {
                'center': (lat, lon),
                'size': int,
                'points': [(lat, lon), ...]
            }
        """
        # 1. Filtragem por qualidade dos dados
        
        valid_packets = [p for p in packets if p['error_code'] == 0]
        self._update_error_stats(packets)

        grid_cells = _dd(list)

        for p in valid_packets:
            i = int(p['lat']) // 100
            j = int(p['lon']) // 100
            grid_cells[(i,j)].append(p)
        
        print(valid_packets)

        def _cluster_cell(cell_packets):
            coords = np.array([(p['lat'], p['lon']) for p in cell_packets])
            cluster = DBSCAN(eps=self.eps, min_samples=self.min_samples, 
                      metric=self.metric).fit(np.radians(coords)).labels_
            return self._extract_significant_clusters(coords, cluster)

        
        clusters = []

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(_cluster_cell, pts) for pts in grid_cells.values()]
            for f in futures:
                clusters.extend(f.result())

        clusters.sort(key=lambda c: c['size'], reverse=True)

        return clusters
    
    def _extract_significant_clusters(self, coords, labels):
        """Extrai clusters que atendem ao critério de tamanho mínimo."""

        clusters = []
        unique_labels = set(labels) - {-1}  
        
        for label in unique_labels:
            cluster_points = coords[labels == label]
            cluster_size = len(cluster_points)
            
            if cluster_size >= self.min_cluster_size:
                center = (np.mean(cluster_points[:, 0]), np.mean(cluster_points[:, 1]))
                clusters.append({
                    'center': center,
                    'size': cluster_size,
                    'points': cluster_points.tolist()
                })
        
        
        clusters.sort(key=lambda x: x['size'], reverse=True)
        return clusters
    
    def _update_error_stats(self, packets):
        """Atualiza estatísticas de códigos de erro."""
        for p in packets:
            self.error_stats[p['error_code']] += 1
    
def udp_receiver():
        """
        Recebe pacotes UDP e inicia uma análise do fluxo após o primeiro pacote.
        Se parar de receber pacotes, envia os pacotes acumulados para a fila.
        """
        accumulated_packets = []
        last_packet_time = None

        while True:
            print("Rodando")
            try:
                data, addr = sock.recvfrom(4096)
                packet = json.loads(data.decode("utf-8"))
                accumulated_packets.append(packet)
                last_packet_time = time.time()

                print(len(accumulated_packets))

            except socket.timeout:
                # Verifica se o fluxo parou (nenhum pacote recebido por 5 segundos)
                if last_packet_time and (time.time() - last_packet_time > 5):
                    print("Fluxo de pacotes parou. Enviando pacotes acumulados para a fila.")
                    if accumulated_packets:
                        packet_queue.put(accumulated_packets)
                        accumulated_packets = []
                        start_time = time.time()
                        print(packet_queue)
                        detected_clusters = detector.process_packet_burst(packet_queue.get())
                        processing_time = time.time() - start_time
                        print(f"Tempo de processamento: {processing_time:.4f} s - Clusters detectados: {len(detected_clusters)}")
                    last_packet_time = None  # Reseta o tempo do último pacote

                continue

if __name__ == "__main__":

    detector = RealTimeClusterDetector(
        eps=0.00005 * (3.141592653589793/180),  # convertendo 0.00005° para radianos (~8.73e-7)
        min_samples=10,      # núcleos a partir de 10 vizinhos
        min_cluster_size=200 # clusters válidos com pelo menos 200 pontos
    )

    # Fila concorrente para pacotes
    packet_queue = queue.Queue()

    # Abre conexão UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", 5000))
    sock.settimeout(1.0)
    udp_receiver()







