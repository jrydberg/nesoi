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

from txgossip.recipies import KeyStoreMixin, LeaderElectionMixin


class KeyStore(KeyStoreMixin, LeaderElectionMixin):
    """Gossip participant that both implements our replicated
    key-value store and a leader-election mechanism.
    """

    def __init__(self, clock, storage):
        LeaderElectionMixin.__init__(self, clock)
        KeyStoreMixin.__init__(self, clock, storage, [
                self.LEADER_KEY, self.VOTE_KEY, self.PRIO_KEY])
        # The first thing we do is to start an election.
        self.start_election()
        self._is_leader = False

    def value_changed(self, peer, key, value):
        """A peer changed one of its values."""
        if key == '__heartbeat__':
            return

        print "changed", key

        if LeaderElectionMixin.value_changed(self, peer, key, value):
            # This value change was handled by the leader election
            # mixin.
            return

        # Pass it through our replication engine:
        KeyStoreMixin.value_changed(self, peer, key, value)

        if self._is_leader:
            # This peer is the leader of the cluster, which means that
            # we're responsible for firing notifications.
            if not key.startswith('watcher:'):
                self._notify(key)

        if hasattr(self._storage, "sync"):
            self._storage.sync()

    def peer_alive(self, peer):
        """The gossiper reports that C{peer} is alive."""
        self.start_election()
        self.synchronize_keys_with_peer(peer)

    def peer_dead(self, peer):
        """The gossiper reports that C{peer} is dead."""
        self.start_election()

    def leader_elected(self, is_leader, leader):
        """Leader elected."""
        if is_leader:
            print "elected leader"
        else:
            print "elected slave"
        self._is_leader = is_leader
        if is_leader:
            # Go through and possible trigger all notifications.
            for key in self.keys('app:*'):
                self._notify(key)
            for key in self.keys('srv:*'):
                self._notify(key)

    def _notify(self, key):
        """Possible notify listener that something has changed."""
        for wkey in self.keys('watcher:*'):
            watcher = self[wkey]
            if watcher is None:
                continue
            print wkey, watcher
            if (key.startswith(watcher['pattern'])
                and watcher['last-hit'] < self.timestamp_for_key(key)):
                # Trigger XXX
                print "TRIGGER", key, repr(watcher)
                watcher['last-hit'] = self.clock.seconds()
                self[wkey] = watcher
