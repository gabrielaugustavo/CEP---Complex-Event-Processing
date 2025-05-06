import numpy as np
from sklearn.cluster import DBSCAN
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import socket, queue, time, threading, json
import tkinter as tk
from tkinter import Button, Label, W, E, N, S
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk  
import sys
from mockup import generate_realistic_burst


HOST_MOD_3 = "10.15.82.198"
PORT_MOD_3 = 12345

tk_root = None

class RealTimeClusterDetector:
    def __init__(self, eps=0.003, min_samples=15, min_cluster_size=50):
        self.eps = eps
        self.min_samples = min_samples
        self.min_cluster_size = min_cluster_size
        self.metric = 'haversine'
        self.error_stats = defaultdict(int)

    def process_packet_burst(self, packets, max_workers=8):
        grid_cells = defaultdict(list)
        for p in packets:
            i = int(p['lat']) * 100
            cod = int(p['error_code'])
            grid_cells[(i, cod)].append(p)

        def _cluster_cell(cell_packets):
            coords = np.array([(p['lat'], p['lon']) for p in cell_packets])
            error_code = int(cell_packets[0].get('error_code', -1))
            cluster = DBSCAN(eps=self.eps, min_samples=self.min_samples, metric=self.metric).fit(
                np.longlong(coords)
            ).labels_
            return self._extract_significant_clusters(coords, cluster, error_code)

        clusters = []
        with ThreadPoolExecutor(max_workers = max_workers) as executor:
            futures = [executor.submit(_cluster_cell, pts) for pts in grid_cells.values()]
            for f in futures:
                clusters.extend(f.result())

        clusters.sort(key=lambda c: c['size'], reverse=True)
        return clusters

    def _extract_significant_clusters(self, coords, labels, error_code):
        clusters = []
        unique_labels = set(labels) - {-1}
        for label in unique_labels:
            cluster_points = coords[labels == label]
            if len(cluster_points) >= self.min_cluster_size:
                center = (np.mean(cluster_points[:, 0]), np.mean(cluster_points[:, 1]))
                clusters.append({
                    'center': center,
                    'size': len(cluster_points),
                    'points': cluster_points.tolist(),
                    'error_code': error_code
                })
        clusters.sort(key=lambda x: x['size'], reverse=True)
        return clusters

    def _update_error_stats(self, packets):
        for p in packets:
            self.error_stats[p['error_code']] += 1

gui_queue = queue.Queue()
packet_queue = queue.Queue()

def validate_packet(packet):
    """Verifica se o pacote possui os campos e tipos esperados."""
    required = ['lat', 'lon', 'error_code']
    for key in required:
        if key not in packet:
            return False
    try:
        float(packet['lat'])
        float(packet['lon'])
        int(packet['error_code'])
    except (TypeError, ValueError):
        return False
    return True

def udp_receiver():
    accumulated_packets = []
    last_packet_time = None
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            packet = json.loads(data.decode("utf-8"))
            if not validate_packet(packet):
                continue
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
                    processing_time = time.time() - start_time
                    gui_queue.put(('result', detected_clusters))
                    gui_queue.put(('plot', (burst, detected_clusters, detector.eps)))
                    gui_queue.put(('processing_time', processing_time))
                    print(f"Tempo de processamento: {processing_time:.4f} s - Clusters detectados: {len(detected_clusters)}")
                    for cluster_detail in detected_clusters:
                        lat, lon = cluster_detail['center']
                        error_code = cluster_detail['error_code']
                        print(f"Centro do cluster ({lat:.6f}, {lon:.6f}) -  Erro: {error_code}")
                    udp_modulo_3(detected_clusters)
                last_packet_time = None
            continue
        except OSError:
            continue

