"""
Phân tích độ trễ truyền dữ liệu MQTT từ số liệu đo trong Phụ lục khóa luận.

Dữ liệu: do_tre_phu_luc.csv (144 phép đo: 3 chặng x 3 node x 4 lần đo x 4 loại cảm biến)
  chặng 1 = ESP32 -> Mosquitto local, chặng 2 = Mosquitto -> MariaDB,
  chặng 3 = Mosquitto local -> HiveMQ Cloud.

Chạy:  python analyze_latency.py   (kết quả vào thư mục ket_qua/)
"""
import os
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OUT_DIR = "ket_qua"
CHANG_TEN = {1: "Chặng 1: ESP32 → Mosquitto", 2: "Chặng 2: Mosquitto → MariaDB",
             3: "Chặng 3: Mosquitto → HiveMQ Cloud"}

# 1) Thống kê mô tả theo chặng và node
Q_STATS = """
SELECT chang, node,
       COUNT(*)                                   AS so_phep_do,
       ROUND(AVG(do_tre_ms), 0)                   AS tb_ms,
       MIN(do_tre_ms)                             AS min_ms,
       MAX(do_tre_ms)                             AS max_ms,
       ROUND(SQRT(AVG(do_tre_ms * do_tre_ms)
                  - AVG(do_tre_ms) * AVG(do_tre_ms)), 1) AS do_lech_chuan
FROM do_tre
GROUP BY chang, node
ORDER BY chang, node
"""

# 2) Trung bình theo chặng (mọi node)
Q_HOP = """
SELECT chang, ROUND(AVG(do_tre_ms), 0) AS tb_ms
FROM do_tre
GROUP BY chang
ORDER BY chang
"""

# 3) Trung bình mỗi lần đo (gộp 4 cảm biến) để xem độ ổn định giữa các lần
Q_RUN = """
SELECT chang, node, lan_do, ROUND(AVG(do_tre_ms), 1) AS tb_ms
FROM do_tre
GROUP BY chang, node, lan_do
ORDER BY chang, node, lan_do
"""


def load(conn):
    df = pd.read_csv("do_tre_phu_luc.csv")
    df.to_sql("do_tre", conn, index=False, if_exists="replace")
    return df


def chart_box(df, path):
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5), sharey=False)
    for ax, chang in zip(axes, (1, 2, 3)):
        sub = df[df["chang"] == chang]
        nodes = ["bep", "phongkhach", "gara"]
        ax.boxplot([sub[sub["node"] == n]["do_tre_ms"] for n in nodes])
        ax.set_xticklabels(["Bếp", "Phòng khách", "Gara"])
        ax.set_title(CHANG_TEN[chang], fontsize=10)
        ax.set_ylabel("Độ trễ (ms)")
    fig.suptitle("Phân bố độ trễ theo chặng và node (16 phép đo mỗi hộp)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def chart_stack(stats, path):
    p = stats.pivot(index="node", columns="chang", values="tb_ms")
    p = p.loc[["bep", "phongkhach", "gara"]]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    # tổng ESP32 -> Cloud = chặng 1 + chặng 3 (chặng 2 là nhánh song song)
    ax.bar(p.index, p[1], label=CHANG_TEN[1])
    ax.bar(p.index, p[3], bottom=p[1], label=CHANG_TEN[3])
    ax.set_xticks(range(3))
    ax.set_xticklabels(["Bếp", "Phòng khách", "Gara"])
    ax.set_ylabel("Độ trễ trung bình (ms)")
    ax.set_title("Độ trễ ESP32 → Cloud = chặng 1 + chặng 3")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    conn = sqlite3.connect(":memory:")
    df = load(conn)

    stats = pd.read_sql(Q_STATS, conn)
    hop = pd.read_sql(Q_HOP, conn)
    runs = pd.read_sql(Q_RUN, conn)

    stats.to_csv(f"{OUT_DIR}/thong_ke_theo_chang_node.csv", index=False)
    chart_box(df, f"{OUT_DIR}/phan_bo_do_tre.png")
    chart_stack(stats, f"{OUT_DIR}/do_tre_den_cloud.png")

    print("=== Thống kê theo chặng và node ===")
    print(stats.to_string(index=False))
    print("\n=== Trung bình theo chặng ===")
    print(hop.to_string(index=False))

    # Độ trễ tổng ESP32 -> Cloud theo node
    p = stats.pivot(index="node", columns="chang", values="tb_ms")
    p["tong_esp32_cloud"] = p[1] + p[3]
    print("\n=== Tổng ESP32 -> Cloud (chặng 1 + chặng 3) ===")
    print(p[["tong_esp32_cloud"]].to_string())
    print("Trung bình 3 node:", round(p["tong_esp32_cloud"].mean()))

    # Biên dao động giữa các lần đo ở chặng 1
    r1 = runs[runs["chang"] == 1].groupby("node")["tb_ms"].agg(lambda s: s.max() - s.min())
    print("\n=== Biên dao động chặng 1 giữa 4 lần đo (ms) ===")
    print(r1.round(1).to_string())


if __name__ == "__main__":
    main()
