import pathlib
import sys

from app.graph import graph

result = graph.invoke({"image_path": sys.argv[1], "errors": [], "retries": 0})

out = pathlib.Path("output")
out.mkdir(exist_ok=True)
for name, content in result["files"].items():
    (out / name).write_text(content, encoding="utf-8")

print("attempts:", result["retries"], "| remaining errors:", result["errors"])