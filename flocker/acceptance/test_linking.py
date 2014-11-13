# Copyright Hybrid Logic Ltd.  See LICENSE file for details.

"""
Tests for linking containers.
"""
from socket import error
from telnetlib import Telnet
from time import sleep

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


class LinkingTests(TestCase):
    """
    Tests for linking containers.

    Similar to:
    http://doc-dev.clusterhq.com/gettingstarted/examples/linking.html

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
        waiting_for_es = self._wait_for_elasticsearch_start(self.node_1)

        checking_no_messages = waiting_for_es.addCallback(lambda _:
            self.assertEqual(set([]), self._get_log_messages(self.node_1))
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

    def test_linking(self):
        """
        Containers can be linked to using network ports.
        """
        def get_telnet_connection_to_logstash():
            try:
                return Telnet(host=self.node_1, port=LOGSTASH_EXTERNAL_PORT)
            except error:
                return False

        waiting_for_logstash = loop_until(get_telnet_connection_to_logstash)

        messages = set([
            str({"firstname": "Joe", "lastname": "Bloggs"}),
            str({"firstname": "Fred", "lastname": "Bloggs"}),
        ])

        def send_messages(telnet):
            for message in messages:
                telnet.write(message + "\n")

        sending_messages = waiting_for_logstash.addCallback(send_messages)

        def get_hits_node_1():
            # TODO merge this with the other one?
            es = Elasticsearch(hosts=[{"host": self.node_1,
                                "port": ELASTICSEARCH_EXTERNAL_PORT}])
            try:
                return len(es.search()[u'hits'][u'hits']) >= len(messages)
            except TransportError:
                return False

        waiting_for_es = sending_messages.addCallback(
            lambda _: self._wait_for_elasticsearch_start(self.node_1))
        d = waiting_for_es.addCallback(lambda _: loop_until(get_hits_node_1))

        def rest_of_test(ignored):
            self.assertEqual(messages, self._get_log_messages(self.node_1))

            flocker_deploy(self, self.elk_deployment_moved, self.elk_application)

            waiting_for_es = self._wait_for_elasticsearch_start(self.node_2)

            def node_2_get_hits():
                es_node_2 = Elasticsearch(
                    hosts=[{"host": self.node_2, "port": ELASTICSEARCH_EXTERNAL_PORT}])
                try:
                    return len(es_node_2.search()[u'hits'][u'hits']) >= len(messages)
                except TransportError:
                    return False
            getting_hits = waiting_for_es.addCallback(
                lambda _: loop_until(node_2_get_hits)
            )
            assert_messages_moved = getting_hits.addCallback(
                lambda _: self.assertEqual(messages, self._get_log_messages(self.node_2)))
            return assert_messages_moved

        d.addCallback(rest_of_test)
        return d

    def _wait_for_elasticsearch_start(self, node):
        es_to_wait_for = Elasticsearch(
            hosts=[{"host": node,
                    "port": ELASTICSEARCH_EXTERNAL_PORT}])
        waiting_for_ping = loop_until(lambda: es_to_wait_for.ping())
        return waiting_for_ping

    def _get_log_messages(self, node):
        """
        Takes elasticsearch instance, returns log messages.
        """
        # TODO get_elasticsearch helper function
        # TODO turn this into _assert_expected_log_messages
        es = Elasticsearch(hosts=[{"host": node,
                        "port": ELASTICSEARCH_EXTERNAL_PORT}])
        hits = es.search()[u'hits'][u'hits']
        return set([hit[u'_source'][u'message'] for hit in hits])
