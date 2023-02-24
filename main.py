from scraper import popular_movies, score
import toml
import json
import logging
import random
from utils import DateTimeEncoder


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

watchlist_path = "res/watchlist.toml"
measures_path = "res/measures.jsonl"
nb_query = 15

class Watchlist:
    def __init__(self, path):
        self.path = path
        self.watchlist = toml.load(path)
        
    def save(self):
        self.watchlist["movies"] = set(self.watchlist["movies"])
        with open(self.path, "w") as f:
            log.info(f"saving {len(self.watchlist)} movies")
            toml.dump(self.watchlist, f)

    def add(self, movieid):
        log.info(f"adding {movieid} to watchlist")
        self.watchlist["movies"].append(movieid)
    
    def add_multiple(self, movieids):
        log.info(f"adding {movieids} to watchlist")
        self.watchlist["movies"].extend(movieids)

    def getn(self, n):
        log.info(f"getting {n} movies from watchlist")
        return self.watchlist["movies"][:n]

    def shuffle(self):
        log.info("shuffling watchlist")
        random.shuffle(self.watchlist)

class Measures:
    def __init__(self, path):
        self.path = path
        self.measures = list()
        pass

    def query_add(self, movieid):
        m = score(movieid)
        self.measures.append(m)
        return m
    
    def append_to_file(self):
        with open(self.path, "a+") as f:
            log.info(f"adding {len(self.measures)} new measures")
            for measure in self.measures:
                ser = DateTimeEncoder().encode(measure)
                #ser = json.dumps(measure)
                f.writelines(ser + "\n")

if __name__ == "__main__":

    log.info("hello")
    #load watchlist
    wl = Watchlist(watchlist_path)
    m = Measures(measures_path )

    # get popular movies
    new_movies = popular_movies()

    # query measures for new movies
    for movieid in new_movies:
        m.query_add(movieid)

    # query measures for old movies
    for movieid in wl.getn(nb_query):
        m.query_add(movieid)

    # add new movies to watchlist
    wl.add_multiple(new_movies)

    # shuffle list
    wl.shuffle() 

    wl.save()
    m.append_to_file()