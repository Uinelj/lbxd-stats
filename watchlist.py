from scraper import popular_movies, score, PopularPeriod, popular_movies_v2
import front
import json
import logging
import random
from utils import DateTimeEncoder

log = logging.getLogger(__name__)


class Watchlist:
    def __init__(self, path):
        self.path = path
        with open(self.path) as f:
            self.watchlist = json.load(f)
        log.info(f"watchlist len: {len(self)}")

    def save(self):
        len(self.watchlist)
        self.watchlist = set(self.watchlist)
        log.info(f"watchlist len: {len(self)}")
        len(self.watchlist)
        with open(self.path, "w") as f:
            json.dump(list(self.watchlist), f, indent=2)

    def add(self, movieid):
        log.info(f"adding {movieid} to watchlist")
        self.watchlist.append(movieid)

    def contains(self, movieid):
        return movieid in self.watchlist

    def add_multiple(self, movieids):
        self.watchlist.extend(movieids)

    def getn(self, n):
        log.info(f"getting {n} movies from watchlist")
        return self.watchlist[:n]

    def __len__(self):
        return len(self.watchlist)

    def shuffle(self):
        log.info("shuffling watchlist")
        random.shuffle(self.watchlist)
