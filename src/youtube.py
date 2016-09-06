# Copyright (c) 2014-2016 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from gi.repository import GLib, Gio, GObject

from gettext import gettext as _
from threading import Thread
import json

from lollypop.sqlcursor import SqlCursor
from lollypop.tagreader import TagReader
from lollypop.define import Lp


class Youtube(GObject.GObject):
    """
        Youtube helper
    """
    __gsignals__ = {
        'uri-set': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self):
        """
            Init helper
        """
        GObject.GObject.__init__(self)

    def save_track(self, item, persistent):
        """
            Save item into collection as track
            @param item as SearchItem
            @param persistent as DbPersistent
        """
        t = TagReader()
        artists = "; ".join(item.artists)
        (artist_ids, new_artist_ids) = t.add_artists(artists,
                                                     artists,
                                                     "")
        (album_artist_ids, new_album_artist_ids) = t.add_album_artists(
                                                           artists,
                                                           "")

        (album_id, new_album) = t.add_album(item.album,
                                            album_artist_ids,
                                            "", 0, 0)

        (genre_ids, new_genre_ids) = t.add_genres(_("Youtube"), album_id)

        # Add track to db
        track_id = Lp().tracks.add(item.name, "", item.duration,
                                   0, item.discnumber, "",
                                   album_id, None, 0, 0, persistent)
        t.update_track(track_id, artist_ids, genre_ids)
        t.update_album(album_id, album_artist_ids, genre_ids, None)
        with SqlCursor(Lp().db) as sql:
                sql.commit()
        # Notify about new artists/genres
        if new_genre_ids or new_artist_ids:
            for genre_id in new_genre_ids:
                GLib.idle_add(Lp().scanner.emit, 'genre-added', genre_id)
            for artist_id in new_artist_ids:
                GLib.idle_add(Lp().scanner.emit, 'artist-added',
                              artist_id, album_id)
        t = Thread(target=self.__save_cover, args=(item, album_id,))
        t.daemon = True
        t.start()
        t = Thread(target=self.__set_youtube_uri, args=(item, track_id,))
        t.daemon = True
        t.start()
        if Lp().settings.get_value('artist-artwork'):
            Lp().art.cache_artists_info()

    def save_album(self, item, persistent):
        """
            Save item into collection as album
            @param item as SearchItem
            @param persistent as DbPersistent
        """
        pass

#######################
# PRIVATE             #
#######################
    def __set_youtube_uri(self, item, track_id):
        """
            Get youtube uri
            @param item as SearchItem
            @param track id as int
        """
        youtube_id = self.__get_youtube_id(item)
        argv = ["youtube-dl", "-g", "-f", "bestaudio",
                "https://www.youtube.com/watch?v=%s" % youtube_id, None]
        try:
            (s, out, err, e) = GLib.spawn_sync(None, argv, None,
                                               GLib.SpawnFlags.SEARCH_PATH,
                                               None)
            url = out.decode('utf-8')
            Lp().tracks.set_uri(track_id, url)
            GLib.idle_add(self.emit, 'uri-set', track_id)
        except Exception as e:
            print("Youtube::__get_youtube_uri()", e)

    def __get_youtube_id(self, item):
        """
            Get youtube id
            @param item as SearchItem
        """
        search = "%s %s %s" % (item.name,
                               " ".join(item.artists),
                               item.album)
        key = "AIzaSyBiaYluG8pVYxgKRGcc4uEbtgE9q8la0dw"
        cx = "015987506728554693370:waw3yqru59a"
        try:
            f = Gio.File.new_for_uri("https://www.googleapis.com/youtube/v3/"
                                     "search?part=snippet&q=%s&"
                                     "type=video&key=%s&cx=%s" % (
                                                              search,
                                                              key,
                                                              cx))
            (status, data, tag) = f.load_contents(None)
            if status:
                decode = json.loads(data.decode('utf-8'))
                return decode['items'][0]['id']['videoId']
        except Exception as e:
            print("Youtube::__get_youtube_id():", e)
        return None

    def __save_cover(self, item, album_id):
        """
            Save cover to store
            @param item as SearchItem
            @param album id as int
        """
        f = Gio.File.new_for_uri(item.cover)
        (status, data, tag) = f.load_contents(None)
        if status:
            Lp().art.save_album_artwork(data, album_id)
