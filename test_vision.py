import json
import sys

from app.nodes.vision import parse_diagram

out = parse_diagram({"image_path": sys.argv[1]})
print(json.dumps(out["parsed_diagram"], indent=2))