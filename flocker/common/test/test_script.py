# Copyright Hybrid Logic Ltd.  See LICENSE file for details.

"""Tests for :module:`flocker.common.script`."""

import io
import sys

from twisted.internet import task
from twisted.internet.defer import succeed
from twisted.python import usage
from twisted.trial.unittest import SynchronousTestCase

from zope.interface.verify import verifyClass

from flocker.common.script import (
    flocker_standard_options, FlockerScriptRunner, ICommandLineScript)

from flocker import __version__


def helpProblems(command_name, help_text):
    """Identify and return a list of help text problems.

    :param text command_name: The name of the command which should appear in the
        help text.
    :param text help_text: The full help text to be inspected.
    :return: A list of problems found with the supplied ``help_text``.
    :rtype: list
    """
    problems = []
    expected_start = b'Usage: {command}'.format(command=command_name)
    if not help_text.startswith(expected_start):
        problems.append(
            'Does not begin with {expected}. Found {actual} instead'.format(
                expected=repr(expected_start),
                actual=repr(help_text[:len(expected_start)])
            )
        )
    return problems


class FakeSysModule(object):
    """A ``sys`` like substitute.

    For use in testing the handling of `argv`, `stdout` and `stderr` by command
    line scripts.

    :ivar list argv: See ``__init__``
    :ivar stdout: A py:class:`io.BytesIO` object representing standard output.
    :ivar stderr: A py:class:`io.BytesIO` object representing standard error.
    """
    def __init__(self, argv=None):
        """Initialise the fake sys module.

        :param list argv: The arguments list which should be exposed as
            ``sys.argv``.
        """
        if argv is None:
            argv = []
        self.argv = argv
        # io.BytesIO is not quite the same as sys.stdout/stderr
        # particularly with respect to unicode handling.  So,
        # hopefully the implementation doesn't try to write any
        # unicode.
        self.stdout = io.BytesIO()
        self.stderr = io.BytesIO()


class FlockerScriptRunnerInitTests(SynchronousTestCase):
    """Tests for :py:meth:`FlockerScriptRunner.__init__`."""

    def test_sys_default(self):
        """
        `FlockerScriptRunner.sys` is `sys` by default.
        """
        self.assertIs(
            sys,
            FlockerScriptRunner(script=None, options=None).sys_module
        )

    def test_sys_override(self):
        """
        `FlockerScriptRunner.sys` can be overridden in the constructor.
        """
        dummySys = object()
        self.assertIs(
            dummySys,
            FlockerScriptRunner(script=None, options=None,
                                sys_module=dummySys).sys_module
        )

    def test_react(self):
        """
        `FlockerScriptRunner._react` is ``task.react`` by default
        """
        self.assertIs(
            task.react,
            FlockerScriptRunner(script=None, options=None)._react
        )


class FlockerScriptRunnerParseOptionsTests(SynchronousTestCase):
    """Tests for :py:meth:`FlockerScriptRunner._parseOptions`."""

    def test_parseOptions(self):
        """
        ``FlockerScriptRunner._parseOptions`` accepts a list of arguments,
        passes them to the `parseOptions` method of its ``options`` attribute
        and returns the populated options instance.
        """
        class OptionsSpy(usage.Options):
            def parseOptions(self, arguments):
                self.parseOptionsArguments = arguments

        expectedArguments = [object(), object()]
        runner = FlockerScriptRunner(script=None, options=OptionsSpy())
        options = runner._parseOptions(expectedArguments)
        self.assertEqual(expectedArguments, options.parseOptionsArguments)

    def test_parseOptionsUsageError(self):
        """
        `FlockerScriptRunner._parseOptions` catches `usage.UsageError`
        exceptions and writes the help text and an error message to `stderr`
        before exiting with status 1.
        """
        expectedMessage = b'foo bar baz'
        expectedCommandName = b'test_command'

        class FakeOptions(usage.Options):
            synopsis = 'Usage: %s [options]' % (expectedCommandName,)

            def parseOptions(self, arguments):
                raise usage.UsageError(expectedMessage)

        fake_sys = FakeSysModule()

        runner = FlockerScriptRunner(script=None, options=FakeOptions(),
                                     sys_module=fake_sys)
        error = self.assertRaises(SystemExit, runner._parseOptions, [])
        expectedErrorMessage = b'ERROR: %s\n' % (expectedMessage,)
        errorText = fake_sys.stderr.getvalue()
        self.assertEqual(
            (1, [], expectedErrorMessage),
            (error.code,
             helpProblems('test_command', errorText),
             errorText[-len(expectedErrorMessage):])
        )


