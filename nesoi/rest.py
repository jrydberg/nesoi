from twisted.web.resource import Resource
from twisted.web import server, http, client, error
from twisted.internet import defer
from twisted.python import log
from zope.interface import Interface, implements
import re
try:
    import json
except ImportError:
    import simplejson as json


class ControllerError(Exception):

    def __init__(self, responseCode):
        self.responseCode = responseCode
        self.message = None


class UnsupportedRepresentationError(ControllerError):
    """
    The given representation was not supported by the controller.
    """

    def __init__(self):
        ControllerError.__init__(self, http.UNSUPPORTED_MEDIA_TYPE)


class NoSuchResourceError(ControllerError):

    def __init__(self):
        ControllerError.__init__(self, http.NOT_FOUND)


def read_json(request):
    return json.loads(request.content.read())


def write_json(request, data, ct='application/json', rc=200):
    """
    Write JSON reponse to request.
    """
    sdata = json.dumps(data, indent=2).encode('utf-8')
    request.setHeader('content-type', ct)
    request.setHeader('content-length', len(sdata))
    request.setResponseCode(rc)
    request.write(sdata)


def compile_regexp(url_def):
    """
    Compile url defintion to a regular expression.
    """
    elements = url_def.split('/')

    l = list()
    for element in elements:
        try:
            front, rest = element.split('{', 1)
            middle, end = rest.split('}', 1)

            expr = '(?P<%s>[0-9a-zA-Z\.\-_]+)' % middle.replace('-', '_')
            l.append(''.join([front, expr, end]))
        except ValueError:
            l.append(element)

    return '/'.join(l) + '$'


class Router(Resource):
    isLeaf = True

    def __init__(self):
        self.controllers = list()

    def addController(self, controllerPath, controller):
        """
        Add router.
        """
        regexp = re.compile(compile_regexp(controllerPath))
        self.controllers.append((regexp, controller))

    def getController(self, request):
        """
        Return an initialized controller based on the given request.
        """
        controllerUrl = request.URLPath()
        postpath = list(request.postpath)
        if postpath:
            if not postpath[-1]:
                del postpath[-1]
        p = '/'.join(postpath)
        for regexp, controller in self.controllers:
            m = regexp.match(p)
            if m is not None:
                return controller, controllerUrl.click(p), m.groupdict()
        print "no matching controller", p

    def ebControl(self, reason, request):
        reason.printTraceback()
        reason.trap(ControllerError)
        request.setResponseCode(reason.value.responseCode)
        if reason.value.message is not None:
            request.setHeader('content-length', str(len(reason.value.message)))
            request.write(reason.value.message)
        else:
            request.setHeader('content-length', '0')
        request.finish()

    def ebInternal(self, reason, request):
        request.setResponseCode(http.INTERNAL_SERVER_ERROR)
        request.setHeader('content-length', '0')
        request.finish()
        return reason

    def cbControl(self, result, request):
        """
        Callback from controller method.

        C{repr} is a provider of L{IRepresentation} that should be
        rendered to the client.
        """
        rc = 200
        if type(result) == tuple:
            rc, result = result
        elif type(result) == int:
            rc = result

        if type(result) == dict:
            write_json(request, result, rc=rc)
        elif type(result) == str:
            request.setResponseCode(rc)
            request.write(result)
        else:
            request.setHeader('content-length', 0)

        request.finish()

    def render(self, request):
        """
        Render request.
        """
        controller, url, params = self.getController(request)
        if controller is None:
            request.setResponseCode(http.INTERNAL_SERVER_ERROR)
            return 'No controller found for URL'

        method = getattr(controller, request.method.lower(), None)
        if method is None:
            request.setResponseCode(http.NOT_ALLOWED)
            return ''
        input = []
        if request.method.lower() in ('post', 'put'):
            input.append(read_json(request))

        doneDeferred = defer.maybeDeferred(method, self, request, url,
                                           *input, **params)
        doneDeferred.addCallback(self.cbControl, request)
        doneDeferred.addErrback(self.ebControl, request)
        doneDeferred.addErrback(self.ebInternal, request)
        doneDeferred.addErrback(log.deferr)
        return server.NOT_DONE_YET
