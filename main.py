import numpy as np
from sklearn.cluster import DBSCAN
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import socket, queue, time, threading, io, json
import tkinter as tk
from tkinter import Button, Label, W, E, N, S, Canvas
from mockup import generate_realistic_burst
import matplotlib.pyplot as plt
from PIL import Image, ImageTk
import sys


last_plot_data = [None, None, None]

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
                'points': [(lat, lon), ...],
                'error_code' : error_code
            }
        """

        grid_cells = defaultdict(list)

        for p in packets:
            i = int(p['lat'])*1000
            cod = int(p['error_code'])
            grid_cells[(i,cod)].append(p)
        
        #print("Grids Existentes: " + str(len(grid_cells)))
        #print(list(grid_cells.keys()))

        def _cluster_cell(cell_packets):
            coords = np.array([(p['lat'], p['lon']) for p in cell_packets])
            error_code = int(cell_packets[0].get('error_code', -1))
            cluster = DBSCAN(eps=self.eps, min_samples=self.min_samples, 
                      metric=self.metric).fit(np.longlong(coords)).labels_
            return self._extract_significant_clusters(coords, cluster, error_code)

        
        clusters = []

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(_cluster_cell, pts) for pts in grid_cells.values()]
            for f in futures:
                clusters.extend(f.result())

        clusters.sort(key=lambda c: c['size'], reverse=True)

        return clusters
    
    def _extract_significant_clusters(self, coords, labels, error_code):
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
                    'points': cluster_points.tolist(),
                    'error_code' : error_code
                })
        
        
        clusters.sort(key=lambda x: x['size'], reverse=True)
        return clusters
    
    def _update_error_stats(self, packets):
        """Atualiza estatísticas de códigos de erro."""
        for p in packets:
            self.error_stats[p['error_code']] += 1
    
gui_queue = queue.Queue()

def udp_receiver():
    """
    Recebe pacotes UDP e inicia uma análise do fluxo após o primeiro pacote.
    Se parar de receber pacotes, envia os pacotes acumulados para a fila.
    """
    accumulated_packets = []
    last_packet_time = None

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            packet = json.loads(data.decode("utf-8"))
            accumulated_packets.append(packet)
            gui_queue.put(('packet', len(accumulated_packets)))
            last_packet_time = time.time()

        except socket.timeout:
            if last_packet_time and (time.time() - last_packet_time > 5):
                if accumulated_packets:
                    packet_queue.put(accumulated_packets)
                    burst = packet_queue.get()
                    accumulated_packets = []
                    start_time = time.time()
                    detected_clusters = detector.process_packet_burst(burst)
                    gui_queue.put(('result', detected_clusters))
                    gui_queue.put(('plot', (burst, detected_clusters, detector.eps)))
                    processing_time = time.time() - start_time
                    print(f"Tempo de processamento: {processing_time:.4f} s - Clusters detectados: {len(detected_clusters)}")
                    for cluster_detail in detected_clusters:
                        lat, lon = cluster_detail['center']
                        error_code = cluster_detail['error_code']
                        print(f"Centro do cluster ({lat:.6f}, {lon:.6f}) -  Erro: {error_code}")
                last_packet_time = None
            continue

        except OSError:
            break


class CustomGUI:
    def __init__(self, master):
        self.master = master
        self.createWidgets()

    def createWidgets(self):
        """Build GUI with control buttons and display labels."""
        self.grafico = Button(self.master, width=15, padx=3, pady=3)
        self.grafico["text"] = "Gráfico"
        self.grafico["command"] = lambda: plot_clusters(*last_plot_data)
        self.grafico.grid(row=2, column=0, padx=2, pady=2)
        self.grafico["state"] = "disabled"

        self.canvas = Canvas(self.master, width=600, height=300, bg="black")
        self.canvas.grid(row=0, column=0, columnspan=4, padx=5, pady=5)

        self.timeBox = Label(self.master, width=12, text="00:00")
        self.timeBox.grid(row=1, column=1, columnspan=2, sticky=W+E+N+S, padx=5, pady=5)

   
   
  

def render_plot_image(packets, clusters, eps, width=600, height=300):
    """Gera uma imagem PNG do gráfico de clusters e retorna um PhotoImage para exibir na GUI."""
    fig = plt.figure(figsize=(width/100, height/100), dpi=100)
    ax = fig.add_subplot(111)
    coords = np.array([(p['lat'], p['lon']) for p in packets])
    ax.scatter(coords[:,1], coords[:,0], c='black', alpha=0.6, s=20)
    cmap = plt.get_cmap('tab10', max(len(clusters), 1))
    for idx, c in enumerate(clusters):
        pts = np.array(c['points'])
        color = cmap(idx)
        ax.scatter(pts[:,1], pts[:,0], c=[color], s=30)
        lat_c, lon_c = c['center']
        ax.scatter(lon_c, lat_c, marker='x', c=[color], s=100)
        radius = eps * (180/np.pi)
        circle = plt.Circle((lon_c, lat_c), radius, fill=False, edgecolor=color, linewidth=2)
        ax.add_patch(circle)
    lons = coords[:,1]
    lats = coords[:,0]
    margin = eps * (180/np.pi) * 1.1
    ax.set_xlim(lons.min() - margin, lons.max() + margin)
    ax.set_ylim(lats.min() - margin, lats.max() + margin)
    ax.set_aspect('equal', adjustable='box')
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.set_title('Clusters')
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    img = Image.open(buf)
    if img.height > img.width:
        img = img.rotate(90, expand=True)
    return ImageTk.PhotoImage(img)

def start_gui():
    root = tk.Tk()
    gui = CustomGUI(root)
    root.title("CEP Real-Time Detector")
    packet_label = tk.Label(root, text="Pacotes Recebidos: 0")
    packet_label.grid(row=3, column=0, columnspan=2, sticky=W+E, padx=5, pady=5)

    result_text = tk.Text(root, height=10)
    result_text.grid(row=4, column=0, columnspan=4, sticky=W+E, padx=5, pady=5)

    def poll_gui():
        while not gui_queue.empty():
            event, data = gui_queue.get()
            if event == 'packet':
                packet_label.config(text=f"Pacotes Recebidos: {data}")
            elif event == 'result':
                result_text.delete(1.0, tk.END)
                result_text.insert(tk.END, f"Clusters detectados: {len(data)}\n")
                for c in data:
                    lat, lon = c['center']
                    result_text.insert(tk.END, f"Centro: ({lat:.6f}, {lon:.6f}), Erro: {c['error_code']}, Tamanho: {c['size']}\n")
            elif event == 'plot':
                burst, detected_clusters, eps = data
                last_plot_data[0], last_plot_data[1], last_plot_data[2] = burst, detected_clusters, eps
                photo = render_plot_image(burst, detected_clusters, eps)
                gui.canvas.delete("all")
                gui.canvas.create_image(0, 0, anchor='nw', image=photo)
                gui.canvas.image = photo
                gui.grafico['state'] = 'normal'
        root.after(100, poll_gui)

    threading.Thread(target=udp_receiver, daemon=True).start()
    root.after(100, poll_gui)
    send_button = tk.Button(root, text="Enviar Dados", command=lambda: threading.Thread(target=generate_realistic_burst, daemon=True).start())
    send_button.grid(row=5, column=0, columnspan=4, pady=10)

    def on_closing():
        try:
            sock.close()
        except:
            pass
        root.quit()
        root.destroy()
        sys.exit(0)

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

def plot_clusters(packets, clusters, eps):
    """Plota pontos recebidos, marca centros dos clusters e desenha círculos de raio eps."""
    coords = np.array([(p['lat'], p['lon']) for p in packets])
    fig, ax = plt.subplots()
    ax.clear()
    ax.scatter(coords[:,1], coords[:,0], c='black', alpha=0.6, s=20, label='ruído')
    cmap = plt.get_cmap('tab10', max(len(clusters), 1))
    for idx, c in enumerate(clusters):
        pts = np.array(c['points'])
        color = cmap(idx)
        ax.scatter(pts[:,1], pts[:,0], c=[color], s=30, label=f'cluster {idx}')
        lat_c, lon_c = c['center']
        ax.scatter(lon_c, lat_c, marker='x', c=[color], s=100, label=f'centro {idx}')
        radius = eps * (180/np.pi)
        circle = plt.Circle((lon_c, lat_c), radius, fill=False, edgecolor=color, linewidth=2)
        ax.add_patch(circle)
        
    lons = coords[:,1]
    lats = coords[:,0]
    margin = eps * (180/np.pi) * 1.1
    ax.set_xlim(lons.min() - margin, lons.max() + margin)
    ax.set_ylim(lats.min() - margin, lats.max() + margin)
    ax.set_aspect('equal', adjustable='box')
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    fig.canvas.draw()
    plt.pause(0.001)

if __name__ == "__main__":

    detector = RealTimeClusterDetector(
        eps=0.005,   
        min_samples=100,         
        min_cluster_size=300      
    )

    packet_queue = queue.Queue()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", 5000))
    sock.settimeout(1.0)
    start_gui()







