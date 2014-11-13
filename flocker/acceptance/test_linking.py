# Copyright Hybrid Logic Ltd.  See LICENSE file for details.

"""
Tests for linking containers.
"""
from socket import error
from telnetlib import Telnet

# TODO add this to setup.py, do the whole @require Elasticsearch
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import TransportError

from twisted.python.filepath import FilePath
from twisted.trial.unittest import TestCase

from flocker.node._docker import BASE_NAMESPACE, PortMap, Unit, Volume
from flocker.testtools import loop_until

from .testtools import (assert_expected_deployment, flocker_deploy, get_nodes,
                        require_flocker_cli)

ELASTICSEARCH_INTERNAL_PORT = 9200
ELASTICSEARCH_EXTERNAL_PORT = 9200

ELASTICSEARCH_APPLICATION = u"elasticsearch"
ELASTICSEARCH_IMAGE = u"clusterhq/elasticsearch"
ELASTICSEARCH_VOLUME_MOUNTPOINT = u'/var/lib/elasticsearch'

ELASTICSEARCH_UNIT = Unit(
    name=ELASTICSEARCH_APPLICATION,
    container_name=BASE_NAMESPACE + ELASTICSEARCH_APPLICATION,
    activation_state=u'active',
    container_image=ELASTICSEARCH_IMAGE + u':latest',
    ports=frozenset([
        PortMap(internal_port=ELASTICSEARCH_INTERNAL_PORT,
                external_port=ELASTICSEARCH_EXTERNAL_PORT),
        ]),
    volumes=frozenset([
        Volume(node_path=FilePath(b'/tmp'),
               container_path=FilePath(ELASTICSEARCH_VOLUME_MOUNTPOINT)),
        ]),
)

LOGSTASH_INTERNAL_PORT = 5000
LOGSTASH_EXTERNAL_PORT = 5000

LOGSTASH_LOCAL_PORT = 9200
LOGSTASH_REMOTE_PORT = 9200

LOGSTASH_APPLICATION = u"logstash"
LOGSTASH_IMAGE = u"clusterhq/logstash"

LOGSTASH_UNIT = Unit(
    name=LOGSTASH_APPLICATION,
    container_name=BASE_NAMESPACE + LOGSTASH_APPLICATION,
    activation_state=u'active',
    container_image=LOGSTASH_IMAGE + u':latest',
    ports=frozenset([
        PortMap(internal_port=LOGSTASH_INTERNAL_PORT,
                external_port=LOGSTASH_INTERNAL_PORT),
        ]),
    volumes=frozenset([]),
)

KIBANA_INTERNAL_PORT = 8080
KIBANA_EXTERNAL_PORT = 80

KIBANA_APPLICATION = u"kibana"
KIBANA_IMAGE = u"clusterhq/kibana"

KIBANA_UNIT = Unit(
    name=KIBANA_APPLICATION,
    container_name=BASE_NAMESPACE + KIBANA_APPLICATION,
    activation_state=u'active',
    container_image=KIBANA_IMAGE + u':latest',
    ports=frozenset([
        PortMap(internal_port=KIBANA_INTERNAL_PORT,
                external_port=KIBANA_EXTERNAL_PORT),
        ]),
    volumes=frozenset([]),
)

MESSAGES = set([
    str({"firstname": "Joe", "lastname": "Bloggs"}),
    str({"firstname": "Fred", "lastname": "Bloggs"}),
])


