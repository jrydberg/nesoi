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

import json

from twisted.application import service
from twisted.web import client
from twisted.python import log
from txgossip.recipies import KeyStoreMixin, LeaderElectionMixin


class _LeaderElectionProtocol(LeaderElectionMixin):
    """Private version of the leader election protocol that informs
    the application logic about election results.
    """

    def __init__(self, clock, app):
        LeaderElectionMixin.__init__(self, clock, vote_delay=2)
        self._app = app

    def leader_elected(self, is_leader, leader):
        LeaderElectionMixin.leader_elected(self, is_leader, leader)
        self._app.leader_elected(is_leader)


class ClusterNode(service.Service, KeyStoreMixin, LeaderElectionMixin):
    """Gossip participant that both implements our replicated
    key-value store and a leader-election mechanism.
    """

    def __init__(self, clock, storage, client=client):
        self.election = _LeaderElectionProtocol(clock, self)
        self.keystore = KeyStoreMixin(clock, storage,
                [self.election.LEADER_KEY, self.election.VOTE_KEY,
                 self.election.PRIO_KEY])
        self.client = client
        self.storage = storage

    def startService(self):
        self.keystore.load_from(self.storage)
        service.Service.startService(self)

    def value_changed(self, peer, key, value):
        """A peer changed one of its values."""
        if key == '__heartbeat__':
            return

        if self.election.value_changed(peer, key, value):
            # This value change was handled by the leader election
            # protocol.
            return
        self.keystore.value_changed(peer, key, value)

        if self.election.is_leader and peer.name == self.gossiper.name:
            # This peer is the leader of the cluster, which means that
            # we're responsible for firing notifications.
            if not key.startswith('watcher:'):
                self._check_notify(key)

    def make_connection(self, gossiper):
        """Make connection to gossip instance."""
        self.gossiper = gossiper
        self.election.make_connection(gossiper)
        self.keystore.make_connection(gossiper)
        self.gossiper.set(self.election.PRIO_KEY, 0)

    def peer_alive(self, peer):
        """The gossiper reports that C{peer} is alive."""
        self.election.peer_alive(peer)

    def peer_dead(self, peer):
        """The gossiper reports that C{peer} is dead."""
        self.election.peer_alive(peer)

    def leader_elected(self, is_leader):
        """Leader elected."""
        print "is leader?", is_leader
        if is_leader:
            # Go through and possible trigger all notifications.
            for key in self.keystore.keys('app:*'):
                self._check_notify(key)
            for key in self.keystore.keys('srv:*'):
                self._check_notify(key)

    def _notify(self, wkey, watcher):
        """Notification watcher about change."""
        def done(result):
            watcher['last-hit'] = self.clock.seconds()
            # Verify that the watcher has not been deleted.
            if wkey in self and self.keystore[wkey] is not None:
                self.keystore.set(wkey, watcher)
        d = self.client.getPage(str(watcher['endpoint']), method='POST',
                postdata=json.dumps({'name': watcher['name'],
                                     'uri': watcher['uri']}),
                timeout=3)
        return d.addCallback(done).addErrback(log.err)

    def _check_notify(self, key):
        """Possible notify listener that something has changed."""
        for wkey in self.keystore.keys('watcher:*'):
            watcher = self.keystore.get(wkey)
            if watcher is None:
                continue
            timestamp = self.keystore.timestamp_for_key(key)
            if (key.startswith(watcher['pattern'])
                    and watcher['last-hit'] < timestamp):
                self._notify(wkey, watcher)
