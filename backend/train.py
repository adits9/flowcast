import argparse
import json
from pathlib import Path

from app.config import settings
from app.forecast import train

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train FlowCast with synthetic demo data or observed campus data.")
    parser.add_argument("--csv", type=Path, help="Observed 15-minute occupancy samples; see README for columns")
    parser.add_argument("--output", type=Path, default=settings.model_path)
    args = parser.parse_args()
    print(json.dumps(train(args.output, args.csv)["metadata"], indent=2))
