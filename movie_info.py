from tmdbv3api import Movie
from pathlib import Path
import json
from watchlist import Watchlist
import os
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


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
        log.info(f"refreshing {movie}")
        movie_rm_spaces = movie.replace("-", " ")
        movie_tmdb = self.movie.search(movie_rm_spaces)

        # if no results
        if len(movie_tmdb) == 0:
            # try with potential date removed
            movie_date_removed = _remove_date(movie_rm_spaces)
            log.info(f"removed date : {movie_rm_spaces} to {movie_date_removed}")
            # don't bother trying if no date is met
            if movie_date_removed != movie_rm_spaces:
                movie_tmdb = self.movie.search(movie_date_removed)

            # if we still have no results
            # (or still haven't updated movie_tmdb value), raise
            if len(movie_tmdb) == 0:
                raise MovieNotFound

        # else, write
        log.debug(f"{movie}, {movie_tmdb[0].title}, {movie_tmdb[0].id}")
        with open(self.data_dir / f"{movie}.json", "w") as f:
            json.dump(dict(movie_tmdb[0]), f, indent=2)

        return movie_tmdb[0]

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


mi = MovieInfo()
