import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.matching.pricing_service import run_pricing


def run():
    run_pricing()


if __name__ == "__main__":
    run()
