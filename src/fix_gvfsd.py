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

from gi.repository import Gio, GLib

from time import time

from lollypop.utils import debug


class GvfsdFix:
    """
        Workaround https://bugzilla.gnome.org/show_bug.cgi?id=775600
    """

    def __init__(self):
        """
            Init workaround
        """
        self.__uris = []
        self.__deleting = False
        self.__bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.__mounttracker = Gio.DBusProxy.new_sync(
                                    self.__bus, Gio.DBusProxyFlags.NONE, None,
                                    'org.gtk.vfs.Daemon',
                                    '/org/gtk/vfs/mounttracker',
                                    'org.gtk.vfs.MountTracker',
                                    None)

    def add_uri(self, uri):
        """
            Add a new uri to queue
            Start queue if needed
            @param uri as str
        """
        self.__uris.append((uri, time()))
        if not self.__deleting:
            GLib.idle_add(self.__unmount_shares)

    def del_uri(self, uri):
        """
            Remove uri from queue
            @param uri as str
        """
        for (_uri, _time) in self.__uris:
            if uri == _uri:
                self.__uris.remove((uri, _time))
                break

#######################
# PRIVATE             #
#######################
    def __unmount_shares(self):
        """
            Unmount share mounted since 1 min
        """
        debug("unmount_shares()")
        if not self.__uris:
            self.__deleting = False
            return
        self.__deleting = True
        (uri, _time) = self.__uris[0]
        if time() - _time > 60:
            self.__unmount_share(uri)
        else:
            GLib.timeout_add(60000, self.__unmount_shares)

    def __unmount_share(self, uri):
        """
            Unmount share for uri
            @param uri as str
            @return unmounted as bool
        """
        debug("unmount_share(): %s" % uri)
        try:
            self.__mounttracker.call('ListMounts', None,
                                     Gio.DBusCallFlags.NO_AUTO_START,
                                     500, None, self.__on_list_mounts,
                                     uri)
        except Exception as e:
            print("GvfsdFix::__unmount_share():", e)
            GLib.idle_add(self.__unmount_shares)

    def __on_list_mounts(self, src, res, uri):
        """
            Unmount result
            @param src as GObject.Object
            @param res as Gio.Task
            @param uri as str
        """
        debug("__on_list_mounts(): %s" % uri)
        try:
            mount = None
            for item in src.call_finish(res)[0]:
                item_uri = GLib.uri_unescape_string(item[3], None)
                if item_uri.find(uri) != -1:
                    mount = item[1]
                    debug("unmount_share(): %s" % mount)
                    break

            # Uri doesn't exist, remove it
            # Can this happen?
            if mount is None:
                self.del_uri(uri)
                GLib.idle_add(self.__unmount_shares)
                return

            http = Gio.DBusProxy.new_sync(
                            self.__bus, Gio.DBusProxyFlags.NONE, None,
                            'org.gtk.vfs.mountpoint_http',
                            mount,
                            'org.gtk.vfs.Mount',
                            None)
            http.call('Unmount',
                      GLib.Variant('(sou)',
                                   ('org.gtk.vfs.mountpoint_http',
                                    mount,
                                    0),),
                      Gio.DBusCallFlags.NO_AUTO_START,
                      500, None, self.__on_unmount, uri)
        except Exception as e:
            print("GvfsdFix::__on_list_mounts():", e)
            GLib.idle_add(self.__unmount_shares)

    def __on_unmount(self, src, res, uri):
        """
            Check result
            @param src as GObject.Object
            @param res as Gio.Task
            @param uri as str
        """
        debug("__on_unmount(): %s" % uri)
        try:
            self.del_uri(uri)
            f = Gio.File.new_for_uri(uri)
            # Needed to force gvfs to invalidate cache
            try:
                f.load_contents_async(None, None)
            except:
                pass
            GLib.idle_add(self.__unmount_shares)
        except Exception as e:
            print("GvfsdFix::__on_unmount():", e)
            GLib.idle_add(self.__unmount_shares)
