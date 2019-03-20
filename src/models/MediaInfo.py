from functools import total_ordering
import datetime
import taglib
import os
from hashlib import md5
from src.utils import getFileType, pathUp
from src.models.Database import Database

@total_ordering
class MediaInfo(object):

    IMAGE_CACHE = os.path.join(Database.BASE, "cache")

    def __init__(self, path, pos, title, artist, album, albumArtist, duration, image, year=0):
        self.path = os.path.normpath(path)
        self.pos = pos
        self.title = title
        self.artist = artist
        self.album = album
        self.albumArtist = albumArtist
        self.year = year
        self.duration = duration
        self.image = image

    def searchImage(path, song=None):
        if song and song.picture:
            picture = song.picture
            if picture.mimetype == "image/jpg": ext = ".jpg"
            elif picture.mimetype == "image/jpeg": ext = ".jpeg"
            elif picture.mimetype == "image/png": ext = ".png"
            elif picture.mimetype == "image/bmp": ext = ".bmp"
            elif picture.mimetype == "image/gif": ext = ".gif"
            else: ext = ""
            dataHash = md5(picture.data).hexdigest()
            fpath = os.path.join(MediaInfo.IMAGE_CACHE, dataHash + ext)
            if os.path.isfile(fpath): return fpath
            Database.saveFile(picture.data, dataHash + ext, "cache")
            return fpath

        searchPath = pathUp(path)
        paths = list(filter(lambda path: getFileType(path) == "image", os.listdir(searchPath)))
        if paths:
            prioritize = ["Case Cover Back Outer", "Cover.", "cover.", "CD."]
            def find_path():
                for path in paths:
                    for priority in prioritize:
                        if path.startswith(priority):
                            return path
                return paths[0]
            return os.path.join(searchPath, find_path())
        else:
            return None

    def verify(self):
        if not os.path.isfile(self.path):
            return False
        if self.image and not os.path.isfile(self.image):
            self.image = MediaInfo.searchImage(self.path)
        return True

    def fromFile(path):
        song = taglib.File(path)
        artist = song.tags["ARTIST"][0] if "ARTIST" in song.tags else ""
        title = song.tags["TITLE"][0] if "TITLE" in song.tags else os.path.basename(path)

        pos = -1
        if "TRACKNUMBER" in song.tags:
            try:
                if "/" in song.tags["TRACKNUMBER"][0]:
                    pos = int(song.tags["TRACKNUMBER"][0].split("/")[0])
                else:
                    pos = int(song.tags["TRACKNUMBER"][0])
            except ValueError:
                pass

        try: album = song.tags["ALBUM"][0]
        except: album = ""

        try: albumArtist = song.tags["ALBUMARTIST"][0]
        except: albumArtist = artist

        try: year = int(song.tags["DATE"][0])
        except: year = -1

        return MediaInfo(path, pos, title, artist,
                         album, albumArtist,
                         datetime.datetime.fromtimestamp(song.length),
                         MediaInfo.searchImage(path, song),
                         year)

    # comparators
    def __lt__(self, other):
        if not isinstance(other, MediaInfo):
            return False
        if self.album == other.album and self.pos != -1 and other.pos != -1:
            return self.pos < other.pos
        return self.title < other.title

    def __eq__(self, other):
        if not isinstance(other, MediaInfo):
            return False
        if self.path == other.path:
            return True
        return object.__eq__(self, other)
