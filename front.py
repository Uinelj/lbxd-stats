import polars as pl
import plotly.express as px
from datetime import datetime
import logging

log = logging.getLogger(__name__)

MEASURES = "res/measures.jsonl"


def extract_movie(df, movieid):
    ratings = df.filter(pl.col("movie") == movieid)
    print(ratings.collect())
    return ratings


def movie_iter(measures_path):
    pl.scan_ndjson(MEASURES)


def gen_graph_info():
    df = pl.scan_ndjson(MEASURES)

    df = df.with_columns(pl.col("timestamp").apply(lambda x: datetime.fromisoformat(x)))
    # go form one rating per row to one movie
    # per row (aggregating scores, timestamps and counts)
    by_movie = (
        df.groupby(pl.col("movie")).agg(
            [pl.col("rating"), pl.col("timestamp"), pl.col("count")]
        )
    ).collect()

    nb_movies = by_movie.select(pl.count())[0, 0]

    for idx, foo in enumerate(by_movie.rows(named=True)):
        movie = foo["movie"]
        fig = px.line(
            x=foo["timestamp"], y=foo["rating"], title=movie, text=foo["rating"]
        )
        fig.update_traces(textposition="bottom right")

        log.info(f"writing graph ({idx}/{nb_movies}): {movie}")
        with open(f"res/graph_data/{movie}.json", "w") as f:
            f.write(fig.to_json(pretty=True))


if __name__ == "__main__":
    gen_graph_info()
