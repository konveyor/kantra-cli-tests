import unittest

from output import trim_incident_uri

class TestTrimMethods(unittest.TestCase):
    """
        Testing `trim_incident_uri` method to making files-based atributes unique across platforms and containers,
        it looked it become too fragile, so better have tests for it.
    """

    samples = [
        # [uri, root_path, expected result]
        [
            # container prefix
            "file:///opt/input/source/src/main/resources/persistence.properties",
            "/home/runner/work/kantra-cli-tests/kantra-cli-tests/data/tmp/tackle-testap-public-cloud-readiness",
            "src/main/resources/persistence.properties"
        ],
        [
            # containerless input root prefix
            "file:///home/runner/work/kantra-cli-tests/kantra-cli-tests/data/tmp/tackle-testap-public-cloud-readiness/src/main/resources/persistence.properties",
            "/home/runner/work/kantra-cli-tests/kantra-cli-tests/data/tmp/tackle-testap-public-cloud-readiness",
            "src/main/resources/persistence.properties"
        ],
        [
            # containerless CI windows input root prefix
            r'D:\a\kantra-cli-tests\kantra-cli-tests\data\tmp\tackle-testap-public-cloud-readiness\src\main\resources\persistence.properties',
            r'D:\a\kantra-cli-tests\kantra-cli-tests\data\tmp\tackle-testap-public-cloud-readiness',
            'src/main/resources/persistence.properties'
        ],
        [
            # containerless local win10
            "file:///C:/Users/SomeUser/mig/kantra-cli-tests/data/tmp/tackle-testap-public-cloud-readiness/src/main/resources/persistence.properties",
            "C:/Users/SomeUser/mig/kantra-cli-tests/data/tmp/tackle-testap-public-cloud-readiness",
            "src/main/resources/persistence.properties"
        ],
        [
            # m2/repository pivot
            "file:///root/.m2/repository/io/konveyor/demo/configuration-utils/1.0.0/io/konveyor/demo/config/ApplicationConfiguration.java",
            "",
            "m2/repository/io/konveyor/demo/configuration-utils/1.0.0/io/konveyor/demo/config/ApplicationConfiguration.java"
        ],
        [
            # m2/repository pivot Windows
            "C://Users//runneradmin//.m2//repository//io//konveyor//demo//configuration-utils//1.0.0//io//konveyor//demo//config//ApplicationConfiguration.java",
            "",
            "m2/repository/io/konveyor/demo/configuration-utils/1.0.0/io/konveyor/demo/config/ApplicationConfiguration.java"
        ],
        [
            # binary java-project
            "/opt/input/something/java-project-dGGptYWPwMpfixya/src/main/java/weblogic/transaction/TxHelper.java",
            "",
            "src/main/java/weblogic/transaction/TxHelper.java"
        ],
        [
            # binary exploded
            "/tmp/java-project/jee-example-services-jar-exploded/META-INF/weblogic-ejb-jar.xml",
            "",
            "binary-exploded/META-INF/weblogic-ejb-jar.xml"
        ]
    ]

    def test_trim(self):
        for sample in self.samples:
            print("Trimming `%s`" % sample[0])
            self.assertEqual(trim_incident_uri(sample[0], sample[1]), sample[2])

if __name__ == '__main__':
    unittest.main()
