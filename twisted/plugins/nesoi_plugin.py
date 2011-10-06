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

from zope.interface import implements

from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker
from twisted.internet import reactor

from nesoi import service


class Options(usage.Options):

    optParameters = (
        ("listen-port", "p", 6553, "The port number to listen on."),
        ("listen-address", "a", None, "The listen address."),
        ("data-file", "d", "nesoi.data", "File to store data in."),
        ("seed", "s", None, "Address to running Nesoi instance.")
        )


class MyServiceMaker(object):
    implements(IServiceMaker, IPlugin)

    tapname = "nesoi"
    description = "coordination and configuration manager"
    options = Options

    def makeService(self, options):
        """."""
        if not options['listen-address']:
            raise usage.UsageError("listen address must be specified")
        return service.create_service(reactor, options)

serviceMaker = MyServiceMaker()
