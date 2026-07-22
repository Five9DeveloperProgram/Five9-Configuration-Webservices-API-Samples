import base64
import gzip
import unittest

from five9.utils import ivr_diagram


def _tts(text):
    """Build a gzip+Base64 encoded speakElement payload like the API returns."""
    raw = (
        "<speakElement><textElement><body>%s</body></textElement></speakElement>"
        % text
    )
    return base64.b64encode(gzip.compress(raw.encode("utf-8"))).decode("utf-8")


# A minimal but representative IVR: incomingCall -> play (with TTS) -> hangup.
SAMPLE_IVR = """<?xml version="1.0" encoding="UTF-8"?>
<ivrScript>
  <modules>
    <incomingCall>
      <moduleName>Start</moduleName>
      <moduleId>1</moduleId>
      <singleDescendant>2</singleDescendant>
    </incomingCall>
    <play>
      <moduleName>Greeting</moduleName>
      <moduleId>2</moduleId>
      <singleDescendant>3</singleDescendant>
      <data>
        <prompts>
          <prompt>
            <ttsPrompt><xml>%s</xml></ttsPrompt>
          </prompt>
        </prompts>
      </data>
    </play>
    <hangup>
      <moduleName>End</moduleName>
      <moduleId>3</moduleId>
    </hangup>
  </modules>
</ivrScript>""" % _tts("Welcome to support")

FOREIGN_SCRIPT_IVR = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ivrScript>
  <domainId>131792</domainId>
  <properties/>
  <modules>
    <incomingCall>
      <singleDescendant>7DF8903F3DDA41DDA3EB96BC6C5F939E</singleDescendant>
      <moduleName>IncomingCall4</moduleName>
      <locationX>128</locationX>
      <locationY>139</locationY>
      <moduleId>D9DED4ED05BE486B873DCF6DC3194719</moduleId>
      <data/>
    </incomingCall>
    <foreignScript>
      <ascendants>D9DED4ED05BE486B873DCF6DC3194719</ascendants>
      <singleDescendant>2AA87B2576FF4B139878E298D77E0221</singleDescendant>
      <moduleName>ForeignScript5</moduleName>
      <locationX>246</locationX>
      <locationY>139</locationY>
      <moduleId>7DF8903F3DDA41DDA3EB96BC6C5F939E</moduleId>
      <data>
        <ivrScript>
          <id>300000000000063</id>
          <name>_fs_contactLookup</name>
        </ivrScript>
        <passCRM>true</passCRM>
        <returnCRM>true</returnCRM>
        <params>
          <entry>
            <key>sampleInputVarible</key>
            <value>
              <isVarSelected>true</isVarSelected>
              <variableName>sampleVarSendToFS</variableName>
            </value>
          </entry>
          <entry>
            <key>sampleConstantInput</key>
            <value>
              <isVarSelected>false</isVarSelected>
              <stringValue>
                <value>HELLO</value>
                <id>0</id>
              </stringValue>
            </value>
          </entry>
        </params>
        <returnVals>
          <entry>
            <key>someVariableToSetFromTheChildScript</key>
            <value>sampleOutputVariable</value>
          </entry>
        </returnVals>
        <isConsistent>true</isConsistent>
      </data>
    </foreignScript>
    <hangup>
      <ascendants>7DF8903F3DDA41DDA3EB96BC6C5F939E</ascendants>
      <moduleName>Hangup24</moduleName>
      <locationX>391</locationX>
      <locationY>147</locationY>
      <moduleId>2AA87B2576FF4B139878E298D77E0221</moduleId>
      <data>
        <dispo>
          <id>0</id>
          <name>No Disposition</name>
        </dispo>
        <returnToCallingModule>true</returnToCallingModule>
        <errCode>
          <isVarSelected>false</isVarSelected>
          <integerValue>
            <value>0</value>
          </integerValue>
        </errCode>
        <errDescription>
          <isVarSelected>false</isVarSelected>
          <stringValue>
            <value></value>
            <id>0</id>
          </stringValue>
        </errDescription>
        <overwriteDisposition>true</overwriteDisposition>
      </data>
    </hangup>
  </modules>
  <userVariables>
    <entry>
      <key>sampleVarSendToFS</key>
      <value>
        <name>sampleVarSendToFS</name>
        <description></description>
        <stringValue>
          <value></value>
          <id>0</id>
        </stringValue>
        <attributes>192</attributes>
        <isNullValue>true</isNullValue>
      </value>
    </entry>
    <entry>
      <key>sampleOutputVariable</key>
      <value>
        <name>sampleOutputVariable</name>
        <description></description>
        <stringValue>
          <value>a varialbe with a default value</value>
          <id>0</id>
        </stringValue>
        <attributes>192</attributes>
        <isNullValue>false</isNullValue>
      </value>
    </entry>
  </userVariables>
  <multiLanguagesPrompts/>
  <multiLanguagesVIVRPrompts/>
  <multiLanguagesTextPrompts/>
  <multiLanguagesMenuChoices/>
  <multiLanguagesEwtAnnouncement/>
  <languages/>
  <functions/>
  <defaultLanguage>en-US</defaultLanguage>
  <defaultMethod>GET</defaultMethod>
  <defaultFetchTimeout>5</defaultFetchTimeout>
  <showLabelNames>true</showLabelNames>
  <defaultVivrTimeout>5</defaultVivrTimeout>
  <unicodeEncoding>true</unicodeEncoding>
  <useShortcut>false</useShortcut>
  <resetErrorCode>true</resetErrorCode>
  <showAllChannelPrompts>false</showAllChannelPrompts>
  <extContactFieldsInput>true</extContactFieldsInput>
  <extContactFieldsOutput>true</extContactFieldsOutput>
  <useIvrTimeZoneInAssignment>true</useIvrTimeZoneInAssignment>
  <timeoutInMilliseconds>3600000</timeoutInMilliseconds>
  <version>1300001</version>
