import numpy as np
import pandas as pd
import polars as pl
from ydata_profiling import ProfileReport
from datetime import datetime
from pathlib import Path

def gen_report(measures: Path = "res/measures.jsonl", out: Path = "res/static/report.html"):
    df = pl.read_ndjson(measures)
    # df = df.with_columns(pl.col("timestamp").str.strptime(pl.Date, "%+", strict=False))
    df = df.with_columns(pl.col("timestamp").apply(lambda x: datetime.fromisoformat(x)))
    print(df)

    p = ProfileReport(df.to_pandas())
    p.to_file(out)