class LinkingTests(TestCase):
    """
    Tests for linking containers.

    Similar to:
    http://doc-dev.clusterhq.com/gettingstarted/examples/linking.html

    # TODO remove the loopuntil changes
    # TODO Link to this file from linking.rst

    # TODO proper docstring
    # This has the flaw of not actually testing Kibana. It does connect the
    # linking feature - between elasticsearch and logstash, and the kibana
    # thing needs to be set up right (this test verifies that it is running)
    # We could e.g. use selenium and check that there is no error saying that
    # kibana is not connected
    """
    @require_flocker_cli
    def setUp(self):
        """
        TODO
        """
        getting_nodes = get_nodes(num_nodes=2)

        def deploy_elk(node_ips):
            self.node_1, self.node_2 = node_ips

            elk_deployment = {
                u"version": 1,
                u"nodes": {
                    self.node_1: [
                        ELASTICSEARCH_APPLICATION, LOGSTASH_APPLICATION,
                        KIBANA_APPLICATION,
                    ],
                    self.node_2: [],
                },
            }

            self.elk_deployment_moved = {
                u"version": 1,
                u"nodes": {
                    self.node_1: [LOGSTASH_APPLICATION, KIBANA_APPLICATION],
                    self.node_2: [ELASTICSEARCH_APPLICATION],
                },
            }

            self.elk_application = {
                u"version": 1,
                u"applications": {
                    ELASTICSEARCH_APPLICATION: {
                        u"image": ELASTICSEARCH_IMAGE,
                        u"ports": [{
                            u"internal": ELASTICSEARCH_INTERNAL_PORT,
                            u"external": ELASTICSEARCH_EXTERNAL_PORT,
                        }],
                        u"volume": {
                            u"mountpoint": ELASTICSEARCH_VOLUME_MOUNTPOINT,
                        },
                    },
                    LOGSTASH_APPLICATION: {
                        u"image": LOGSTASH_IMAGE,
                        u"ports": [{
                            u"internal": LOGSTASH_INTERNAL_PORT,
                            u"external": LOGSTASH_EXTERNAL_PORT,
                        }],
                        u"links": [{
                            u"local_port": LOGSTASH_LOCAL_PORT,
                            u"remote_port": LOGSTASH_REMOTE_PORT,
                            u"alias": u"es",
                        }],
                    },
                    KIBANA_APPLICATION: {
                        u"image": KIBANA_IMAGE,
                        u"ports": [{
                            u"internal": KIBANA_INTERNAL_PORT,
                            u"external": KIBANA_EXTERNAL_PORT,
                        }],
                    },
                },
            }

            flocker_deploy(self, elk_deployment, self.elk_application)

        deploying_elk = getting_nodes.addCallback(deploy_elk)
        return deploying_elk

    def test_deploy(self):
        """
        # TODO
        """
        d = assert_expected_deployment(self, {
            self.node_1: set([ELASTICSEARCH_UNIT, LOGSTASH_UNIT, KIBANA_UNIT]),
            self.node_2: set([]),
        })

        return d

    def test_elasticsearch_empty(self):
        """
        # TODO by default elasticsearch is empty
        """
        # TODO put waiting_for_es into _assertX
        waiting_for_es = self._wait_for_elasticsearch_start(node=self.node_1)

        checking_no_messages = waiting_for_es.addCallback(
            self._assert_expected_log_messages,
            node=self.node_1,
            expected_messages=set([]),
        )

        return checking_no_messages

    def test_moving_just_elasticsearch(self):
        """
        # TODO It is possible to move just elasticsearch
        """
        flocker_deploy(self, self.elk_deployment_moved, self.elk_application)

        asserting_es_moved = assert_expected_deployment(self, {
            self.node_1: set([LOGSTASH_UNIT, KIBANA_UNIT]),
            self.node_2: set([ELASTICSEARCH_UNIT]),
        })

        return asserting_es_moved

    def test_logstash_messages_in_es(self):
        """
        # TODO messages from logstash show up in es
        """
        sending_messages = self._send_messages_to_logstash(self.node_1)
        waiting_for_es = sending_messages.addCallback(
            self._wait_for_elasticsearch_start,
            node=self.node_1,
        )

        checking_messages = waiting_for_es.addCallback(
            self._assert_expected_log_messages,
            node=self.node_1,
            expected_messages=MESSAGES,
        )

        return checking_messages

    def test_linking(self):
        """
        Containers can be linked to using network ports.
        """
        sending_messages = self._send_messages_to_logstash(self.node_1)

        waiting_for_es = sending_messages.addCallback(
            self._wait_for_elasticsearch_start,
            node=self.node_1,
        )

        checking_messages = waiting_for_es.addCallback(
            self._assert_expected_log_messages,
            node=self.node_1,
            expected_messages=MESSAGES,
        )

        def test_messages_move(ignored):
            flocker_deploy(self, self.elk_deployment_moved,
                self.elk_application)

            waiting_for_es = self._wait_for_elasticsearch_start(node=self.node_2)

            assert_messages_moved = waiting_for_es.addCallback(
                self._assert_expected_log_messages,
                node=self.node_2,
                expected_messages=MESSAGES)

            return assert_messages_moved

        checking_messages.addCallback(test_messages_move)
        return checking_messages

    def _wait_for_elasticsearch_start(self, ignored=None, node=None):
        es_to_wait_for = Elasticsearch(
            hosts=[{"host": node,
                    "port": ELASTICSEARCH_EXTERNAL_PORT}])
        waiting_for_ping = loop_until(lambda: es_to_wait_for.ping())
        return waiting_for_ping

    def _assert_expected_log_messages(self, ignored, node, expected_messages):
        """
        Takes elasticsearch instance, returns log messages.

        This is bad because it'll loop until timeout if the messages don't
        come
        """
        es = Elasticsearch(hosts=[{"host": node,
                            "port": ELASTICSEARCH_EXTERNAL_PORT}])

        def get_hits():
            try:
                return len(es.search()[u'hits'][u'hits']) >= len(expected_messages)
            except TransportError:
                return False

        d = loop_until(get_hits)

        def check_same(ignored):
            hits = es.search()[u'hits'][u'hits']
            messages = set([hit[u'_source'][u'message'] for hit in hits])
            self.assertEqual(messages, expected_messages)

        d.addCallback(check_same)

        return d

    def _send_messages_to_logstash(self, node):
        """
        Logstash sometimes takes ages to start up
        """
        def get_telnet_connection_to_logstash():
            try:
                return Telnet(host=node, port=LOGSTASH_EXTERNAL_PORT)
            except error:
                return False

        waiting_for_logstash = loop_until(get_telnet_connection_to_logstash)

        def send_messages(telnet):
            for message in MESSAGES:
                telnet.write(message + "\n")

        sending_messages = waiting_for_logstash.addCallback(send_messages)
        return sending_messages
