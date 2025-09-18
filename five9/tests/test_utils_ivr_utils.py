import unittest
from five9.utils.ivr_utils import ivr_variable_usage, extract_jsfunctions_from_ivr, decompress_function_body
import base64
import zlib


class DummyIVR:
    def __init__(self, name, xmlDefinition):
        self.name = name
        self.xmlDefinition = xmlDefinition


class TestIVRUtils(unittest.TestCase):
    def test_ivr_variable_usage(self):
        xml = '<root><variableName>script.var1</variableName><variableName>script.var2</variableName></root>'
        ivrs = [DummyIVR('TestIVR', xml)]
        result = ivr_variable_usage(ivrs)
        self.assertIn('script.var1', result)
        self.assertIn('script.var2', result)

    def test_extract_jsfunctions_from_ivr(self):
        # Prepare a simple function body compressed with zlib and base64
        function_body_original = 'return 1 + 1;'  # simple JS
        compressed = zlib.compress(function_body_original.encode('utf-8'))
        b64 = base64.b64encode(compressed).decode('utf-8')
        xml = f"""
        <root>
          <functions>
            <entry>
              <value>
                <name>add</name>
                <functionBody>{b64}</functionBody>
                <arguments>
                  <arguments><name>a</name></arguments>
                  <arguments><name>b</name></arguments>
                </arguments>
              </value>
            </entry>
          </functions>
        </root>
        """
        functions = extract_jsfunctions_from_ivr(xml)
        self.assertEqual(len(functions), 1)
        self.assertEqual(functions[0]['name'], 'add')
        self.assertIn('function add(a, b)', functions[0]['js'])

    def test_decompress_function_body_invalid(self):
        self.assertIsNone(decompress_function_body('not-valid-base64'))


if __name__ == '__main__':
    unittest.main()
