# app.py
import os
import uuid
from collections import defaultdict
from flask import Flask, request, Response, jsonify, render_template_string

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

# HTML page served at /
INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>MiniDFS — Upload visualizer</title>
  <style>
    body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, 14px; padding: 20px; max-width: 900px; }
    table { border-collapse: collapse; width: 100%; margin-top: 10px; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background: #f2f2f2; }
    .node { padding: 8px; border-radius: 6px; background: #fafafa; margin-bottom: 6px; }
    .chunk-percent { font-weight: 600; }
    .small { font-size: 0.9em; color: #555; }
    .center { text-align: center; }
    #out { white-space: pre-wrap; background:#fff; border:1px solid #eee; padding:10px; margin-top:8px; }
  </style>
</head>
<body>
  <h2>MiniDFS — Upload visualizer</h2>
  <p class="small">Chunk size: <span id="cfg_chunk"></span> bytes • Replication: <span id="cfg_rep"></span></p>

  <form id="uploadForm">
    <input type="file" id="fileInput" name="file" required />
    <button type="submit">Upload & Analyze</button>
  </form>

  <div id="summary" style="display:none;">
    <h3>File summary</h3>
    <p><strong>Name:</strong> <span id="fname"></span> · <strong>Size:</strong> <span id="fsize"></span> bytes</p>
    <p><strong>Total chunks:</strong> <span id="tot_chunks"></span></p>

    <h3>Per-chunk breakdown</h3>
    <table id="chunkTable">
      <thead>
        <tr><th class="center">Chunk ID</th><th>Size (bytes)</th><th>% of file</th><th>Replicated on</th></tr>
      </thead>
      <tbody></tbody>
    </table>

    <h3>Node distribution</h3>
    <div id="nodes"></div>
  </div>

  <div id="out"></div>

