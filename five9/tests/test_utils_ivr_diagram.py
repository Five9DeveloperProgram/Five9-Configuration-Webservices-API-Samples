import base64
import gzip
import unittest

from five9.utils import ivr_diagram


def _tts(text):
    raw = (
        "<speakElement><textElement><body>%s</body></textElement></speakElement>"
        % text
    )
    return base64.b64encode(gzip.compress(raw.encode("utf-8"))).decode("utf-8")


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
    <ifElse>
      <ascendants>7DF8903F3DDA41DDA3EB96BC6C5F939E</ascendants>
      <moduleName>SampleIfWithANY</moduleName>
      <locationX>311</locationX>
      <locationY>293</locationY>
      <moduleId>88E1F94302E54DC1A97A66F98ED494C5</moduleId>
      <data>
        <branches>
          <entry>
            <key>IF</key>
            <value>
              <name>IF</name>
              <desc>6A5CE2494D0F4C7FBBB8BCBC40147FCB</desc>
            </value>
          </entry>
          <entry>
            <key>ELSE</key>
            <value>
              <name>ELSE</name>
              <desc>2AA87B2576FF4B139878E298D77E0221</desc>
            </value>
          </entry>
        </branches>
        <customCondition>1 OR 2</customCondition>
        <conditionGrouping>ANY</conditionGrouping>
        <conditions>
          <comparisonType>EQUALS</comparisonType>
          <joinMode>AND</joinMode>
          <rightOperand>
            <isVarSelected>false</isVarSelected>
            <stringValue>
              <value>15</value>
              <id>0</id>
            </stringValue>
          </rightOperand>
          <leftOperand>
            <isVarSelected>true</isVarSelected>
            <variableName>__BUFFER__</variableName>
          </leftOperand>
        </conditions>
        <conditions>
          <comparisonType>EQUALS</comparisonType>
          <joinMode>AND</joinMode>
          <rightOperand>
            <isVarSelected>false</isVarSelected>
            <stringValue>
              <value>bbb</value>
              <id>0</id>
            </stringValue>
          </rightOperand>
          <leftOperand>
            <isVarSelected>true</isVarSelected>
            <variableName>sampleVarSendToFS</variableName>
          </leftOperand>
        </conditions>
      </data>
    </ifElse>
    <ifElse>
      <ascendants>88E1F94302E54DC1A97A66F98ED494C5</ascendants>
      <moduleName>IfElse16</moduleName>
      <locationX>493</locationX>
      <locationY>314</locationY>
      <moduleId>6A5CE2494D0F4C7FBBB8BCBC40147FCB</moduleId>
      <data>
        <branches>
          <entry>
            <key>IF</key>
            <value>
              <name>IF</name>
              <desc>FFF6A64147FB45B783CBF83F6AFA6ED4</desc>
            </value>
          </entry>
          <entry>
            <key>ELSE</key>
            <value>
              <name>ELSE</name>
              <desc>2AA87B2576FF4B139878E298D77E0221</desc>
            </value>
          </entry>
        </branches>
        <customCondition>(1 AND 2) AND NOT 3</customCondition>
        <conditionGrouping>CUSTOM</conditionGrouping>
        <conditions>
          <comparisonType>EQUALS</comparisonType>
          <joinMode>AND</joinMode>
          <rightOperand>
            <isVarSelected>false</isVarSelected>
            <integerValue>
              <value>15</value>
            </integerValue>
          </rightOperand>
          <leftOperand>
            <isVarSelected>true</isVarSelected>
            <variableName>Contact.AttemptsInt</variableName>
          </leftOperand>
        </conditions>
        <conditions>
          <comparisonType>LIKE</comparisonType>
          <joinMode>AND</joinMode>
          <rightOperand>
            <isVarSelected>false</isVarSelected>
            <stringValue>
              <value>something%</value>
              <id>0</id>
            </stringValue>
          </rightOperand>
          <leftOperand>
            <isVarSelected>true</isVarSelected>
            <variableName>__BUFFER__</variableName>
          </leftOperand>
        </conditions>
        <conditions>
          <comparisonType>EQUALS</comparisonType>
          <joinMode>AND</joinMode>
          <rightOperand>
            <isVarSelected>false</isVarSelected>
            <stringValue>
              <value>15</value>
              <id>0</id>
            </stringValue>
          </rightOperand>
          <leftOperand>
            <isVarSelected>true</isVarSelected>
            <variableName>__BUFFER__</variableName>
          </leftOperand>
        </conditions>
      </data>
    </ifElse>
    <hangup>
      <ascendants>6A5CE2494D0F4C7FBBB8BCBC40147FCB</ascendants>
      <moduleName>Hangup37</moduleName>
      <locationX>766</locationX>
      <locationY>281</locationY>
      <moduleId>FFF6A64147FB45B783CBF83F6AFA6ED4</moduleId>
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
  <modulesOnHangup>
    <startOnHangup>
      <singleDescendant>06D9BB08C82E41269790CD6C795D27C7</singleDescendant>
      <moduleName>StartOnHangup4</moduleName>
      <locationX>20</locationX>
      <locationY>10</locationY>
      <moduleId>B388B27C1A46451CAEC57C5D4F49BB3D</moduleId>
    </startOnHangup>
    <hangup>
      <ascendants>B388B27C1A46451CAEC57C5D4F49BB3D</ascendants>
      <moduleName>Hangup5</moduleName>
      <locationX>120</locationX>
      <locationY>10</locationY>
      <moduleId>06D9BB08C82E41269790CD6C795D27C7</moduleId>
      <data>
        <dispo>
          <id>-17</id>
          <name>Caller Disconnected</name>
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
        <overwriteDisposition>false</overwriteDisposition>
      </data>
    </hangup>
  </modulesOnHangup>
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
          <value></value>
          <id>0</id>
        </stringValue>
        <attributes>8</attributes>
        <isNullValue>true</isNullValue>
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
</ivrScript>"""


FUNCTION_IVR = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ivrScript>
  <domainId>131792</domainId>
  <properties/>
  <modules>
    <incomingCall>
      <singleDescendant>2</singleDescendant>
      <moduleName>Start</moduleName>
      <moduleId>1</moduleId>
      <data/>
    </incomingCall>
    <setVariable>
      <singleDescendant>3</singleDescendant>
      <moduleName>SetJsonValue</moduleName>
      <moduleId>2</moduleId>
      <data>
        <expressions>
          <variableName>resultVar</variableName>
          <isFunction>true</isFunction>
          <functionType>normalizePhone</functionType>
          <arguments>
            <arguments>
              <isVarSelected>true</isVarSelected>
              <variableName>rawNumber</variableName>
            </arguments>
            <arguments>
              <isVarSelected>false</isVarSelected>
              <stringValue>
                <value>US</value>
                <id>0</id>
              </stringValue>
            </arguments>
          </arguments>
        </expressions>
      </data>
    </setVariable>
    <hangup>
      <ascendants>2</ascendants>
      <moduleName>End</moduleName>
      <moduleId>3</moduleId>
      <data/>
    </hangup>
  </modules>
  <userVariables/>
  <functions>
    <entry>
      <key>ABCDEF123456</key>
      <value>
        <jsFunctionId>ABCDEF123456</jsFunctionId>
        <description>Sample helper</description>
        <returnType>STRING</returnType>
        <name>normalizePhone</name>
        <arguments>
          <arguments>
            <name>rawNumber</name>
            <description>Unformatted phone number</description>
            <type>STRING</type>
          </arguments>
          <arguments>
            <name>defaultCountry</name>
            <description></description>
            <type>STRING</type>
          </arguments>
        </arguments>
        <functionBody>H4sIAAAAAAAAACtKLSktylMwBAALoH20CAAAAA==</functionBody>
      </value>
    </entry>
  </functions>
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
</ivrScript>"""


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

    def test_ivr_to_text_documents_summary_sections(self):
        doc = ivr_diagram.ivr_to_text(SAMPLE_IVR, name="SupportFlow")
        self.assertIn("# IVR: SupportFlow", doc)
        self.assertIn("## Script Variables", doc)
        self.assertIn("No script variables defined.", doc)
        self.assertIn("## JavaScript Functions", doc)
        self.assertIn("No JavaScript functions defined.", doc)
        self.assertIn("## Foreign Scripts", doc)
        self.assertIn("No foreign scripts defined.", doc)

    def test_foreign_script_documents_summary_grouping(self):
        doc = ivr_diagram.ivr_to_text(FOREIGN_SCRIPT_IVR, name="Foreign Script Demo")
        self.assertIn("## Foreign Scripts", doc)
        self.assertIn("_fs_contactLookup", doc)
        self.assertIn("Module: ForeignScript5", doc)
        self.assertIn("Parameters:", doc)
        self.assertIn("sampleInputVarible", doc)
        self.assertIn("*{{sampleVarSendToFS}}*", doc)
        self.assertIn("sampleConstantInput", doc)
        self.assertIn("**[HELLO]**", doc)
        self.assertIn("Return Values:", doc)
        self.assertIn("someVariableToSetFromTheChildScript", doc)
        self.assertIn("*{{sampleOutputVariable}}*", doc)
        self.assertIn("## Script Variables", doc)
        self.assertIn("| Name | Default | Description |", doc)
        self.assertIn("| sampleVarSendToFS |", doc)
        self.assertIn("| sampleOutputVariable |", doc)
        self.assertEqual(doc.count("| Name | Default | Description |"), 1)

    def test_complex_ifelse_documents_row_numbers_and_expression(self):
        svg = ivr_diagram.ivr_to_svg(FOREIGN_SCRIPT_IVR, name="Complex If Demo")
        self.assertIn("1. IF __BUFFER__ EQUALS &quot;15&quot;", svg)
        self.assertIn("2. IF sampleVarSendToFS EQUALS", svg)
        self.assertIn("&quot;bbb&quot;", svg)
        self.assertIn("Grouping: ANY", svg)
        self.assertIn("Expression: 1 OR 2", svg)
        self.assertIn("1. IF Contact.AttemptsInt EQUALS", svg)
        self.assertIn("15</text>", svg)
        self.assertIn("2. IF __BUFFER__ LIKE &quot;something%&quot;", svg)
        self.assertIn("3. IF __BUFFER__ EQUALS &quot;15&quot;", svg)
        self.assertIn("Grouping: CUSTOM", svg)
        self.assertIn("Expression: (1 AND 2) AND NOT 3", svg)

    def test_function_summary_lists_arguments(self):
        doc = ivr_diagram.ivr_to_text(FUNCTION_IVR, name="Function Demo")
        self.assertIn("## JavaScript Functions", doc)
        self.assertIn("normalizePhone", doc)
        self.assertIn("Return Type: STRING", doc)
        self.assertIn("Description: Sample helper", doc)
        self.assertIn("rawNumber: STRING", doc)
        self.assertIn("defaultCountry: STRING", doc)
        self.assertIn("Used By: SetJsonValue", doc)

    def test_empty_script_raises(self):
        with self.assertRaises(ValueError):
            ivr_diagram.ivr_to_svg("<ivrScript><modules/></ivrScript>")


if __name__ == "__main__":
    unittest.main()
