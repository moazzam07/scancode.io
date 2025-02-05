# SPDX-License-Identifier: Apache-2.0
#
# http://nexb.com and https://github.com/nexB/scancode.io
# The ScanCode.io software is licensed under the Apache License version 2.0.
# Data generated with ScanCode.io is provided as-is without warranties.
# ScanCode is a trademark of nexB Inc.
#
# You may not use this software except in compliance with the License.
# You may obtain a copy of the License at: http://apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software distributed
# under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
# CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.
#
# Data Generated with ScanCode.io is provided on an "AS IS" BASIS, WITHOUT WARRANTIES
# OR CONDITIONS OF ANY KIND, either express or implied. No content created from
# ScanCode.io should be considered or used as legal advice. Consult an Attorney
# for any legal advice.
#
# ScanCode.io is a free software code scanning tool from nexB Inc. and others.
# Visit https://github.com/nexB/scancode.io for support and download.

import io
import tempfile
import uuid
from pathlib import Path
from unittest import mock

from django.test import TestCase

from scanpipe.models import CodebaseResource
from scanpipe.models import Project
from scanpipe.pipes import d2d
from scanpipe.pipes.input import copy_input
from scanpipe.pipes.input import copy_inputs
from scanpipe.tests import make_resource_file
from scanpipe.tests import package_data1


