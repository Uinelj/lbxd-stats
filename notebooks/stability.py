import marimo

__generated_with = "0.16.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    return (pl,)


@app.cell
def _(pl):
    df = pl.read_ndjson("../res/measures.jsonl")
    return (df,)


@app.cell
def _(df, pl):
    # get the num_refreshes per movie distribution
    df.group_by("movie").agg(pl.count("timestamp"))
    # get the time between refreshes distribution (should be bound by 1 or 2 weeks)
    return


@app.cell
def _(df, pl):
    df.filter(pl.col("movie") == "enola-holmes").sort(by="timestamp", descending=True)
    return


if __name__ == "__main__":
    app.run()