def udp_modulo_3(detected_clusters):
    sock_mod3 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_mod3.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    packetSend = []
    for cluster_detail in detected_clusters:
        lat, lon = cluster_detail['center']
        error_code = cluster_detail['error_code']
        packetSend.append({
            'URI': 102,
            'lat': lat,
            'lon': lon,
            'error_code': error_code
        })
    for packet in packetSend:
        data = json.dumps(packet).encode("utf-8")
        sock_mod3.sendto(data, (HOST_MOD_3, PORT_MOD_3))
        print(f"Pacote Enviado :{data}")
    return

class CustomGUI:
    def __init__(self, master):
        self.master = master
        self.createWidgets()
        self.photos = [] 

    def createWidgets(self):
        self.fig = plt.Figure(figsize=(7,4), dpi=100, constrained_layout=True)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)
        self.canvas.get_tk_widget().grid(row=0, column=0, columnspan=4, padx=5, pady=5)
        toolbar_frame = tk.Frame(self.master)
        toolbar_frame.grid(row=1, column=0, columnspan=4, padx=5, pady=2)
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()

        self.timeBox = Label(self.master, width=35, text="Tempo de Processamento: 00:00 s")
        self.timeBox.grid(row=2, column=1, columnspan=2, sticky=W+E+N+S, padx=5, pady=5)

        self.packet_total = Label(self.master, width=35, text="Pacotes Recebidos: 0")
        self.packet_total.grid(row=3, column=1, columnspan=2, sticky=W+E+N+S, padx=5, pady=5)

def start_gui():
    
    global tk_root
    root = tk.Tk()
    tk_root = root
    gui = CustomGUI(root)
    root.title("CEP Real-Time Detector")

    result_text = tk.Text(root, height=10)
    result_text.grid(row=4, column=0, columnspan=4, sticky=W+E, padx=5, pady=5)

    def poll_gui():
        while not gui_queue.empty():
            event, data = gui_queue.get()
            if event == 'packet':
                gui.packet_total.config(text=f"Pacotes Recebidos: {data}")
            elif event == 'result':
                result_text.delete(1.0, tk.END)
                result_text.insert(tk.END, f"Clusters detectados: {len(data)}\n")
                for c in data:
                    lat, lon = c['center']
                    result_text.insert(tk.END, f"Centro: ({lat:.6f}, {lon:.6f}), Erro: {c['error_code']}, Tamanho: {c['size']}\n")
            elif event == 'plot':
                packets, clusters, eps = data
                ax = gui.ax
                ax.clear()
                coords = np.array([(p['lat'], p['lon']) for p in packets])
                ax.scatter(coords[:,1], coords[:,0], c='black', alpha=0.6, s=20, label='ruído')
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
                lon_min, lon_max = coords[:,1].min(), coords[:,1].max()
                lat_min, lat_max = coords[:,0].min(), coords[:,0].max()
                lon_range, lat_range = lon_max - lon_min, lat_max - lat_min
                margin_lon = max(lon_range * 0.02, eps * (180/np.pi) * 0.05)
                margin_lat = max(lat_range * 0.02, eps * (180/np.pi) * 0.05)
                ax.set_xlim(lon_min - margin_lon, lon_max + margin_lon)
                ax.set_ylim(lat_min - margin_lat, lat_max + margin_lat)
                ax.margins(0)  
                ax.set_xlabel('Longitude')
                ax.set_ylabel('Latitude')
                ax.set_aspect('equal', adjustable='box')
                gui.canvas.draw()
            elif event == 'processing_time':
                gui.timeBox.config(text=f"Tempo de Processamento: {data:.4f} s")
        root.after(100, poll_gui)

    threading.Thread(target=udp_receiver, daemon=True).start()
    root.after(100, poll_gui)

    send_button = tk.Button(
        root,
        text="Enviar Dados",
        command=lambda: threading.Thread(target=generate_realistic_burst, daemon=True).start()
    )
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

if __name__ == "__main__":
    detector = RealTimeClusterDetector(
        eps=0.0025,
        min_samples=100,
        min_cluster_size=300
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", 5000))
    sock.settimeout(1.0)

    start_gui()







