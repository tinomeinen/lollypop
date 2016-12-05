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
        self.__mounts = []
        self.__times = {}
        self.__cancel = Gio.Cancellable.new()
        self.__bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.__mounttracker = Gio.DBusProxy.new_sync(
                                    self.__bus, Gio.DBusProxyFlags.NONE, None,
                                    'org.gtk.vfs.Daemon',
                                    '/org/gtk/vfs/mounttracker',
                                    'org.gtk.vfs.MountTracker',
                                    None)
        GLib.timeout_add(60000, self.__scanner)

    def prevent_unmount(self, uri):
        """
            Prevent uri unmount for 60 seconds
            @param uri as str
        """
        for _time in self.__times:
            if self.__times[_time][1].find(uri) != -1:
                debug("prevent_unmount(): %s" % uri)
                del self.__times[_time]
                break

    def stop(self):
        """
            Force clean for all uris
        """
        self.__cancel.cancel()

#######################
# PRIVATE             #
#######################
    def __scanner(self):
        """
            Scanner for mounted uris
        """
        debug("__scanner()")
        try:
            self.__mounttracker.call('ListMounts', None,
                                     Gio.DBusCallFlags.NO_AUTO_START,
                                     500, self.__cancel, self.__on_list_mounts)
        except Exception as e:
            print("GvfsdFix::__scanner():", e)
            GLib.timeout_add(60000, self.__scanner)

    def __on_list_mounts(self, src, res):
        """
            Unmount result
            @param src as GObject.Object
            @param res as Gio.Task
            @param uri as str
        """
        debug("__on_list_mounts()")
        try:
            mount = None
            # Add new uris to list
            for item in src.call_finish(res)[0]:
                if not item[3].startswith("http:uri"):
                    continue
                mount = item[1]
                uri = GLib.uri_unescape_string(item[3], None)
                if mount not in self.__mounts:
                    self.__mounts.append(mount)
                    self.__times[time()] = (mount, uri)
            # Unmount old shares
            for _time in self.__times.keys():
                if time() - _time > 60:
                    (mount, uri) = self.__times[_time]
                    http = Gio.DBusProxy.new_sync(
                                    self.__bus, Gio.DBusProxyFlags.NONE, None,
                                    'org.gtk.vfs.mountpoint_http',
                                    mount,
                                    'org.gtk.vfs.Mount',
                                    self.__cancel)
                    http.call('Unmount',
                              GLib.Variant('(sou)',
                                           ('org.gtk.vfs.mountpoint_http',
                                            mount,
                                            0),),
                              Gio.DBusCallFlags.NO_AUTO_START,
                              500, self.__cancel, self.__on_unmount,
                              _time)
            GLib.timeout_add(60000, self.__scanner)
        except Exception as e:
            print("GvfsdFix::__on_list_mounts():", e)
            GLib.timeout_add(60000, self.__scanner)

    def __on_unmount(self, src, res, _time):
        """
            Check result
            @param src as GObject.Object
            @param res as Gio.Task
            @param time as int
        """
        (mount, uri) = self.__times[_time]
        debug("__on_unmount(): %s" % uri)
        try:
            f = Gio.File.new_for_uri(uri)
            # Needed to force gvfs to invalidate cache
            try:
                f.load_contents_async(None, None)
            except:
                pass
            del self.__times[_time]
            self.__mounts.remove(mount)
        except Exception as e:
            print("GvfsdFix::__on_unmount():", e)