</ivrScript>
"""


class TestIVRDiagram(unittest.TestCase):
    def test_parse_ivr_nodes_and_edges(self):
        nodes, edges = ivr_diagram.parse_ivr(SAMPLE_IVR)
        self.assertEqual(len(nodes), 3)
        self.assertEqual(len(edges), 2)
        self.assertEqual(nodes["1"]["tag"], "incomingCall")

    def test_decoded_tts_prompt_present(self):
        nodes, _ = ivr_diagram.parse_ivr(SAMPLE_IVR)
        self.assertIn('"Welcome to support"', nodes["2"]["body"])

    def test_ivr_to_svg_is_valid_svg(self):
        svg = ivr_diagram.ivr_to_svg(SAMPLE_IVR)
        self.assertTrue(svg.lstrip().startswith("<svg"))
        self.assertIn("</svg>", svg)
        self.assertIn("Greeting", svg)

    def test_ivr_to_text_documents_modules_and_transitions(self):
        doc = ivr_diagram.ivr_to_text(SAMPLE_IVR, name="SupportFlow")
        self.assertIn("# IVR: SupportFlow", doc)
        self.assertIn("Greeting", doc)
        self.assertIn("Welcome to support", doc)
        self.assertIn("-> **End**", doc)

    def test_foreign_script_documents_inputs_and_outputs(self):
        doc = ivr_diagram.ivr_to_text(FOREIGN_SCRIPT_IVR, name="Inbound Demo")
        self.assertIn("Script: _fs_contactLookup", doc)
        self.assertIn("Pass CRM: true", doc)
        self.assertIn("Return CRM: true", doc)
        self.assertIn("Input: sampleInputVarible <- *{{sampleVarSendToFS}}*", doc)
        self.assertIn("Input: sampleConstantInput <- **[HELLO]**", doc)
        self.assertIn("Output: someVariableToSetFromTheChildScript -> *{{sampleOutputVariable}}*", doc)
        self.assertIn("## Script Variables", doc)
        self.assertIn("**sampleVarSendToFS**", doc)
        self.assertIn("**sampleOutputVariable**", doc)
        self.assertIn("- Default: a varialbe with a default value", doc)
    def test_foreign_script_svg_includes_input_and_output_labels(self):
        svg = ivr_diagram.ivr_to_svg(FOREIGN_SCRIPT_IVR)
        self.assertIn("sampleInputVarible", svg)
        self.assertIn("{{sampleVarSendToFS}}", svg)
        self.assertIn("sampleConstantInput", svg)
        self.assertIn("[HELLO]", svg)
        self.assertIn("someVariableToSetFromTheChildScript", svg)
        self.assertIn("{{sampleOutputVariable}}", svg)

    def test_empty_script_raises(self):
        with self.assertRaises(ValueError):
            ivr_diagram.ivr_to_svg("<ivrScript><modules/></ivrScript>")


if __name__ == "__main__":
    unittest.main()
