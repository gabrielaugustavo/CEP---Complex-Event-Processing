import time
import matplotlib.pyplot as plt
from main import RealTimeClusterDetector
from mockup import generate_realistic_burst

def measure_time(detector, packets, workers):
    start = time.time()
    detector.process_packet_burst(packets, max_workers=workers)
    return time.time() - start

if __name__ == "__main__":
    burst = generate_realistic_burst()  
    detector = RealTimeClusterDetector(eps=0.0025, min_samples=100, min_cluster_size=300)

    worker_counts = [1, 2, 4, 8, 16, 32, 64, 128]
    times = []
    for w in worker_counts:
        t = measure_time(detector, burst, w)
        print(f"threads={w}: tempo={t:.4f}s")
        times.append(t)

    speedup = [times[0]/t for t in times]

    plt.figure()
    plt.plot(worker_counts, speedup, marker='o')
    plt.title("Speedup vs Número de Threads")
    plt.xlabel("Número de Threads")
    plt.ylabel("Speedup")
    plt.grid(True)
    plt.xticks(worker_counts)
    plt.savefig("speedup.png", dpi=150)
    plt.show()