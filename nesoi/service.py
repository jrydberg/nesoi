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

import shelve

from twisted.application.service import MultiService
from twisted.application.internet import TCPServer, UDPServer
from twisted.web.server import Site
from txgossip.gossip import Gossiper

from nesoi.model import ResourceModel
from nesoi.keystore import ClusterNode
from nesoi import api, rest


def create_service(reactor, options):
    """Based on options provided by the user create a service that
    will provide whatever it is that Nesoi do.
    """
    service = MultiService()

    listen_address = options['listen-address']

    storage = shelve.open(options['data-file'], writeback=True)
    cluster_node = ClusterNode(reactor, storage)
    service.addService(cluster_node)

    model = ResourceModel(reactor, cluster_node.keystore)

    gossiper = Gossiper(reactor, cluster_node, listen_address)
    if options['seed']:
        gossiper.seed([options['seed']])

    service.addService(UDPServer(int(options['listen-port']), gossiper,
        interface=listen_address))

    router = rest.Router()
    router.addController('app', api.ApplicationCollectionResource(model))
    router.addController('app/{appname}/web-hooks', api.WebhookCollectionResource(model, 'appname', 'app'))
    router.addController('app/{appname}/web-hooks/{hookname}', api.WebhookResource(model, 'appname', 'app'))
    router.addController('app/{appname}', api.ApplicationResource(model))
    router.addController('srv', api.ServiceCollectionResource(model))
    router.addController('srv/{srvname}', api.ServiceHostCollectionResource(model))
    router.addController('srv/{srvname}/web-hooks', api.WebhookCollectionResource(model, 'srvname', 'service'))
    router.addController('srv/{srvname}/web-hooks/{hookname}', api.WebhookResource(model, 'srvname', 'service'))
    router.addController('srv/{srvname}/{hostname}', api.ServiceHostResource(model))

    service.addService(TCPServer(int(options['listen-port']), Site(router),
        interface=listen_address))

    #gossiper.set(cluster_node.election.PRIO_KEY, 0)
    #cluster_node.keystore.load_from(storage)

    return service
