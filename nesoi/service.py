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

from datetime import datetime

from twisted.application import service
from twisted.web import server, resource, http
from txgossip.gossip import Gossiper
#import txgossip
from . import rest, keystore


class WebhookResourceMixin:
    """Mixin for resource controllers that want to provide webhooks
    subscriptions on their resource.

    This mixin only implements the discovery part of the webhooks.  A
    webhook resource also has to be present in the routing table.
    """

    def head(self, router, request, url, **args):
        """Response with a link to the subscriptions resource"""
        request.setHeader('Link', '%s, rel="Subscriptions"' % (
            str(url.child('web-hooks'))))
        return 200


class WebhookResourceController:

    def __init__(self, clock, keystore, keypattern):
        """."""
        self.clock = clock
        self.keystore = keystore
        self.keypattern = keypattern

    def get(self, router, request, url, hookname=None, **args):
        """."""
        if hookname is not None:
            print "hookname"
            wkey = 'watcher:%s:%s:' % (self.keypattern,
                                       hookname)
            if not wkey in self.keystore:
                raise FEL()
            watcher = self.keystore[wkey]
            if watcher is None:
                raise rest.NoSuchResourceError()
            return {
                'name': watcher['name'],
                'endpoint': watcher['endpoint']
                }

        watchers = []
        for wkey in self.keystore.keys('watcher:*'):
            print "wkey", wkey
            watcher = self.keystore[wkey]
            print "watcher", repr(watcher)
            if watcher is None:
                continue
            if watcher['pattern'] == self.keypattern:
                watchers.append(watcher)

        data = {}
        for watcher in watchers:
            data[watcher['name']] = {
                'name': watcher['name'],
                'endpoint': watcher['endpoint']
                }

        return data

    def _validate_watcher(self, config, hookname=None):
        for required in ('name', 'endpoint',):
            if not required in config:
                raise rest.ControllerError(400)
        if hookname is not None:
            if config['name'] != hookname:
                raise rest.ControllerError(400)

    def post(self, router, request, url, config, hookname=None, **args):
        """Create a web-hook watcher."""
        if hookname is not None:
            # Can not post to a watcher.
            raise rest.ControllerError(400)
        self._validate_watcher(config)

        watcher = {'name': config['name'],
            'endpoint': config['endpoint'],
            'pattern': self.keypattern,
            'last-hit': self.clock.seconds()}
        wkey = str('watcher:%s:%s' % (self.keypattern, watcher['name']))
        if wkey in self.keystore and self.keystore[wkey] is not None:
            print self.keystore.keys()
            raise rest.ControllerError(409)
        self.keystore[wkey] = watcher
        request.setHeader('location', str(url.child(watcher['name'])))
        return http.CREATED, config

    def put(self, router, request, url, config, hookname=None, **args):
        """Update an existing web-hook watcher."""
        if hookname is None:
            # We cannot put to the collection resource.
            raise rest.ControllerError(400)

        self._validate_watcher(config, hookname)
        wkey = str('watcher:%s:%s:' % (self.keypattern, hookname))
        if not wkey in self.keystore or self.keystore[wkey] is None:
            raise rest.NoSuchResourceError()

        watcher = self.keystore[wkey]
        watcher.update({
            'name': config['name'],
            'endpoint': config['endpoint']
            })
        self.keystore[wkey] = watcher
        return config

    def delete(self, router, request, url, hookname=None, **args):
        """Delete a web-hook waltcher."""
        if hookname is None:
            raise rest.ControllerError(400)

        wkey = str('watcher:%s:%s' % (self.keypattern, hookname))
        if not wkey in self.keystore or self.keystore[wkey] is None:
            raise rest.NoSuchResourceError()
        self.keystore[wkey] = None
        return http.NO_CONTENT


class ApplicationController(WebhookResourceMixin):
    """REST controller for application configurations."""

    def __init__(self, clock, keystore):
        self.clock = clock
        self.keystore = keystore

    def put(self, router, request, url, config, appname=None):
        """Update application configuration."""
        for required in ('name', 'config',):
            if not required in config:
                raise rest.ControllerError(400)
        config['updated_at'] = str(datetime.fromtimestamp(
                self.clock.seconds()))
        self.keystore['app:%s' % appname] = config
        return config

    def get(self, router, request, url, appname=None):
        """Read out application configuration."""
        key = 'app:%s' % appname
        if not key in self.keystore or self.keystore[key] is None:
            raise rest.NoSuchResourceError()
        return self.keystore[key]