class ScanPipeD2DPipesTest(TestCase):
    data_location = Path(__file__).parent.parent / "data"

    def setUp(self):
        self.project1 = Project.objects.create(name="Analysis")

    def test_scanpipe_pipes_d2d_get_inputs(self):
        with self.assertRaises(FileNotFoundError) as error:
            d2d.get_inputs(self.project1)
        self.assertEqual("from* archive not found.", str(error.exception))

        _, input_location = tempfile.mkstemp(prefix="from-")
        self.project1.copy_input_from(input_location)

        with self.assertRaises(FileNotFoundError) as error:
            d2d.get_inputs(self.project1)
        self.assertEqual("to* archive not found.", str(error.exception))

        _, input_location = tempfile.mkstemp(prefix="to-")
        self.project1.copy_input_from(input_location)

        self.assertEqual(2, len(d2d.get_inputs(self.project1)))

    def test_scanpipe_pipes_d2d_get_resource_codebase_root(self):
        input_location = self.data_location / "codebase" / "a.txt"
        file_location = copy_input(input_location, self.project1.codebase_path)
        codebase_root = d2d.get_resource_codebase_root(self.project1, file_location)
        self.assertEqual("", codebase_root)

        to_dir = self.project1.codebase_path / "to"
        to_dir.mkdir()
        file_location = copy_input(input_location, to_dir)
        codebase_root = d2d.get_resource_codebase_root(self.project1, file_location)
        self.assertEqual("to", codebase_root)

        from_dir = self.project1.codebase_path / "from"
        from_dir.mkdir()
        file_location = copy_input(input_location, from_dir)
        codebase_root = d2d.get_resource_codebase_root(self.project1, file_location)
        self.assertEqual("from", codebase_root)

    def test_scanpipe_pipes_d2d_collect_and_create_codebase_resources(self):
        input_location = self.data_location / "codebase" / "a.txt"
        to_dir = self.project1.codebase_path / "to"
        to_dir.mkdir()
        from_dir = self.project1.codebase_path / "from"
        from_dir.mkdir()
        copy_input(input_location, to_dir)
        copy_input(input_location, from_dir)
        d2d.collect_and_create_codebase_resources(self.project1)

        self.assertEqual(4, self.project1.codebaseresources.count())
        from_resource = self.project1.codebaseresources.get(path="from/a.txt")
        self.assertEqual("from", from_resource.tag)
        to_resource = self.project1.codebaseresources.get(path="to/a.txt")
        self.assertEqual("to", to_resource.tag)

    def test_scanpipe_pipes_d2d_get_extracted_path(self):
        path = "not/an/extracted/path/"
        r1 = make_resource_file(self.project1, path)
        expected = "not/an/extracted/path/-extract/"
        self.assertEqual(expected, d2d.get_extracted_path(r1))

        path = "a.jar-extract/subpath/file.ext"
        r2 = make_resource_file(self.project1, path)
        expected = "a.jar-extract/subpath/file.ext-extract/"
        self.assertEqual(expected, d2d.get_extracted_path(r2))

    def test_scanpipe_pipes_d2d_get_extracted_subpath(self):
        path = "not/an/extracted/path/"
        self.assertEqual(path, d2d.get_extracted_subpath(path))

        path = "a.jar-extract/subpath/file.ext"
        self.assertEqual("subpath/file.ext", d2d.get_extracted_subpath(path))

        path = "a.jar-extract/subpath/b.jar-extract/subpath/file.ext"
        self.assertEqual("subpath/file.ext", d2d.get_extracted_subpath(path))

    def test_scanpipe_pipes_d2d_get_diff_ratio(self):
        resource_files = [
            self.data_location / "codebase" / "a.txt",
            self.data_location / "codebase" / "b.txt",
            self.data_location / "codebase" / "c.txt",
        ]
        copy_inputs(resource_files, self.project1.codebase_path)

        resource1 = make_resource_file(self.project1, "a.txt")
        resource2 = make_resource_file(self.project1, "b.txt")
        self.assertEqual(0.5, d2d.get_diff_ratio(resource1, resource2))

        resource3 = make_resource_file(self.project1, "c.txt")
        self.assertEqual(0.0, d2d.get_diff_ratio(resource1, resource3))

    @mock.patch("scanpipe.pipes.purldb.match_by_sha1")
    def test_scanpipe_pipes_d2d_purldb_match(self, mock_match_by_sha1):
        to_1 = make_resource_file(self.project1, "to/package.jar", sha1="abcdef")
        # The initial status will be updated to "matched-to-purldb"
        to_2 = make_resource_file(
            self.project1, "to/package.jar-extract/a.class", status="mapped"
        )
        to_3 = make_resource_file(self.project1, "to/package.jar-extract/b.class")

        package_data = package_data1.copy()
        package_data["uuid"] = uuid.uuid4()
        mock_match_by_sha1.return_value = [package_data]

        buffer = io.StringIO()
        d2d.purldb_match(self.project1, extensions=[".jar"], logger=buffer.write)
        self.assertEqual("Matching 1 .jar resources against PurlDB", buffer.getvalue())

        package = self.project1.discoveredpackages.get()
        self.assertEqual(package_data["name"], package.name)
        self.assertNotEqual(package_data["uuid"], package.uuid)

        for resource in [to_1, to_2, to_3]:
            resource.refresh_from_db()
            self.assertEqual("matched-to-purldb", resource.status)
            self.assertEqual(package, resource.discovered_packages.get())

    def test_scanpipe_pipes_d2d_get_best_path_matches_same_name(self):
        to_1 = CodebaseResource(name="package-1.0.ext", path="to/package-1.0.ext")
        to_2 = CodebaseResource(name="package-2.0.ext", path="to/package-2.0.ext")
        from_1 = CodebaseResource(name="package-1.0.ext", path="from/package-1.0.ext")
        from_2 = CodebaseResource(name="package-2.0.ext", path="from/package-2.0.ext")
        matches = [from_1, from_2]
        self.assertEqual([from_1], d2d.get_best_path_matches(to_1, matches))
        self.assertEqual([from_2], d2d.get_best_path_matches(to_2, matches))

    def test_scanpipe_pipes_d2d_get_best_path_matches_extracted_subpath(self):
        to_1 = CodebaseResource(path="to/jar-extract/a/package-1.0.ext")
        to_2 = CodebaseResource(path="to/jar-extract/a/package-2.0.ext")
        from_1 = CodebaseResource(path="from/src/a/package-1.0.ext")
        from_2 = CodebaseResource(path="from/src/a/package-2.0.ext")
        matches = [from_1, from_2]
        self.assertEqual([from_1], d2d.get_best_path_matches(to_1, matches))
        self.assertEqual([from_2], d2d.get_best_path_matches(to_2, matches))

    def test_scanpipe_pipes_d2d_get_best_path_matches(self):
        to_1 = make_resource_file(self.project1, path="to/a/b/c/file.txt")
        from_1 = make_resource_file(self.project1, path="from/source/f/i/j/file.txt")
        from_2 = make_resource_file(self.project1, path="from/source/a/b/c/file.txt")
        from_3 = make_resource_file(self.project1, path="from/q/w/e/file.txt")

        matches = [from_1, from_2, from_3]
        self.assertEqual([from_2], d2d.get_best_path_matches(to_1, matches))

        # Cannot determine the best as only the filename matches
        to_2 = make_resource_file(self.project1, path="to/x/y/z/init.jsp.readme")
        self.assertEqual(matches, d2d.get_best_path_matches(to_2, matches))

    def test_scanpipe_pipes_d2d_checksum_map(self):
        sha1 = "abcde"
        to_1 = make_resource_file(self.project1, path="to/a/b/c/file.txt", sha1=sha1)
        make_resource_file(self.project1, path="from/source/f/i/j/file.txt", sha1=sha1)
        from_2 = make_resource_file(
            self.project1, path="from/source/a/b/c/file.txt", sha1=sha1
        )
        # Matchable path but missing sha1 value
        make_resource_file(self.project1, path="from/content/a/b/c/file.txt")
        make_resource_file(self.project1, path="from/q/w/e/file.txt", sha1=sha1)

        buffer = io.StringIO()
        d2d.checksum_map(self.project1, "sha1", logger=buffer.write)
        expected = "Mapping 1 to/ resources using sha1 against from/ codebase"
        self.assertEqual(expected, buffer.getvalue())
        self.assertEqual(1, to_1.related_from.count())
        relation = to_1.related_from.get()
        self.assertEqual("sha1", relation.map_type)
        self.assertEqual(from_2, relation.from_resource)

    def test_scanpipe_pipes_d2d_java_to_class_map(self):
        from1 = make_resource_file(
            self.project1,
            path="from/flume-ng-node-1.9.0-sources.jar-extract/org/apache/flume/node/"
            "AbstractConfigurationProvider.java",
        )
        from2 = make_resource_file(
            self.project1,
            path="from-flume-ng-node-1.9.0-sources.jar-extract/org/apache/flume/WRONG/"
            "Application.java",
        )
        to1 = make_resource_file(
            self.project1,
            path="to/flume-ng-node-1.9.0.jar-extract/org/apache/flume/node/"
            "AbstractConfigurationProvider$ChannelComponent.class",
        )
        to2 = make_resource_file(
            self.project1,
            path="to/flume-ng-node-1.9.0.jar-extract/org/apache/flume/node/"
            "AbstractConfigurationProvider.class",
        )
        to3 = make_resource_file(
            self.project1,
            path="to/flume-ng-node-1.9.0.jar-extract/org/apache/flume/node/"
            "Application.class",
        )

        buffer = io.StringIO()
        d2d.java_to_class_map(self.project1, logger=buffer.write)
        expected = "Mapping 3 .class resources to .java"
        self.assertIn(expected, buffer.getvalue())

        self.assertEqual(2, self.project1.codebaserelations.count())

        r1 = self.project1.codebaserelations.get(to_resource=to1, from_resource=from1)
        self.assertEqual("java_to_class", r1.map_type)
        expected = {"from_source_root": "from/flume-ng-node-1.9.0-sources.jar-extract/"}
        self.assertEqual(expected, r1.extra_data)

        r2 = self.project1.codebaserelations.get(to_resource=to2, from_resource=from1)
        self.assertEqual("java_to_class", r2.map_type)
        expected = {"from_source_root": "from/flume-ng-node-1.9.0-sources.jar-extract/"}
        self.assertEqual(expected, r2.extra_data)

        no_relations = self.project1.codebaseresources.has_no_relation()
        self.assertIn(from2, no_relations)
        self.assertIn(to3, no_relations)
        to3.refresh_from_db()
        self.assertEqual("no-java-source", to3.status)

    def test_scanpipe_pipes_d2d_jar_to_source_map(self):
        from1 = make_resource_file(
            self.project1,
            path="from/flume-ng-node-1.9.0-sources.jar-extract/org/apache/flume/node/"
            "AbstractConfigurationProvider.java",
        )
        from2 = make_resource_file(
            self.project1,
            path="from/flume-ng-node-1.9.0-sources.jar-extract",
        )
        to1 = make_resource_file(
            self.project1,
            path="to/flume-ng-node-1.9.0.jar-extract/org/apache/flume/node/"
            "AbstractConfigurationProvider.class",
        )
        to2 = make_resource_file(
            self.project1,
            path="to/flume-ng-node-1.9.0.jar-extract/META-INF/MANIFEST.MF",
        )
        to_jar = make_resource_file(
            self.project1,
            path="to/flume-ng-node-1.9.0.jar",
        )

        d2d.java_to_class_map(self.project1)
        relation = self.project1.codebaserelations.get()
        self.assertEqual(from1, relation.from_resource)
        self.assertEqual(to1, relation.to_resource)
        self.assertEqual("java_to_class", relation.map_type)
        expected = {"from_source_root": "from/flume-ng-node-1.9.0-sources.jar-extract/"}
        self.assertEqual(expected, relation.extra_data)

        buffer = io.StringIO()
        d2d.jar_to_source_map(self.project1, logger=buffer.write)
        expected = "Mapping 1 .jar resources using jar_to_source_map"
        self.assertIn(expected, buffer.getvalue())

        self.assertEqual(2, self.project1.codebaserelations.count())
        relation = self.project1.codebaserelations.get(map_type="jar_to_source")
        self.assertEqual(from2, relation.from_resource)
        self.assertEqual(to_jar, relation.to_resource)
        to2.refresh_from_db()
        self.assertEqual("ignored-meta-inf", to2.status)

    def test_scanpipe_pipes_d2d_path_map(self):
        from1 = make_resource_file(
            self.project1,
            path="from/core/src/main/org/apache/bar/file.ext",
        )
        make_resource_file(
            self.project1,
            path="from/core/src/main/org/apache/bar/file2.ext",
        )
        to1 = make_resource_file(
            self.project1,
            path="to/apache/bar/file.ext",
        )

        buffer = io.StringIO()
        d2d.path_map(self.project1, logger=buffer.write)
        expected = "Mapping 1 to/ resources using path map against from/ codebase"
        self.assertIn(expected, buffer.getvalue())

        self.assertEqual(1, self.project1.codebaserelations.count())
        relation = self.project1.codebaserelations.get()
        self.assertEqual(from1, relation.from_resource)
        self.assertEqual(to1, relation.to_resource)
        self.assertEqual("path", relation.map_type)
        self.assertEqual({"path_score": "3/3"}, relation.extra_data)
