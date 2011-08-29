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

from twisted.application import service
from twisted.web import server, resource
from txgossip.recipies import KeyStoreMixin, LeaderElectionMixin
import txgossip
from nosio import rest


class Participant(KeyStoreMixin, LeaderElectionMixin):

    def __init__(self, clock, storage):
        LeaderElectionMixin.__init__(self, clock)
        KeyStoreMixin.__init__(self, clock, storage, [
                self.LEADER_KEY, self.VOTE_KEY, self.PRIO_KEY])
        # The first thing we do is to start an election.
        self.start_election()
        self._is_leader = False

    def value_changed(self, peer, key, value):
        """A peer changed one of its values."""
        if LeaderElectionMixin.value_changed(self, peer, key, value):
            # This value change was handled by the leader election
            # mixin.
            return

        # Pass it through our replication engine:
        KeyStoreMixin.value_changed(self, peer, key, value)
        
        if self._is_leader:
            # This peer is the leader of the cluster, which means that
            # we're responsible for firing notifications.
            pass
        
    def peer_alive(self, peer):
        """The gossiper reports that C{peer} is alive."""
        self.start_election()
        self.synchronize_keys_with_peer(peer)

    def peer_dead(self, peer):
        """The gossiper reports that C{peer} is dead."""
        self.start_election()

    def leader_elected(self, is_leader, leader):
        """Leader elected."""
        self._is_leader = is_leader
        if is_leader:
            # Go through and possible trigger all notifications.
            pass
        

class ApplicationController:

    def __init__(self, keystore):
        self.keystore = keystore

    def put(self, request, url, appname=None):
        """Update application configuration."""
        config = rest.read_json(request)
        for required in ('name', 'configuration',):
            if not required in config:
                raise rest.ControllerError(400)

        key = 'app:%s' % appname
        timestamp = str(datetime.datetime.fromtimestamp(
                self.clock.seconds()))

        response_code = 200
        if not key in self.keystore:
            response_code=201
            config['created_at'] = timestamp
        config['updated_at'] = timestamp
        config['name'] = appname

        rest.write_json(request, config, rc=response_code)
    post = put

    def get(self, request, url, appname=None):
        """Read out application configuration."""
        key = 'app:%s' % appname
        try:
            config = self.keystore[key]
        except KeyError:
            raise rest.NoSuchResourceError()
        rest.write_json(request, config)


class ApplicationCollectionController:

    def __init__(self, keystore):
        self.keystore = keystore

    def get(self, request, url):
        """Read out application configuration."""
        apps = []
        for key in self.keystore.keys():
            if key.startswith('app:'):
                apps.append(self.keystore[key])
        rest.write_json(request, {'apps': apps})


class ServiceHostController:

    def __init__(self, keystore):
        self.keystore = keystore

    def get(self, request, url, srvname=None, hostname=None):
        if hostname == ':master':
            master_key = 'srv:%s:__master__' % srvname
            if not master_key in self.keystore:
                raise rest.NoSuchResourceError()
            hostname = self.keystore[master_key]
        key = 'srv:%s:%s' % (srvname, hostname)
        if key not in self.keystore:
            raise rest.NoSuchResourceError()

        config = dict(self.keystore[key])
        rest.write_json(request, config)

    def put(self, request, url, srvname=None, hostname=None):
        """.
        """
        for required in ('name', 'configuration',):
            if not required in config:
                raise rest.ControllerError(400)
        data = read_json(request)
        update_master = hostname == ':master'
        if update_master:
            hostname = data['name']

        key = 'srv:%s:%s' % (srvname, hostname)
        timestamp = self.clock.seconds()
        data['updated_at'] = timestamp
        if not key in self.keystore:
            data['created_at'] = timestamp
        self.keystore[key] = data

            master_key = 'srv:%s:__master__' % srvname
            if self.keystore.get(master_key) != hostname:
                self.keystore[master_key] = hostname

        rest.write_json(request, config)


class ServiceController:

    def __init__(self, keystore):
        self.keystore = keystore

    def get(self, request, url, srvname=None):
        key = 'srv:%s:' % srvname
        for key in self.keystore.keys():
            if key == 'srv:%s:__master__' % srvname:
                # ignore the master record.
                continue
            if key.startswith(srvname):
                apps.append(self.keystore[key])
                

        key = 'srv:%s' % appname
        try:
            config = self.keystore[key]
        except KeyError:
            raise rest.NoSuchResourceError()
        rest.write_json(request, config)




class Lemek(service.Service):

    def __init__(self, reactor, listen_addr, listen_port):
        service.Service.__init__(self)
        self.reactor = reactor
        self._listen_port = listen_port
        self.participant = Participant(reactor)
        self._protocol = txgossip.Gossiper(reactor, '%s:%d' % (
                listen_addr, listen_port), self.participant)

    def startService(self):
        self.reactor.listenUDP(self._listen_port, self._protocol)
        self.reactor.listenTCP(self._listen_port, server.Site(
                self._resource))
