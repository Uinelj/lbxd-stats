import json
import logging
import random

log = logging.getLogger(__name__)


class Watchlist:
    def __init__(self, path):
        self.path = path
        with open(self.path) as f:
            self.watchlist = json.load(f)
        log.info(f"watchlist len: {len(self)}")

    def save(self):
        len(self.watchlist)
        # self.watchlist = set(self.watchlist)
        log.info(f"watchlist len: {len(self)}")
        with open(self.path, "w") as f:
            json.dump(self.watchlist, f, indent=2)

    def add(self, movieid, movie_title):
        log.info(f"adding {movieid} to watchlist")
        self.watchlist[movieid] = movie_title

    def contains(self, movieid):
        return movieid in self.watchlist.keys()

    def add_multiple(self, movies):
        for movie_id, movie_title in movies:
            self.watchlist[movie_id] = movie_title

    def getn(self, n):
        log.info(f"getting {n} movies from watchlist")
        watchlist = list(self.watchlist)
        random.shuffle(watchlist)
        return watchlist[:n]

    def __len__(self):
        return len(self.watchlist)

    # def shuffle(self):
    #     log.info("shuffling watchlist")
    #     random.shuffle(self.watchlist)
