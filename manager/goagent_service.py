import thread
import socket
import logging

import dpkt

import goagent


LOGGER = logging.getLogger(__name__)
APPIDS_COUNT = 10
enabled = True
failures_count = 0


def modified_gae_urlfetch(*args, **kwargs):
    global failures_count
    global enabled
    response = goagent.gae_urlfetch(*args, **kwargs)
    if 200 != response.app_status:
        failures_count += 1
    if failures_count > 5:
        LOGGER.error('goagent failed for more than 5 times, disable service')
        enabled = False
    return response


def monkey_patch_goagent():
    goagent.logging.info = goagent.logging.debug
    goagent.GAEProxyHandler.urlfetch = staticmethod(modified_gae_urlfetch)


monkey_patch_goagent()


def run():
    thread.start_new(start_goagent, ())


def clean():
    pass


def start_goagent():
    try:
        global enabled
        goagent.common.GAE_APPIDS = resolve_appids()
        if not goagent.common.GAE_APPIDS:
            enabled = False
            LOGGER.error("no appids, disable goagent service")
            return
        goagent.common.GAE_FETCHSERVER = '%s://%s.appspot.com%s?' % (
            goagent.common.GOOGLE_MODE, goagent.common.GAE_APPIDS[0], goagent.common.GAE_PATH)
        server = goagent.gevent.server.StreamServer(
            (goagent.common.LISTEN_IP, goagent.common.LISTEN_PORT), goagent.GAEProxyHandler)
        server.serve_forever()
    except:
        LOGGER.exception('goagent service failed')


def resolve_appids():
    appids = []
    for i in range(1, 1 + APPIDS_COUNT):
        appid = resolve_appid(i)
        if appid:
            appids.append(appid)
    return appids


def resolve_appid(index):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
        sock.settimeout(3)
        request = dpkt.dns.DNS(qd=[dpkt.dns.DNS.Q(name='goagent%s.fqrouter.com' % index, type=dpkt.dns.DNS_TXT)])
        sock.sendto(str(request), ('8.8.8.8', 53))
        data, addr = sock.recvfrom(1024)
        response = dpkt.dns.DNS(data)
        answer = response.an[0]
        appid = ''.join(e for e in answer.rdata if e.isalnum())
        LOGGER.info('resolved goagent appid %s => %s' % (index, appid))
        return appid
    except:
        LOGGER.exception('failed to resolve goagent appid %s' % index)
        return None