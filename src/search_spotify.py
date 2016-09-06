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

from gi.repository import GLib, Gio

from lollypop.search_item import SearchItem

import json


class SpotifySearch:
    """
        Search provider for Spotify
    """
    def __init__(self):
        """
            Init provider
        """
        pass

    def tracks(self, name):
        """
            Return tracks containing name
            @param name as str
            @return tracks as [SearchItem]
        """
        items = []
        try:
            formated = GLib.uri_escape_string(name, None, True).replace(
                                                                      ' ', '+')
            s = Gio.File.new_for_uri("https://api.spotify.com/v1/search?q=%s"
                                     "&type=track" % formated)
            (status, data, tag) = s.load_contents()
            if status:
                decode = json.loads(data.decode('utf-8'))
                for item in decode['tracks']['items']:
                    search_item = SearchItem()
                    search_item.is_track = True
                    search_item.name = item['name']
                    search_item.album = item['album']['name']
                    search_item.tracknumber = int(item['track_number'])
                    search_item.discnumber = int(item['disc_number'])
                    search_item.duration = int(item['duration_ms']) / 1000
                    search_item.cover = item['album']['images'][0]['url']
                    search_item.smallcover = item['album']['images'][2]['url']
                    for artist in item['artists']:
                        search_item.artists.append(artist['name'])
                    items.append(search_item)
        except Exception as e:
            print("SpotifySearch::tracks(): %s" % e)
        return items

    def albums(self, name):
        """
            Return albums containing name
            @param name as str
            @return albums as [SearchItem]
        """
        album_items = []
        try:
            # Read album list
            formated = GLib.uri_escape_string(name, None, True).replace(
                                                                      ' ', '+')
            s = Gio.File.new_for_uri("https://api.spotify.com/v1/search?q=%s"
                                     "&type=album" % formated)
            (status, data, tag) = s.load_contents()
            if status:
                decode = json.loads(data.decode('utf-8'))
                # For each album, get cover and tracks
                for item in decode['albums']['items']:
                    album_item = SearchItem()
                    album_item.name = item['name']
                    album_item.is_track = False
                    album_item.cover = item['images'][0]['url']
                    album_item.smallcover = item['images'][2]['url']
                    album_spotify_id = item['id']
                    s = Gio.File.new_for_uri("https://api.spotify.com/v1/"
                                             "albums/%s" % album_spotify_id)
                    (status, data, tag) = s.load_contents()
                    if status:
                        decode = json.loads(data.decode('utf-8'))
                        for item in decode['tracks']['items']:
                            track_item = SearchItem()
                            track_item.is_track = True
                            track_item.name = item['name']
                            track_item.album = album_item.name
                            track_item.tracknumber = int(item['track_number'])
                            track_item.discnumber = int(item['disc_number'])
                            track_item.duration = int(item['duration_ms'])\
                                / 1000
                            for artist in item['artists']:
                                track_item.artists.append(artist['name'])
                            if not album_item.artists:
                                album_item.artists = track_item.artists
                            album_item.subitems.append(track_item)
                    album_items.append(album_item)
        except Exception as e:
            print("SpotifySearch::albums(): %s" % e)
        return album_items

#######################
# PRIVATE             #
#######################
