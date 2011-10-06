# Copyright 2011 Johan Rydberg
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

class ResourceModel(object):
    """Data model for the resources."""

    def __init__(self, clock, keystore):
        self.clock = clock
        self.keystore = keystore

    def apps(self):
        """Return a list of all applicaitons in the model."""
        return [key.split(':', 1)[1]
                for key in self.keystore.keys('app:*')
                if self.keystore.get(key) is not None]

    def app(self, appname):
        """Return configuration for app C{appname}."""
        key = 'app:%s' % (appname,)
        if not key in self.keystore or self.keystore.get(key) is None:
            raise ValueError('no such app: %s' % (appname,))
        return self.keystore.get(key)

    def set_app(self, appname, config):
        """Update an application."""
        key = 'app:%s' % (appname,)
        for required in ('config',):
            if not required in config:
                raise ValueError('missing field "%s" in config' % (
                        required,))
        config['updated_at'] = self.clock.seconds()
        self.keystore.set(key, config)

    def del_app(self, appname):
        """Delete application."""
        key = 'app:%s' % (appname,)
        if self.keystore.get(key) is None:
            raise ValueError('no such app: %s' % (appname,))
        self.keystore.set(key, None)

    def hosts(self, srvname):
        """Return names of all available hosts for service C{srvname}."""
        keypattern = 'srv:%s:*' % (srvname,)
        for key in self.keystore.keys(keypattern):
            if self.keystore.get(key) is not None:
                yield key.split(':', 2)[2]

    def host(self, srvname, hostname):
        """Return config for a service and hostname pair."""
        key = 'srv:%s:%s' % (srvname, hostname)
        if self.keystore.get(key) is None:
            raise ValueError('no such host: %s/%s' % (srvname, hostname))
        return self.keystore.get(key)

    def set_host(self, srvname, hostname, config):
        """Set config for a service and hostname pair."""
        key = 'srv:%s:%s' % (srvname, hostname)
        for required in ('endpoints',):
            if not required in config:
                raise ValueError('missing field "%s" in config' % (
                        required,))
        config['updated_at'] = self.clock.seconds()
        self.keystore.set(key, config)

    def del_host(self, srvname, hostname):
        """Delete a service and hostname pair."""
        key = 'srv:%s:%s' % (srvname, hostname)
        if self.keystore.get(key) is None:
            raise ValueError('no such host: %s/%s' % (srvname, hostname))
        self.keystore.set(key, None)

    def services(self):
        """Return an iterable that will yield the name of all
        available services.
        """
        services = set()
        for key in self.keystore.keys('srv:*:*'):
            if self.keystore.get(key) is None:
                continue
            srvname, hostname = key.split(':', 2)[1:]
            services.add(srvname)
        return services

    def _validate_watcher(self, config, hookname=None):
        for required in ('name', 'endpoint',):
            if not required in config:
                raise ValueError('required field "%s" is missing' % (
                    required,))
        if hookname is not None:
            if config['name'] != hookname:
                raise ValueError('name do not match')

    def _watch(self, keypattern, uri, config, hookname):
        self._validate_watcher(config, hookname)
        watcher = {
            'name': config['name'],
            'endpoint': config['endpoint'],
            'uri': uri,
            'pattern': keypattern,
            'last-hit': self.clock.seconds()
            }
        wkey = str('watcher:%s:%s' % (keypattern, watcher['name']))
        if hookname is None and self.keystore.get(wkey) is not None:
            raise ValueError("already exists")
        self.keystore.set(wkey, watcher)

    def _unwatch(self, keypattern, hookname):
        wkey = str('watcher:%s:%s' % (keypattern, hookname))
        if self.keystore.get(wkey) is None:
            raise Value("no such watcher")
        self.keystore.set(wkey, None)

    def watch_service(self, srvname, config, hookname=None):
        """Watch service C{srvname}."""
        self._watch('srv:%s' % (srvname), '/srv/%s' % (srvname), config,
                    hookname=hookname)

    def unwatch_service(self, hookname, srvname):
        """Stop watching service C{srvname}."""
        self._unwatch('srv:%s' % (srvname), hookname)

    def watch_app(self, appname, config, hookname=None):
        """Watch app config C{appname}."""
        self._watch('app:%s' % (appname), '/app/%s' % (appname), config,
                    hookname=hookname)

    def unwatch_app(self, hookname, appname):
        """Stop watching app config C{appname}."""
        self._unwatch('app:%s' % (appname), hookname)

    def service_watcher(self, srvname, hookname):
        """Return service watcher called C{hookname}."""
        wkey = str('watcher:srv:%s:%s' % (srvname, hookname))
        if self.keystore.get(wkey) is None:
            raise ValueError("no such hook")
        return self.keystore.get(wkey)

    def service_watchers(self, srvname):
        """Return all watcher for service C{srvname}."""
        for key in self.keystore.keys('watcher:srv:%s:*' % (
                                      srvname,)):
            if self.keystore.get(key) is None:
                continue
            yield self.keystore.get(key)

    def app_watcher(self, srvname, hookname):
        """Return app watcher called C{hookname}."""
        wkey = str('watcher:app:%s:%s' % (appname, hookname))
        if self.keystore.get(wkey) is None:
            raise ValueError("no such hook")
        return self.keystore.get(wkey)

    def app_watchers(self, appname):
        """Return all watcher for app config C{appname}."""
        for key in self.keystore.keys('watcher:app:%s:*' % (
                                      appname,)):
            if self.keystore.get(key) is None:
                continue
            yield self.keystore.get(key)
