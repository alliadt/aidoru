from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtMultimedia import *
import sys
import os
import urllib.parse
from .utils import getFileType, pathUp
from .models.Settings import settings
from .models.Database import Database
from .models.MediaInfo import MediaInfo
from .models.AlbumInfo import AlbumInfo
from .views.PlayerWidget import PlayerWidget
from .views.MediaPlayer import MediaPlayer
from .views.MediaLocationSelectionDialog import MediaLocationSelectionDialog

class MainWindow(QMainWindow):

    # modes
    FULL_MODE = 0
    MINI_MODE = 1
    MICRO_MODE = 2

    # files
    MEDIAS_FILE = "medias.pkl"

    # main
    def __init__(self):
        QMainWindow.__init__(self)

        self.setAcceptDrops(True)

        self.media = QMediaPlayer()
        self.mediaInfo = None
        self.album = None
        self.albums = {}
        self.albumPath = ""
        self.medias = [] # medias in scan directory
        self.setWatchFiles()

    initUIDone = pyqtSignal()
    def initUI(self):
        self.setWindowTitle("aidoru~~")
        self.mode = None

        self.setMode(MainWindow.FULL_MODE)
        self.setStyles()
        if settings.redrawBackground:
            # workaround for qt themes with transparent backgrounds
            self.setProperty("class", "redraw-background")
            self.style().unpolish(self)

        self.initUIDone.emit()
        self.show()

        # events
        self.media.mediaStatusChanged.connect(self.mediaStatusChanged)
        self.media.durationChanged.connect(self.durationChanged)

        QShortcut(QKeySequence("Ctrl+Q"), self).activated \
            .connect(sys.exit)
        QShortcut(QKeySequence("Space"), self).activated \
            .connect(self.playPause)
        QShortcut(QKeySequence("Ctrl+F"), self).activated \
            .connect(self.onCtrlF)
        QShortcut(QKeySequence("Ctrl+Shift+F"), self).activated \
            .connect(lambda: self.setMode(MainWindow.FULL_MODE))
        QShortcut(QKeySequence("Ctrl+M"), self).activated \
            .connect(lambda: self.setMode(MainWindow.MINI_MODE))
        QShortcut(QKeySequence("Ctrl+Shift+M"), self).activated \
            .connect(lambda: self.setMode(MainWindow.MICRO_MODE))
        QShortcut(QKeySequence("F5"), self).activated \
            .connect(lambda: self.repopulateMedias())

        # populate media
        try:
            medias = Database.load(MainWindow.MEDIAS_FILE)
        except:
            medias = None
        if medias:
            self.medias = list(filter(lambda media: media.verify(), medias))
            for mediaInfo in medias:
                dpath = pathUp(mediaInfo.path)
                if mediaInfo.album:
                    if dpath not in self.albums:
                        self.albums[dpath] = AlbumInfo(mediaInfo, False)
                    self.albums[dpath].medias.append(mediaInfo)
            self.sortAlbums()
            if len(medias) != len(self.medias):
                Database.save(self.medias, MainWindow.MEDIAS_FILE)
            self.mediasAdded.emit(medias)
            if settings.fileWatch:
                for media in self.medias:
                    self.fsWatcher.addPath(pathUp(media.path))
                    self.fsWatcher.addPath(media.path)
        elif not os.path.isdir(settings.mediaLocation):
            self.hide()
            self.mediaSelectionDialog = MediaLocationSelectionDialog()
            def delMediaSelection():
                self.show()
                self.populateMediaThread()
                del self.mediaSelectionDialog
            self.mediaSelectionDialog.okButton.clicked.connect(delMediaSelection)
            self.mediaSelectionDialog.show()
        else:
            self.populateMediaThread()

    nativeEventHandlers = []
    def nativeEvent(self, eventType, message):
        for handler in MainWindow.nativeEventHandlers:
            result = handler(eventType, message)
            if result: return result
        return QMainWindow.nativeEvent(self, eventType, message)

    windowShow = pyqtSignal()
    def showEvent(self, event):
        QMainWindow.showEvent(self, event)
        self.windowShow.emit()

    def setStyles(self):
        self.setStyleSheet(Database.loadFile("style.css",
                           "style.css" if not settings.darkTheme else "dark.css"))

    def setMode(self, mode):
        if mode == self.mode: return
        if mode == MainWindow.FULL_MODE:
            self.resize(QSize(1200, 900))
            centralWidget = MediaPlayer(self)
        elif mode == MainWindow.MINI_MODE:
            self.setMinimumSize(QSize(300, 475))
            self.resize(QSize(300, 475))
            centralWidget = PlayerWidget(self, PlayerWidget.MAIN_MODE)
        elif mode == MainWindow.MICRO_MODE:
            self.setMinimumSize(QSize(300, 65))
            self.resize(QSize(300, 65))
            centralWidget = PlayerWidget(self, PlayerWidget.MICRO_MODE)
        self.mode = mode
        self.setCentralWidget(centralWidget)

        # reemit events to redraw ui
        def emitAll():
            self.albumPath = ""
            #if self.album: self.albumChanged.emit(self.album)
            if self.mediaInfo: self.songInfoChanged.emit(self.mediaInfo)
            self.media.durationChanged.emit(self.media.duration())
            self.media.positionChanged.emit(self.media.position())
        QTimer.singleShot(0, emitAll)

    # playback
    def playPause(self):
        if self.media.state() == QMediaPlayer.PlayingState:
            self.media.pause()
        else:
            self.media.play()

    # song info
    songInfoChanged = pyqtSignal(MediaInfo)

    def setSong(self, path):
        self.setSongInfo(path)
        mediaContent = QMediaContent(QUrl(self.mediaInfo.path))
        self.media.setMedia(mediaContent)
        self.media.play()
        self.media.stateChanged.emit(self.media.state())

    def setSongInfo(self, path):
        print(path)
        if path.startswith("file://"):
            self.mediaInfo = MediaInfo.fromFile(path[7:])
        else:
            self.mediaInfo = MediaInfo(path)
        self.songInfoChanged.emit(self.mediaInfo)

    def durationChanged(self, duration):
        if duration:
            self.mediaInfo.duration = duration
            self.songInfoChanged.emit(self.mediaInfo)

    # dnd
    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat("text/uri-list"):
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        text = e.mimeData().text()
        if text.startswith("file://"):
            self.setSong(text)

    # album
    albumChanged = pyqtSignal(AlbumInfo)
    def populateAlbum(self, info): # TODO
        if not info.path.startswith("file://"): return
        albumPath = pathUp(info.path)
        if albumPath in self.albums:
            newAlbum = self.albums[albumPath]
        else:
            newAlbum = AlbumInfo(info)
        if newAlbum != self.album:
            self.album = newAlbum
            self.albumChanged.emit(self.album)

    def mediaStatusChanged(self, status):
        if status == QMediaPlayer.EndOfMedia:
            self.nextSong()

    # controls
    def songIndex(self, array):
        try:
            i, _ = next(filter(lambda i: i[1] == self.mediaInfo, enumerate(array)))
            return i
        except StopIteration:
            return -1

    def nextSong(self):
        if self.mode == MainWindow.FULL_MODE and self.centralWidget().mode != MediaPlayer.PLAYING_ALBUM_MODE:
            self.nextSongArray(self.medias, 1)
        elif self.album:
            self.nextSongArray(self.album.medias, 1)
    def prevSong(self):
        if self.mode == MainWindow.FULL_MODE and self.centralWidget().mode != MediaPlayer.PLAYING_ALBUM_MODE:
            self.nextSongArray(self.medias, -1)
        elif self.album:
            self.nextSongArray(self.album.medias, -1)

    def nextSongArray(self, array, delta):
        idx = self.songIndex(array)
        if idx == -1: return
        if 0 <= idx+delta < len(array):
            self.setSong(array[idx+delta].path)

    # files
    mediasAdded = pyqtSignal(list)
    mediasDeleted = pyqtSignal(list)
    def populateMedias(self, path):
        batch = []
        ls = list(map(lambda f: os.path.join(path, f), os.listdir(path)))
        if not ls: return
        if settings.fileWatch:
            self.fsWatcher.addPath(path)
            self.fsWatcher.addPaths(ls)
        for fpath in ls:
            if os.path.isdir(fpath):
                self.populateMedias(fpath)
            elif os.access(fpath, os.R_OK) and getFileType(fpath) == "audio":
                try:
                    mediaInfo = MediaInfo.fromFile(fpath)
                except OSError as e:
                    print(e)
                    continue
                dpath = pathUp(mediaInfo.path)
                if mediaInfo.album:
                    if dpath not in self.albums:
                        self.albums[dpath] = AlbumInfo(mediaInfo, False)
                    self.albums[dpath].medias.append(mediaInfo)
                batch.append(mediaInfo)
        self.sortAlbums()
        self.medias.extend(batch)
        self.mediasAdded.emit(batch)

    def populateMediaThread(self):
        class ProcessMediaThread(QThread):

            def run(self_):
                self.populateMedias(settings.mediaLocation)
                Database.save(self.medias, MainWindow.MEDIAS_FILE)
                del self._thread

        self._thread = ProcessMediaThread()
        self._thread.start()

    def repopulateMedias(self):
        deleted = self.medias
        self.medias = []
        self.albums = {}
        self.mediasDeleted.emit(deleted)
        self.setWatchFiles()
        QTimer.singleShot(0, self.populateMediaThread)

    # albums
    def sortAlbums(self):
        for album in self.albums.values():
            album.medias.sort()

    # file watcher
    def setWatchFiles(self):
        if settings.fileWatch:
            self.fsWatcher = QFileSystemWatcher()
            if self.medias:
                for media in self.medias:
                    self.fsWatcher.addPath(pathUp(media.path))
                    self.fsWatcher.addPath(media.path)
            self.fsWatcher.fileChanged.connect(self.watchFileChanged)
            self.fsWatcher.directoryChanged.connect(self.watchDirChanged)
        elif hasattr(self, "fsWatcher"):
            del self.fsWatcher

    def watchFileChanged(self, fpath):
        try:
            i, mediaInfo = next(filter(lambda i: i[1].path == fpath, enumerate(self.medias)))
            self.mediasDeleted.emit([mediaInfo])
            del self.medias[i]
        except StopIteration:
            pass
        try:
            mediaInfo = MediaInfo.fromFile(fpath)
            self.medias.append(mediaInfo)
            self.mediasAdded.emit([mediaInfo])
        except OSError:
            return

    def watchDirChanged(self, dpath):
        # TODO: handle directories
        oldPaths = set(filter(lambda fpath: pathUp(fpath) == dpath,
            map(lambda info: info.path, self.medias)))
        newPaths = set(map(lambda fpath: os.path.join(dpath, fpath),
                filter(lambda fpath: getFileType(fpath) == "audio", os.listdir(dpath))))
        removed = oldPaths.difference(newPaths)
        added = newPaths.difference(oldPaths)

        for fpath in removed:
            i, mediaInfo = next(filter(lambda i: i[1].path == fpath, enumerate(self.medias)))
            self.mediasDeleted.emit([mediaInfo])
            del self.medias[i]
        for fpath in added:
            try:
                mediaInfo = MediaInfo.fromFile(fpath)
            except OSError:
                continue
            self.medias.append(mediaInfo)
            self.mediasAdded.emit([mediaInfo])

    # misc
    def onCtrlF(self):
        self.setMode(MainWindow.FULL_MODE)
        self.centralWidget().fileListView.searchView.toggleVisible()

instance = None
