"""Build a compact movie catalog (``res/catalog.json``) for the v3 frontend.

Merges each film's latest Letterboxd rating (+ previous rating for the trend,
rating count, last refresh time) with the TMDB poster/release info and the LBXD
title. The frontend only loads this single JSON file.
"""

import json
from pathlib import Path

import polars as pl

MEASURES = Path("res/measures.jsonl")
WATCHLIST = Path("res/watchlist_new.json")
MOVIE_DATA_DIR = Path("res/movie_data")
OUT = Path("res/catalog.json")

# W342 keeps posters crisp on a ~40-80px grid; down-scaled by the browser.
TMDB_POSTER = "https://image.tmdb.org/t/p/w342"


def _latest_measures() -> dict:
    """Return {movie: {rating, prev_rating, count, last_update, n_measures}}."""
    if not MEASURES.exists():
        return {}
    df = (
        pl.scan_ndjson(MEASURES)
        .with_columns(pl.col("timestamp").str.to_datetime())
        .sort("timestamp")
    )
    agg = (
        df.group_by("movie")
        .agg(
            pl.col("rating").tail(2).alias("ratings"),
            pl.col("count").tail(1).alias("counts"),
            pl.col("rating").count().alias("n_measures"),
            pl.col("timestamp").last().alias("last_update"),
        )
        .collect()
    )
    out = {}
    for row in agg.to_dicts():
        ratings = row["ratings"] or []
        rating = ratings[-1] if ratings else None
        prev = ratings[-2] if len(ratings) >= 2 else None
        counts = row["counts"] or []
        count = counts[-1] if counts else None
        last = row["last_update"]
        out[row["movie"]] = {
            "rating": rating,
            "prev_rating": prev,
            "count": count,
            "last_update": last.isoformat() if hasattr(last, "isoformat") else str(last),
            "n_measures": row["n_measures"],
        }
    return out


def _movie_meta(slug: str) -> dict:
    path = MOVIE_DATA_DIR / f"{slug}.json"
    if not path.exists():
        return {}
    try:
        md = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    poster = md.get("poster_path")
    return {
        "poster": f"{TMDB_POSTER}/{poster.lstrip('/')}" if poster else None,
        "release_date": md.get("release_date"),
        "vote_average": md.get("vote_average"),
    }


def _compact(n: int) -> str:
    if n is None:
        return "—"
    if n >= 1000:
        return f"{round(n / 1000)}K"
    return str(n)


def build_catalog() -> list:
    measures = _latest_measures()
    try:
        watchlist = json.loads(WATCHLIST.read_text())
    except (OSError, ValueError):
        watchlist = {}

    catalog = []
    for slug, title in watchlist.items():
        m = measures.get(slug)
        meta = _movie_meta(slug)
        rating = m["rating"] if m else None
        prev = m["prev_rating"] if m else None
        if rating is not None and prev is not None:
            if rating > prev:
                trend = "up"
            elif rating < prev:
                trend = "down"
            else:
                trend = "flat"
        else:
            trend = "none"
        catalog.append(
            {
                "id": slug,
                "title": title,
                "year": (meta.get("release_date") or "")[:4],
                "rating": rating,
                "prev_rating": prev,
                "trend": trend,
                "count": m["count"] if m else None,
                "count_short": _compact(m["count"]) if m else "—",
                "last_update": m["last_update"] if m else None,
                "n_measures": m["n_measures"] if m else 0,
                "poster": meta.get("poster"),
            }
        )

    catalog.sort(
        key=lambda e: (
            -(e["rating"] if e["rating"] is not None else -1),
            -(e["count"] if e["count"] is not None else -1),
            e["title"],
        )
    )
    return catalog


def main() -> None:
    catalog = build_catalog()
    OUT.write_text(json.dumps(catalog, ensure_ascii=False))
    print(f"wrote {OUT} with {len(catalog)} movies")


if __name__ == "__main__":
    main()
