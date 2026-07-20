"""
Chooses which films to update based on some metrics
"""

from typing import Optional
import base64
import numpy as np
from numpy.random import choice
import polars as pl
from glob import glob
import json
from pathlib import Path
from datetime import datetime
import logging

log = logging.getLogger(__name__)


def _traces_to_list(val):
    """Normalize a plotly trace value into a Python list.

    Newer versions of plotly serialize numpy/pandas-backed traces as
    ``{"dtype": "f8", "bdata": "<base64>"}`` instead of plain JSON arrays, so
    the historical graph_data files (which encode the rating series this way)
    must be decoded back into a list. Older files already use plain lists.
    """
    if isinstance(val, dict):
        dtype = val.get("dtype", "f8")
        raw = val.get("bdata")
        if raw is None:
            return []
        try:
            return list(np.frombuffer(base64.b64decode(raw), dtype=np.dtype(dtype)))
        except Exception:
            return []
    if isinstance(val, (list, tuple)):
        return list(val)
    return [val] if val is not None else []


class UpdateSampler:
    def __init__(
        self,
        graph_path: str = "res/graph_data/",
        info_path: str = "res/movie_data/",
        note_history_len=2,
        nb_movies: int | None = None,
    ):
        self.graph_path = graph_path
        self.info_path = info_path
        self.history_len = note_history_len
        self.nb_movies = nb_movies
        self.df = pl.DataFrame()

    def _build_df(self):
        movies = []
        graphlist = glob(f"{self.graph_path}/*json")
        if len(graphlist) == 0:
            print("no movies in graph directory")
        for graphdata in graphlist:
            moviedata = {}
            graphdata = Path(graphdata)

            if " " in graphdata.stem:
                # print(f"skipping {movie.stem}")
                continue
            moviedata["id"] = graphdata.stem

            try:
                with open(graphdata) as f:
                    measures = json.load(f)

                    # ordered from earliest to latest
                    try:
                        last_measures = _traces_to_list(
                            measures["data"][0]["y"]
                        )[-5:]
                        last_update = _traces_to_list(measures["data"][0]["x"])[-1]
                    except (KeyError, IndexError):
                        print(f"failed movie {graphdata.stem}")
                        continue
                    moviedata["measures"] = last_measures
                    moviedata["last_update"] = last_update
            except FileNotFoundError:
                pass

            # get release date
            try:
                with open(f"{self.info_path}/{graphdata.stem}.json") as f:
                    movieinfo = json.load(f)
                    moviedata["release_date"] = movieinfo["release_date"]
            except FileNotFoundError:
                pass
                print(f"no movie info for {graphdata.stem}")

            movies.append(moviedata)
        df = pl.DataFrame(movies)
        # df = df.with_columns(pl.col("last_update").map_rows(datetime.fromisoformat))
        df = df.with_columns(pl.col("last_update").str.to_datetime())
        df = df.with_columns(
            pl.col("release_date").str.strptime(pl.Date, "%Y-%m-%d", strict=False)
        )
        self.df = df

    def _compute_last_measures(self):
        """
        Compute last measures metric.

        sums the changes between two measurements, in a rolling window.
        Ex: [0.5, 0.6, 0.5, 0.7] = [0.1, 0.1, 0.2].sum() = [0.4]

        Currently puts None if history_len > measurements.len()
        """

        def sum_changes(x):
            try:
                return abs(x[1] - x[0])
            except IndexError:
                return 0

        op = pl.element().rolling_map(sum_changes, self.history_len).sum()
        self.df = self.df.with_columns(
            pl.col("measures").list.eval(op, parallel=True).alias("note_change")
        )

    def _compute_days_since_release(self):
        """
        Computes a days since release column from release date.
        Puts null if no release date is specified
        """

        now = datetime.now()
        self.df = self.df.with_columns(
            (now - pl.col("release_date")).dt.total_days().alias("days_since_release")
        )

    def _compute_days_since_update(self):
        now = datetime.now()
        self.df = self.df.with_columns(
            ((now - pl.col("last_update")).dt.total_days()).alias("days_since_update")
        )

    def _compute_note_variability(self):
        self.df = self.df.with_columns(
            [
                (
                    pl.col("note_change")
                    .list.get(-1)
                    .fill_null(0)
                    .alias("note_variability")
                )
            ]
        )

    def _normalize_metrics(self):
        self.df = self.df.with_columns(
            [
                (
                    (pl.col("days_since_release") - pl.col("days_since_release").min())
                    / (
                        pl.col("days_since_release").max()
                        - pl.col("days_since_release").min()
                    )
                ).alias("dsr_norm"),  # days since release metric
                (
                    (pl.col("days_since_update") - pl.col("days_since_update").min())
                    / (
                        pl.col("days_since_update").max()
                        - pl.col("days_since_update").min()
                    )
                ).alias("dsu_norm"),  # days since update metric
                (
                    (pl.col("note_variability") - pl.col("note_variability").min())
                    / (
                        pl.col("note_variability").max()
                        - pl.col("note_variability").min()
                    )
                ).alias("note_var_norm"),  # days since update metric
            ]
        )

        self.df = self.df.with_columns(
            [(1 - pl.col("dsr_norm")).abs().alias("inv_dsr_norm")]
        )

    def _compute_heuristic(self):
        fac_var = 2
        fac_dsr = 1
        fac_dsu = 2

        # TODO: change denom. for null values.
        #       Ex: if note_var_norm == null, then only divide by fac_dsr + fac_dsu
        # Constant metric columns (e.g. every movie has the same note
        # variability) make (x-min)/(max-min) evaluate to NaN; fill both null
        # and NaN so the heuristic stays finite.
        self.df = self.df.with_columns(
            (
                (
                    fac_var * pl.col("note_var_norm").fill_null(0).fill_nan(0)
                    + fac_dsr * pl.col("inv_dsr_norm").fill_null(0).fill_nan(0)
                    + fac_dsu * pl.col("dsu_norm").fill_null(0).fill_nan(0)
                )
                / (fac_var + fac_dsr + fac_dsu)
            )
            .fill_null(0)
            .fill_nan(0)
            .alias("h")
        )

        # convert h into probability; fill_nan guards the all-zero h case
        # (max==min everywhere) so h_prob never contains NaN.
        self.df = self.df.with_columns(
            (pl.col("h") / pl.col("h").sum()).fill_nan(0).alias("h_prob")
        )

    def sample(self, nb_samples: Optional[int] = None):
        """
        nb_samples: override what's set in init
        """
        results = self.df.select([pl.col("id"), pl.col("h_prob")]).to_dict()
        if nb_samples is None:
            nb_samples = self.nb_movies
        # numpy.random.choice rejects NaN/inf probabilities, which appear when a
        # metric column is constant for every movie. Sanitise: replace non-finite
        # values with 0, then normalise (falling back to a uniform draw when the
        # remainder is all zero) so a single bad row can't kill the whole run.
        probs = np.asarray(results["h_prob"], dtype=float)
        probs = np.where(np.isfinite(probs), probs, 0.0)
        total = probs.sum()
        if not np.isfinite(total) or total <= 0:
            probs = np.full(probs.shape, 1.0 / len(probs))
        else:
            probs = probs / total
        to_update = list(
            choice(results["id"], p=probs, size=nb_samples, replace=True)
        )

        log.info(
            self.df.filter(pl.col("id").is_in(to_update))
            .sort("h_prob")
            .select([pl.col("id"), pl.col("h"), pl.col("h_prob")])
        )
        return list(set(to_update))

    def run(self, nb_samples):
        self._build_df()
        self._compute_last_measures()
        self._compute_days_since_release()
        self._compute_days_since_update()
        self._compute_note_variability()
        self._normalize_metrics()
        self._compute_heuristic()
        return self.sample(nb_samples)
