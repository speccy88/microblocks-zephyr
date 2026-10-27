#!/usr/bin/env python3
"""Exercise the real workflow's fail-closed Linux test guard without CI access."""
# SPDX-License-Identifier: MPL-2.0
import ast
import io
import json
from pathlib import Path
import re
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/linux-arm64.yml'


def checked_block():
    source = WORKFLOW.read_text(encoding='utf-8')
    block = source.split('# BEGIN_CHECKED_LINUX_SUITES\n', 1)[1]
    block = block.split('# END_CHECKED_LINUX_SUITES', 1)[0]
    return textwrap.dedent(block)


def workflow_guard():
    namespace = {'__name__': 'workflow_contract_probe'}
    exec(compile(checked_block(), str(WORKFLOW), 'exec'), namespace)
    return namespace


class WorkflowContracts(unittest.TestCase):
    def test_actual_guard_executes_nested_passing_suite(self):
        class RequiredCase(unittest.TestCase):
            def test_real_assertion(self):
                self.assertEqual(5 + 7, 12)
        suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(RequiredCase)])
        result = workflow_guard()['run_checked_suite'](suite, ['RequiredCase'], stream=io.StringIO())
        self.assertEqual(result, {'tests': 1, 'skipped': 0})

    def test_actual_guard_rejects_skips(self):
        class RequiredCase(unittest.TestCase):
            @unittest.skip('missing prerequisite fixture')
            def test_missing_dependency(self):
                pass
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(RequiredCase)
        with self.assertRaisesRegex(RuntimeError, 'skipped'):
            workflow_guard()['run_checked_suite'](suite, ['RequiredCase'], stream=io.StringIO())

    def test_actual_guard_rejects_empty_missing_and_failed_suites(self):
        guard = workflow_guard()['run_checked_suite']
        with self.assertRaisesRegex(RuntimeError, 'empty'):
            guard(unittest.TestSuite(), [], stream=io.StringIO())

        class PresentCase(unittest.TestCase):
            def test_should_not_run(self):
                self.fail('Required class detection should happen before execution')
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(PresentCase)
        with self.assertRaisesRegex(RuntimeError, 'missing.*AbsentCase'):
            guard(suite, ['AbsentCase'], stream=io.StringIO())

        class FailedCase(unittest.TestCase):
            def test_failure_is_not_green(self):
                self.fail('controlled CI guard failure')
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(FailedCase)
        with self.assertRaisesRegex(RuntimeError, 'failed'):
            guard(suite, ['FailedCase'], stream=io.StringIO())

    def test_selections_have_real_nonempty_classes_and_no_broad_discovery(self):
        suites = workflow_guard()['SUITES']
        self.assertEqual(len(suites), len({filename for filename, _ in suites}))
        for filename, required in suites:
            with self.subTest(filename=filename):
                self.assertRegex(filename, r'^test_linux_[a-z0-9_]+\.py$')
                self.assertNotIn('numeric', filename)
                tree = ast.parse((ROOT / 'tests' / filename).read_text(encoding='utf-8'))
                classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
                for name in required:
                    self.assertIn(name, classes)
                    self.assertTrue(any(isinstance(node, ast.FunctionDef) and node.name.startswith('test_')
                                        or isinstance(node, ast.AsyncFunctionDef) and node.name.startswith('test_')
                                        for node in classes[name].body), name + ' has no test methods')
        required_classes = {name for _, required in suites for name in required}
        self.assertTrue({'RealSmallVMMicroDuck', 'RealPinnedEditor', 'LocalBridge',
                         'UnixGateway', 'InstallerLifecycle', 'ReleaseContracts'} <= required_classes)

    def test_source_pins_and_native_architectures_are_explicit(self):
        workflow = WORKFLOW.read_text(encoding='utf-8')
        vm = json.loads((ROOT / 'dependencies/smallvm-v417.json').read_text(encoding='utf-8'))
        ide = json.loads((ROOT / 'dependencies/ide-assets.json').read_text(encoding='utf-8'))
        self.assertIn('SMALLVM_COMMIT: ' + vm['canonical_commit'], workflow)
        self.assertIn('IDE_COMMIT: ' + ide['source_commit'], workflow)
        self.assertRegex(workflow, r'runner: ubuntu-24\.04\s+architecture: x86_64\s+elf_machine: 62')
        self.assertRegex(workflow, r'runner: ubuntu-24\.04-arm\s+architecture: aarch64\s+elf_machine: 183')
        self.assertIn('--sanitize --test', workflow)
        self.assertIn("report['binary_sha256'] == hashlib.sha256(data).hexdigest()", workflow)
        self.assertIn('build-artifacts/ide-source', workflow)
        self.assertIn('linux/arm64/bridge-requirements.txt', workflow)

    def test_inline_python_is_valid_and_commands_are_scoped(self):
        workflow = WORKFLOW.read_text(encoding='utf-8')
        blocks = re.findall(r"^          python3 - <<'PY'\n(.*?)^          PY$", workflow, flags=re.M | re.S)
        self.assertEqual(len(blocks), 4)
        for block in blocks:
            ast.parse(textwrap.dedent(block))
        self.assertNotRegex(workflow, r'(?m)^\s*(?:contents|packages|id-token):\s*write')
        self.assertNotIn('tools/validate.py', workflow)
        self.assertNotIn('test_linux_arm64_numeric', workflow)
        self.assertNotIn('deploy-pages', workflow)
        self.assertNotRegex(workflow, r'(?m)^\s*(?:sudo|ssh|scp|gh release|git push)\b')
        node_files = re.findall(r'tests/[a-z0-9_-]+(?:\.test)?\.cjs', workflow)
        self.assertGreaterEqual(len(node_files), 8)
        for filename in node_files:
            self.assertTrue((ROOT / filename).is_file(), filename)


if __name__ == '__main__':
    unittest.main()