class ApplicationCollectionController:
    """REST controller for listing all applications."""

    def __init__(self, keystore):
        self.keystore = keystore

    def get(self, router, request, url):
        """Read out application configuration."""
        apps = {}
        for key in self.keystore.keys():
            if key.startswith('app:'):
                app = self.keystore[key]
                if app is not None:
                    apps[app['name']] = app
        return apps


class ServiceHostController:
    """."""

    def __init__(self, clock, keystore):
        self.clock = clock
        self.keystore = keystore

    def get(self, router, request, url, srvname=None, hostname=None):
        """."""
        key = 'srv:%s:%s' % (srvname, hostname)
        if key not in self.keystore or self.keystore[key] is None:
            raise rest.NoSuchResourceError()
        return self.keystore[key]

    def put(self, router, request, url, config, srvname=None,
                hostname=None):
        """."""
        for required in ('name', 'endpoints'):
            if not required in config:
                raise rest.ControllerError(400)
        config['updated_at'] = str(datetime.fromtimestamp(
                self.clock.seconds()))
        key = 'srv:%s:%s' % (srvname, hostname)
        self.keystore[key] = config
        return config


class ServiceHostCollectionController(WebhookResourceMixin):

    def __init__(self, keystore):
        self.keystore = keystore

    def get(self, router, request, url, srvname=None):
        srvs = {}
        keypattern = 'srv:%s:*' % srvname
        for key in self.keystore.keys(keypattern):
            if self.keystore[key] is not None:
                srv = self.keystore[key]
                srvs[srv['name']] = srv
        return srvs


class ServiceCollectionController:

    def __init__(self, keystore):
        self.keystore = keystore

    def get(self, router, request, url):
        """Return a mapping of all known services."""
        keypattern = 'srv:*:*'
        services = {}
        for key in self.keystore.keys('srv:*:*'):
            if self.keystore[key] is None:
                continue
            srvname, hostname = key.split(':', 2)[1:]
            srvhost = self.keystore[key]
            if not srvname in services:
                services[srvname] = {
                    'name': srvname, 'hosts': {}
                    }
            services[srvname]['hosts'][hostname] = srvhost
        return services


class Nesoi(service.Service):

    def __init__(self, reactor, listen_addr, listen_port, storage):
        self.reactor = reactor
        self._listen_port = listen_port
        self.keystore = keystore.KeyStore(reactor, storage)
        self._protocol = Gossiper(reactor, '%s:%d' % (
                listen_addr, listen_port), self.keystore)
        self._protocol.set_local_state(
            self.keystore.PRIO_KEY, 0)
        for key in storage:
            self._protocol.set_local_state(key, storage[key])
        self.router = rest.Router()

        # Setup the application controllers:
        self.router.addController(
            'app', ApplicationCollectionController(self.keystore))
        self.router.addController(
            'app/{appname}/web-hooks', WebhookResourceController(
                self.reactor, self.keystore, 'app'))
        self.router.addController(
            'app/{appname}/web-hooks/{hookname}', WebhookResourceController(
                self.reactor, self.keystore, 'app'))
        self.router.addController(
            'app/{appname}', ApplicationController(
                self.reactor, self.keystore))

        # Setup the service controllers:
        self.router.addController(
            'srv', ServiceCollectionController(self.keystore))
        self.router.addController(
            'srv/{srvname}', ServiceHostCollectionController(self.keystore))
        self.router.addController(
            'srv/{srvname}/web-hooks', WebhookResourceController(
                self.reactor, self.keystore, 'srv'))
        self.router.addController(
            'srv/{srvname}/web-hooks/{hookname}', WebhookResourceController(
                self.reactor, self.keystore, 'srv'))
        self.router.addController(
            'srv/{srvname}/{hostname}', ServiceHostController(
                self.reactor, self.keystore))

    def startService(self):
        self.reactor.listenUDP(self._listen_port, self._protocol)
        self.reactor.listenTCP(self._listen_port, server.Site(
                self.router))
