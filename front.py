import polars as pl
import plotly.express as px
from datetime import datetime

MEASURES = "res/measures.jsonl"


def extract_movie(df, movieid):
    ratings = df.filter(pl.col("movie") == movieid)
    print(ratings.collect())
    return ratings


if __name__ == "__main__":
    df = pl.scan_ndjson(MEASURES)
    df = df.with_columns(pl.col("timestamp").apply(lambda x: datetime.fromisoformat(x)))
    ratings = extract_movie(df, "inside-2023").collect()
    fig = px.line(ratings.to_pandas(), x="timestamp", y="rating")
    fig.show()
    # pl.Config.set_tbl_rows(100)
    # print(df.sort("movie").collect())
    # print(df.collect())
