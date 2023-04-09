# for each movie in watchlist, get tmdb movie idin letterboxd page
# then, re-run the getting of movie info, but by using the tmdb
# movie id rather than the bad stem approach.

from watchlist import Watchlist
from scraper import tmdb_id
import json
from movie_info import MovieInfo
from tmdbv3api.exceptions import TMDbException

keys_to_keep = [
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

if __name__ == "__main__":
    wl = Watchlist("res/watchlist_new.json")
    mi = MovieInfo()
    fails = []
    for movieid in list(wl.watchlist):
        _id = tmdb_id(movieid)

        # only keeps some columns
        print(f"getting {movieid}")
        try:
            details = {k: v for k, v in mi.details(_id).items() if k in keys_to_keep}
            with open(f"res/movie_data/{movieid}.json", "w") as w:
                json.dump(dict(details), w, indent=2)
        except TMDbException as e:
            print(f"{movieid} not found")
            fails.append(movieid)
            print(e)

    print("Failed items:")
    for f in fails:
        print(f)
    # print(wl.watchlist)
