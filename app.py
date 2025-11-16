import os
import uuid
from collections import defaultdict
from flask import Flask, request, Response

app = Flask(__name__)

# -----------------------
# CONFIG
# -----------------------
CHUNK_SIZE = 64         # bytes per chunk for simulation
REPLICATION = 3         # number of replicas per chunk
NODES = ["node1", "node2", "node3"]  # virtual nodes
# -----------------------

def chunk_file_bytes(file_bytes, chunk_size=CHUNK_SIZE):
    """Return list of byte chunks."""
    return [file_bytes[i:i+chunk_size] for i in range(0, len(file_bytes), chunk_size)]

def assign_chunks_greedy(num_chunks, nodes=NODES, replication=REPLICATION):
    """
    Greedy fill: each time choose the node with least assigned chunks so far.
    Returns dict node -> list of chunk_ids.
    """
    node_map = {n: [] for n in nodes}
    for cidx in range(num_chunks):
        # replicate this chunk replication times
        for _ in range(replication):
            # choose least loaded node (stable order)
            target = min(node_map.keys(), key=lambda n: len(node_map[n]))
            node_map[target].append(f"chunk_{cidx}")
    return node_map

def build_text_summary(filename, file_size, chunk_size, node_map):
    num_chunks = 0
    for chs in node_map.values():
        for c in chs:
            # collect max index from chunk names
            try:
                idx = int(c.split('_')[1])
                num_chunks = max(num_chunks, idx+1)
            except Exception:
                pass

    lines = []
    lines.append("MiniDFS — Distributed Storage Simulation")
    lines.append("============================================================")
    lines.append(f"File Name          : {filename}")
    lines.append(f"File Size          : {file_size} bytes")
    lines.append(f"Chunk Size         : {chunk_size} bytes")
    lines.append(f"Total Chunks       : {num_chunks}")
    lines.append(f"Replication Factor : {REPLICATION}")
    lines.append("")
    lines.append("Node Chunk Distribution (Greedy Fill):")
    for node in NODES:
        chs = node_map.get(node, [])
        lines.append(f" - {node}: {', '.join(chs) if chs else 'no chunks'}")
    lines.append("")
    lines.append("Chunk -> Replicas (for first 50 chunks):")
    # invert map to show which nodes hold each chunk
    chunk_to_nodes = defaultdict(list)
    for node, chs in node_map.items():
        for c in chs:
            chunk_to_nodes[c].append(node)
    sorted_chunks = sorted(chunk_to_nodes.keys(), key=lambda s: int(s.split('_')[1]))
    for c in sorted_chunks[:50]:
        lines.append(f"  {c} -> {', '.join(chunk_to_nodes[c])}")
    lines.append("")
    lines.append("Concepts demonstrated:")
    lines.append(" - File chunking into fixed-size blocks")
    lines.append(" - Replication of each chunk across multiple storage nodes")
    lines.append(" - Greedy distribution (assign to node with least load)")
    lines.append(" - Metadata mapping (chunk -> replicas) (simulated in-memory)")
    lines.append("")
    lines.append("Notes:")
    lines.append(" - This is a simulation (no real networked nodes).")
    lines.append(" - For real systems you'd persist metadata and store chunk bytes on nodes.")
    lines.append(" - You can change CHUNK_SIZE and REPLICATION at top of file.")
    lines.append("============================================================")
    return "\n".join(lines)


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}

@app.route("/upload", methods=["POST"])
def upload():
    """
    Accepts multipart/form-data with key 'file'.
    Returns a plain text project summary describing chunking & replication.
    """
    if 'file' not in request.files:
        return Response("No file provided (use form field 'file').", status=400, mimetype="text/plain")

    f = request.files['file']
    filename = f.filename or f"uploaded_{uuid.uuid4().hex}"
    data = f.read()
    filesize = len(data)

    # 1) chunk
    chunks = chunk_file_bytes(data, CHUNK_SIZE)
    num_chunks = len(chunks)

    # 2) assign replicas (greedy)
    node_map = assign_chunks_greedy(num_chunks)

    # 3) return text summary
    summary_text = build_text_summary(filename, filesize, CHUNK_SIZE, node_map)
    return Response(summary_text, mimetype="text/plain")

# Entry point for local testing and platforms that set PORT
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    # debug=False for production-like run
    app.run(host="0.0.0.0", port=port, debug=False)