class FlockerScriptRunnerMainTests(SynchronousTestCase):
    """Tests for :py:meth:`FlockerScriptRunner.main`."""

    def test_main_uses_sysargv(self):
        """
        ``FlockerScriptRunner.main`` uses ``self.sys_module.argv``.
        """
        class SpyOptions(usage.Options):
            def opt_hello(self, value):
                self.value = value

        class SpyScript(object):
            def main(self, reactor, arguments):
                self.reactor = reactor
                self.arguments = arguments
                return succeed(None)

        options = SpyOptions()
        script = SpyScript()
        sys = FakeSysModule(argv=[b"flocker", b"--hello", b"world"])

        runner = FlockerScriptRunner(
            script=script, options=options, sys_module=sys)

        class TestSystemExit(SystemExit):
            """A subclass to demonstrate that self._react has been called"""

        dummyReactor = object()

        def fakeReact(main, argv):
            """A fake version of ``task.react``

            Used to avoid running the real reactor in tests.
            """

            self.successResultOf(main(dummyReactor, *argv))
            raise TestSystemExit(0)
        runner._react = fakeReact

        self.assertRaises(TestSystemExit, runner.main)

        self.assertEqual(b"world", script.arguments.value)


class FlockerScriptTestsMixin(object):
    """Common tests for scripts that can be run via L{FlockerScriptRunner}

    :ivar ICommandLineScript script: The script class under test.
    :ivar usage.Options options: The options parser class to use in the test.
    :ivar text command_name: The name of the command represented by ``script``.
    """

    script = None
    options = None
    command_name = None

    def test_interface(self):
        """
        A script that is meant to be run by ``FlockerScriptRunner`` must
        implement ``ICommandLineScript``.
        """
        self.assertTrue(verifyClass(ICommandLineScript, self.script))

    def test_incorrect_arguments(self):
        """
        ``FlockerScriptRunner.main`` exits with status 0 and prints help to
        `stderr` if supplied with unexpected arguments.
        """
        sys = FakeSysModule(argv=[self.command_name, b'--unexpected_argument'])
        script = FlockerScriptRunner(
            self.script(), self.options(), sys_module=sys)
        error = self.assertRaises(SystemExit, script.main)
        error_text = sys.stderr.getvalue()
        self.assertEqual(
            (1, []),
            (error.code, helpProblems(self.command_name, error_text))
        )


class StandardOptionsTestsMixin(object):
    """Tests for classes decorated with ``flocker_standard_options``.

    Tests for the standard options that should be available on every flocker
    command.

    :ivar usage.Options options: The ``usage.Options`` class under test.
    """
    options = None

    def test_sys_module_default(self):
        """
        ``flocker_standard_options`` adds a ``_sys_module`` attribute which is
        ``sys`` by default.
        """
        self.assertIs(sys, self.options()._sys_module)

    def test_sys_module_override(self):
        """
        ``flocker_standard_options`` adds a ``sys_module`` argument to the
        initialiser which is assigned to ``_sys_module``.
        """
        dummy_sys_module = object()
        self.assertIs(
            dummy_sys_module,
            self.options(sys_module=dummy_sys_module)._sys_module
        )

    def test_version(self):
        """
        Flocker commands have a `--version` option which prints the current
        version string to stdout and causes the command to exit with status `0`.
        """
        sys = FakeSysModule()
        error = self.assertRaises(
            SystemExit,
            self.options(sys_module=sys).parseOptions,
            ['--version']
        )
        self.assertEqual(
            (__version__ + '\n', 0),
            (sys.stdout.getvalue(), error.code)
        )

    def test_verbosity_default(self):
        """
        Flocker commands have `verbosity` of `0` by default.
        """
        options = self.options()
        self.assertEqual(0, options['verbosity'])

    def test_verbosity_option(self):
        """
        Flocker commands have a `--verbose` option which increments the
        configured verbosity by `1`.
        """
        options = self.options()
        options.parseOptions(['--verbose'])
        self.assertEqual(1, options['verbosity'])

    def test_verbosity_option_short(self):
        """
        Flocker commands have a `-v` option which increments the configured
        verbosity by 1.
        """
        options = self.options()
        options.parseOptions(['-v'])
        self.assertEqual(1, options['verbosity'])

    def test_verbosity_multiple(self):
        """
        `--verbose` can be supplied multiple times to increase the verbosity.
        """
        options = self.options()
        options.parseOptions(['-v', '--verbose'])
        self.assertEqual(2, options['verbosity'])


@flocker_standard_options
class TestOptions(usage.Options):
    """An unmodified ``usage.Options`` subclass for use in testing."""


class FlockerStandardOptionsTests(StandardOptionsTestsMixin,
                                  SynchronousTestCase):
    """Tests for ``flocker_standard_options``

    Using a decorating an unmodified ``usage.Options`` subclass.
    """
    options = TestOptions
