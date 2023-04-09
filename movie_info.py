from tmdbv3api import Movie
from pathlib import Path
import json
from watchlist import Watchlist
from scraper import tmdb_id
import os
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


KEYS_TO_KEEP = [
    "adult",
    "backdrop_path",
    "genre_ids",
    "id",
    "original_language",
    "original_title",
    "overview",
    "popularity",
    "poster_path",
    "release_date",
    "title",
    "video",
    "vote_average",
    "vote_count",
]


class MovieNotFound(Exception):
    pass


def _remove_date(movie):
    toks = movie.split("-")
    toks = movie.split(" ")

    # remove last token if it can be parsed to a number
    try:
        int(toks[-1])
        toks.pop()
    except ValueError:
        pass

    return " ".join(toks)


# have a letterboxd id - tmdb id mapping somewhere?
# at res/movie_data/index.json?
class MovieInfo:
    def __init__(self, data_dir="res/movie_data"):
        self.movie = Movie()
        self.data_dir = Path(data_dir)

        try:
            log.info(f"creating movie data dir at {data_dir}")
            os.mkdir(data_dir)
        except FileExistsError:
            pass

    def search(self, movieid):
        results = self.movie.search(movieid)
        log.info(f"results for movie {movieid}: {results}")
        return results[0]

    def details(self, tmdb_id):
        """
        get data from tmdb id
        """
        results = self.movie.details(tmdb_id)
        return results

    def get_update(self, movieid):
        """
        get from db OR call refresh()
        """
        try:
            with open(self.data_dir / f"{movieid}.json") as f:
                return json.load(f)
        except FileNotFoundError:
            return self.refresh(movieid)

    def refresh(self, movie):
        """
        refresh a movie
        """

        _id = tmdb_id(movie)
        details = self.details(_id)
        details = {k: v for k, v in details.items() if k in KEYS_TO_KEEP}
        with open(self.data_dir / f"{movie}.json", "w") as f:
            json.dump(details, f, indent=2)

        return details

    def refresh_all(self, wl_path):
        """
        builds mapping from lbxd id to tmdb id
        + saves data in separate json files (one per movie)
        """
        wl = Watchlist(wl_path)
        fails = []
        for idx, movie in enumerate(wl.watchlist):
            if idx % 100 == 0 and idx != 0:
                log.info(f"Fails: {len(fails)}/{len(wl.watchlist)}")
            try:
                self.refresh(movie)
            except MovieNotFound:
                fails.append(movie)
        if len(fails) != 0:
            log.error(f"Following movies failed: {fails}")
