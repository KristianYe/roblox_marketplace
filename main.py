from dataclasses import asdict

import pandas as pd

from utils import collect_items


if __name__ == "__main__":
    all_items = []
    all_items += collect_items()
    df = pd.DataFrame([asdict(item) for item in all_items])
    df = df.drop_duplicates(subset=["id_", "type"])
    df.to_excel("data.xlsx")
