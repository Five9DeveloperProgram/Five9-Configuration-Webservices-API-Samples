#!/usr/bin/env python3
"""ivr_diagram.py -- Five9 IVR script -> styled SVG call-flow (+ text docs).

Adapted for this library from a standalone utility originally written by a
Five9 colleague (``five9_to_lucid.py``). The original took a ``.five9ivr`` file
on disk; the contents of that file are byte-for-byte identical to the
``xmlDefinition`` string this library already pulls via ``getIVRScripts`` and
stores in ``domain_snapshots/{domain}/ivrs/{name}.json``. This module is
therefore reshaped around a string-in/string-out core:

    from five9.utils import ivr_diagram
    svg = ivr_diagram.ivr_to_svg(ivr.xmlDefinition)
    doc = ivr_diagram.ivr_to_text(ivr.xmlDefinition, name=ivr.name)

The SVG is designed to be passed verbatim to Lucidchart via the Lucid
connector's ``lucid_convert_svg_to_diagram`` tool (well under Lucid's 256KB
limit for typical scripts). This module intentionally does NOT talk to Lucid
directly -- it only produces the artifact.

Pipeline notes (from the original):
  - Parses all modules + modulesOnHangup; decodes gzip+Base64 TTS prompts
    (text, {variables}, [File: name] in spoken order); drops self-loops
    and dangling descendant references.
  - Shape/color per module type (STYLE map); unknown types -> gray + flag.
  - Branch-port boxes for every case/ifElse/menu/answerMachine exit, with
    matched value / DTMF digit.
  - Exception handlers are drawn as their own explicit, labeled red exit port
    (mirroring branch ports) rather than an unlabeled second arrow.
  - An on-canvas legend (only the module types actually used) and an optional
    title block (IVR name + module/transition counts) make the SVG
    self-explanatory once exported to Lucid.
  - Layout: per-connected-component Sugiyama-lite (longest-path layering,
    barycenter ordering, drift-free relaxation, chain snapping). Main flow
    left; ON-HANGUP FLOW and UNREFERENCED MODULE components in a side column.
  - Routing: straight verticals preferred; collision-checked 90-degree jogs
    otherwise. Exceptional paths drawn red.

CLI (backward compatible with the original):
    python3 -m five9.utils.ivr_diagram input.five9ivr output.svg
    python3 -m five9.utils.ivr_diagram captured_ivr.json output.svg
"""
import sys, os, re, base64, gzip, html, json
import xml.etree.ElementTree as ET
from collections import defaultdict

# ---------------- shape/color mapping ----------------
# kind: rect | round | diamond | hexagon | ellipse | circle | parallelogram |
#       trapezoid | pentagon | chevron | manual | cylinder | document | card | dblbar
STYLE = {
    'incomingCall':      ('ellipse',       '#CCEEE9'),
    'startOnHangup':     ('ellipse',       '#CCEEE9'),
    'play':              ('round',         '#D7EAD3'),
    'getDigits':         ('manual',        '#EAF1C8'),
    'input':             ('manual',        '#E3EEA8'),
    'recording':         ('manual',        '#F1E4C8'),
    'case':              ('diamond',       '#FFF2CC'),
    'menu':              ('diamond',       '#FFE9B8'),
    'answerMachine':     ('diamond',       '#CCE5EC'),
    'ifElse':            ('hexagon',       '#FCE3C2'),
    'iterator':          ('hexagon',       '#E8DCF2'),
    'setVariable':       ('rect',          '#E6E6E6'),
    'lookupCRMRecord':   ('cylinder',      '#D6E4F7'),
    'crmUpdate':         ('cylinder',      '#BFD7F2'),
    'systemUpdate':      ('cylinder',      '#C6E0C6'),
    'systemInfo':        ('document',      '#DDEAF6'),
    'query':             ('document',      '#DAD4EE'),
    'thirdPartyTransfer':('pentagon',      '#E7D9F0'),
    'agentTransfer':     ('trapezoid',     '#DCE0F2'),
    'skillTransfer':     ('chevron',       '#CFD8F0'),
    'ivaTransfer':       ('chevron',       '#CFE8DA'),
    'voiceMailTransfer': ('parallelogram', '#F5DCE8'),
    'language':          ('dblbar',        '#FCE0D6'),
    'foreignScript':     ('card',          '#DDE3E8'),
    'setDNC':            ('rect',          '#F8D8C9'),
    'hangup':            ('circle',        '#F4CCCC'),
    'PORT':              ('round',         '#FFF3D0'),
    'PORT_EXC':          ('round',         '#FBE3E0'),
}
DEFAULT_STYLE = ('rect', '#EFEFEF')

# Friendly labels for the on-canvas legend (falls back to the raw tag).
LEGEND_NAMES = {
    'incomingCall': 'Incoming call', 'startOnHangup': 'On-hangup start',
    'play': 'Play prompt', 'getDigits': 'Get digits', 'input': 'Input (omni)',
    'recording': 'Record audio', 'case': 'Case / switch', 'menu': 'Menu',
    'answerMachine': 'Answer machine', 'ifElse': 'If / else',
    'iterator': 'Iterator (loop)', 'setVariable': 'Set variable',
    'lookupCRMRecord': 'CRM lookup', 'crmUpdate': 'CRM update',
    'systemUpdate': 'System update', 'systemInfo': 'System info / lookup',
    'query': 'Web query', 'thirdPartyTransfer': '3rd-party transfer',
    'agentTransfer': 'Agent transfer', 'skillTransfer': 'Skill transfer',
    'ivaTransfer': 'IVA / bot transfer', 'voiceMailTransfer': 'Voicemail',
    'language': 'Language', 'foreignScript': 'Foreign Script',
    'setDNC': 'Set DNC', 'hangup': 'Hangup', 'PORT': 'Branch exit',
    'PORT_EXC': 'Exception exit',
}

def is_port(tag):
    return tag.startswith('PORT')

def sanitize(s):
    if s is None: return ''
    repl = {'‘':"'", '’':"'", '“':'"', '”':'"',
            '–':'-', '—':'-', '…':'...', '→':'->',
            ' ':' '}
    for k,v in repl.items(): s = s.replace(k,v)
    try:
        import unicodedata
        s = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode('ascii')
    except Exception: pass
    return s.strip()

def wrap(line, width=34):
    words = line.split()
    out, cur = [], ''
    for w in words:
        if len(cur)+len(w)+1 <= width: cur = (cur+' '+w).strip()
        else:
            if cur: out.append(cur)
            while len(w) > width: out.append(w[:width]); w = w[width:]
            cur = w
    if cur: out.append(cur)
    return out or ['']

def format_foreign_value(value, is_variable):
    value = sanitize(value or '?')
    if is_variable:
        return '*{{%s}}*' % value
    return '**[%s]**' % value

def script_variable_default(value_el):
    if value_el is None:
        return '?'
    for tag in ('stringValue', 'integerValue', 'booleanValue', 'dateValue', 'kvListValue', 'listValue'):
        value = value_el.findtext('%s/value' % tag)
        if value is not None:
            return sanitize(value)
    return sanitize(value_el.findtext('name') or '?')

def script_variable_summary_lines(entry):
    var_name = entry.findtext('key') or entry.findtext('value/name') or '?'
    value_el = entry.find('value')
    description = sanitize(value_el.findtext('description') if value_el is not None else '')
    default_value = script_variable_default(value_el)
    is_null = value_el.findtext('isNullValue') if value_el is not None else None
    default_text = '%s%s' % (default_value, ' (null)' if is_null == 'true' else '')
    return '| %s | %s | %s |' % (sanitize(var_name), default_text, description)

def function_summary_lines(entry, used_by=None):
    value_el = entry.find('value')
    name = value_el.findtext('name') if value_el is not None else None
    return_type = value_el.findtext('returnType') if value_el is not None else None
    description = sanitize(value_el.findtext('description') if value_el is not None else '')
    args = []
    if value_el is not None:
        for arg in value_el.findall('arguments/arguments'):
            arg_name = arg.findtext('name') or '?'
            arg_type = arg.findtext('type') or '?'
            args.append('%s: %s' % (sanitize(arg_name), sanitize(arg_type)))
    lines = ['- **%s**' % sanitize(name or '?')]
    if return_type:
        lines.append('  - Return Type: %s' % sanitize(return_type))
    if description:
        lines.append('  - Description: %s' % description)
    lines.append('  - Arguments: %s' % (', '.join(args) if args else 'None'))
    lines.append('  - Used By: %s' % (', '.join(used_by) if used_by else 'None'))
    return lines

def function_usage_map(root):
    usage = defaultdict(list)
    for container_name in ('modules', 'modulesOnHangup'):
        container = root.find(container_name)
        if container is None:
            continue
        for module in container:
            module_name = module.findtext('moduleName') or module.findtext('moduleId') or module.tag
            if module.tag != 'setVariable':
                continue
            for ex in module.findall('data/expressions'):
                if ex.findtext('isFunction') == 'true':
                    fn = ex.findtext('.//functionType') or ex.findtext('.//name') or 'FUNC'
                    if module_name not in usage[fn]:
                        usage[fn].append(module_name)
    return usage

def foreign_script_summary_lines(root):
    grouped = defaultdict(list)
    for container_name in ('modules', 'modulesOnHangup'):
        container = root.find(container_name)
        if container is None:
            continue
        for module in container.findall('foreignScript'):
            script_name = module.findtext('data/ivrScript/name') or '?'
            module_name = module.findtext('moduleName') or module.findtext('moduleId') or 'foreignScript'
            module_lines = []
            if module.findtext('data/passCRM') is not None:
                module_lines.append('Pass CRM: %s' % module.findtext('data/passCRM'))
            if module.findtext('data/returnCRM') is not None:
                module_lines.append('Return CRM: %s' % module.findtext('data/returnCRM'))
            params = []
            for param in module.findall('data/params/entry'):
                key = param.findtext('key') or '?'
                value_el = param.find('value')
                if value_el is None:
                    continue
                is_var = value_el.findtext('isVarSelected') == 'true'
                raw_value = value_el.findtext('variableName') if is_var else value_el.findtext('.//value')
                params.append('Parameter: %s <- %s' % (key, format_foreign_value(raw_value or '?', is_var)))
            returns = []
            for ret in module.findall('data/returnVals/entry'):
                key = ret.findtext('key') or '?'
                raw_value = ret.findtext('value') or '?'
                returns.append('Return: %s -> %s' % (key, format_foreign_value(raw_value, True)))
            grouped[script_name].append({
                'module_name': module_name,
                'details': module_lines,
                'params': params,
                'returns': returns,
            })
    return grouped

def svg_text_segments(line):
    segments = []
    pos = 0
    pattern = re.compile(r'\*\*\[([^\]]+)\]\*\*|\*\{\{([^}]+)\}\}\*')
    for match in pattern.finditer(line):
        if match.start() > pos:
            segments.append((line[pos:match.start()], None))
        if match.group(1) is not None:
            segments.append((f'[{match.group(1)}]', 'bold'))
        else:
            segments.append((f'{{{{{match.group(2)}}}}}', 'italic'))
        pos = match.end()
    if pos < len(line):
        segments.append((line[pos:], None))
    return segments

# ---------------- prompt decoding ----------------
def decode_tts(xmltext):
    """Return ordered list of prompt fragments from decoded speakElement xml."""
    try:
        raw = gzip.decompress(base64.b64decode(xmltext)).decode('utf-8','replace')
    except Exception:
        return []
    frags = []
    try:
        el = ET.fromstring(raw)
        def walk(e):
            if e.tag == 'textElement':
                b = e.findtext('body')
                if b and b.strip(): frags.append(b.strip())
            elif e.tag == 'variableElement':
                vn = e.findtext('variableName')
                if vn: frags.append('{'+vn+'}')
                else:
                    for c in e: walk(c)
                return
            for c in e: walk(c)
        walk(el)
    except Exception:
        frags = [b.strip() for b in re.findall(r'<body>(.*?)</body>', raw, re.S) if b.strip()]
    return frags

def prompt_lines(prompt_el):
    """Compound prompt: ordered filePrompt / ttsPrompt children -> lines."""
    if prompt_el is None: return []
    lines = []
    for ch in list(prompt_el):
        if ch.tag == 'filePrompt':
            sel = ch.findtext('.//promptSelected')
            name = ch.findtext('.//name')
            if name and (sel is None or sel == 'true'):
                lines.append('[File: %s]' % name)
        elif ch.tag == 'ttsPrompt':
            x = ch.findtext('xml')
            if x:
                frags = decode_tts(x)
                if frags: lines.append('"%s"' % ' '.join(frags))
    return lines

def operand_str(op):
    if op is None: return '?'
    if op.findtext('isVarSelected') == 'true':
        return op.findtext('variableName') or '?'
    int_value = op.findtext('.//integerValue/value')
    if int_value is not None:
        return sanitize(int_value)
    bool_value = op.findtext('.//booleanValue/value')
    if bool_value is not None:
        return sanitize(bool_value)
    v = op.findtext('.//value')
    return '"%s"' % v if v is not None else '?'

# ---------------- parse modules ----------------
def _build(root):
    """Build (nodes, edges) from an ``<ivrScript>`` ElementTree root.

    edges: list of (src, dst, exceptional)
    """
    nodes, edges = {}, []
    exceptions = {}   # moduleId -> exceptional descendant id
    function_arg_names = {}
    for entry in root.findall('functions/entry'):
        fn_name = entry.findtext('value/name')
        if not fn_name:
            continue
        arg_names = []
        for arg in entry.findall('value/arguments/arguments'):
            arg_names.append(sanitize(arg.findtext('name') or '?'))
        if arg_names:
            function_arg_names[sanitize(fn_name)] = arg_names

    def add_edge(s,d,exc=False):
        if s and d: edges.append((s,d,exc))

    def handle(m):
        mid = m.findtext('moduleId')
        name = m.findtext('moduleName') or m.tag
        d = m.find('data')
        body = []
        tag = m.tag
        branches = []   # (branchName, matchText, destId)

        if d is not None:
            if tag in ('play','getDigits','menu','input','recording'):
                # main prompt(s)
                for p in d.findall('.//prompts/prompt') + d.findall('prompt'):
                    body += prompt_lines(p)
                if tag == 'play' and not body:
                    body.append('(recorded / no TTS text)')
            if tag == 'getDigits':
                nd = d.findtext('numberOfDigits'); td = d.findtext('terminateDigit')
                tv = d.findtext('targetVariableName')
                body.append('Digits: %s  Terminate: %s' % (nd, td))
                if tv: body.append('-> %s' % tv)
            if tag == 'input':
                tv = d.findtext('.//targetVariableName') or d.findtext('.//variableName')
                if tv: body.append('-> %s' % tv)
                nit = d.findtext('noInputTimeout')
                if nit: body.append('No-input timeout: %s' % nit)
            if tag == 'recording':
                mt = d.findtext('maxTime'); ma = d.findtext('maxAttempts')
                body.append('Max time: %s  Attempts: %s' % (mt, ma))
            if tag == 'systemInfo':
                sit = d.findtext('systemInfoType')
                if sit: body.append('Info: %s' % sit)
                nrv = d.findtext('numberRecordsVariableName')
                if nrv: body.append('# records -> %s' % nrv)
                for tv in d.findall('.//targetResultVariableNames'):
                    if tv.text: body.append('-> %s' % tv.text)
            if tag == 'systemUpdate':
                body.append('Update: %s' % (d.findtext('objectToModify') or '?'))
                fields = d.findall('.//fieldsToModify')
                if fields: body.append('%d field(s)' % len(fields))
            if tag == 'iterator':
                op = d.findtext('operation'); vn = d.findtext('variableName')
                body.append('%s over %s' % (op or 'iterate', vn or '?'))
                mode = d.findtext('mode')
                if mode: body.append('mode: %s' % mode)
            if tag == 'ivaTransfer':
                proj = d.findtext('projectName'); prov = d.findtext('provider')
                if proj: body.append('Project: %s' % proj)
                if prov: body.append('Provider: %s' % prov)
            if tag == 'setVariable':
                for ex in d.findall('expressions'):
                    vn = ex.findtext('variableName')
                    if ex.findtext('isFunction') == 'true':
                        fn = sanitize(
                            ex.findtext('functionType')
                            or ex.findtext('function/name')
                            or ex.findtext('name')
                            or 'FUNC'
                        )
                        arg_nodes = ex.findall('arguments/arguments')
                        if not arg_nodes:
                            arg_nodes = ex.findall('functionArgs')
                        args = [operand_str(a) for a in arg_nodes]
                        names = function_arg_names.get(fn, [])
                        named_args = []
                        for idx, value in enumerate(args):
                            arg_name = names[idx] if idx < len(names) else 'arg%d' % (idx + 1)
                            named_args.append('%s=%s' % (arg_name, value))
                        args = named_args
                        body.append('%s = %s(%s)' % (vn, fn, ', '.join(args)))
                    else:
                        c = ex.find('constant')
                        val = c.findtext('.//value') if c is not None else None
                        if val is None and c is not None and c.findtext('isVarSelected')=='true':
                            val = c.findtext('variableName')
                        body.append('%s = %s' % (vn, '""' if val is None else val))
            if tag == 'ifElse':
                conds = []
                for idx, c in enumerate(d.findall('conditions'), start=1):
                    lo = operand_str(c.find('leftOperand'))
                    ro = operand_str(c.find('rightOperand'))
                    conds.append('%d. IF %s %s %s' % (
                        idx, lo, c.findtext('comparisonType') or '?', ro
                    ))
                grouping = d.findtext('conditionGrouping')
                custom_expr = d.findtext('customCondition')
                body += conds
                if grouping:
                    body.append('Grouping: %s' % grouping)
                if custom_expr:
                    body.append('Expression: %s' % custom_expr)
                elif len(conds) > 1 and grouping:
                    body.append('(match %s)' % grouping)
            if tag == 'case':
                var = None
                for e in d.findall('branches/entry'):
                    v = e.find('value')
                    if v is not None:
                        vn = v.findtext('.//variableName')
                        if vn: var = vn; break
                body.append('Switch on %s' % (var or '?'))
            if tag == 'lookupCRMRecord':
                for c in d.findall('conditions'):
                    val = c.findtext('value')
                    if c.findtext('isVariableSelected') == 'true':
                        val = c.findtext('variableName') or val
                    body.append('%s %s %s' % (c.findtext('crmField'), c.findtext('operator'), val))
            if tag == 'crmUpdate':
                body.append('Mode: %s' % d.findtext('mode'))
                body.append('Variables: %s' % d.findtext('crmVariablesAction'))
            if tag == 'setDNC':
                body.append('DNC target: %s' % d.findtext('targetVariableName'))
            if tag == 'skillTransfer':
                skills = [o.findtext('name') for o in d.findall('listOfSkillsEx/extrnalObj') if o.findtext('name')]
                body.append('Skill: %s' % (', '.join(skills) or '?'))
                if d.findtext('vmSkillBox/name'):
                    body.append('VM box: %s' % d.findtext('vmSkillBox/name'))
            if tag in ('agentTransfer','thirdPartyTransfer','voiceMailTransfer'):
                dest = d.findtext('.//extension') or d.findtext('.//number') or d.findtext('.//name')
                if dest: body.append('Dest: %s' % dest)
            if tag == 'foreignScript':
                body.append('Script: %s' % d.findtext('ivrScript/name'))
                if d.findtext('passCRM') is not None:
                    body.append('Pass CRM: %s' % d.findtext('passCRM'))
                if d.findtext('returnCRM') is not None:
                    body.append('Return CRM: %s' % d.findtext('returnCRM'))
                for p in d.findall('params/entry'):
                    key = p.findtext('key') or '?'
                    val = p.find('value')
                    if val is None:
                        continue
                    src = val.findtext('variableName') if val.findtext('isVarSelected') == 'true' else None
                    body.append('Input: %s <- %s' % (key, format_foreign_value(
                        src or val.findtext('.//value') or '?',
                        val.findtext('isVarSelected') == 'true'
                    )))
                for r in d.findall('returnVals/entry'):
                    key = r.findtext('key') or '?'
                    out = r.findtext('value') or '?'
                    body.append('Output: %s -> %s' % (key, format_foreign_value(out, True)))
            if tag == 'language':
                mode = d.findtext('selectionMode')
                val = d.findtext('setToValue/stringValue/value')
                body.append('%s %s' % (mode or 'SET', val or ''))
            if tag == 'query':
                body.append('%s %s' % (d.findtext('method') or '', d.findtext('url') or ''))

            # ---- branches ----
            menu_items = {}
            if tag == 'menu':
                for it in d.findall('items'):
                    an = it.findtext('actionName'); dt = it.findtext('dtmf')
                    if an: menu_items[an] = (dt or '').replace('DTMF_','')
            for e in d.findall('branches/entry'):
                key = e.findtext('key')
                v = e.find('value')
                dest = v.findtext('desc') if v is not None else None
                match = None
                if tag == 'case' and v is not None:
                    mv = v.findtext('.//value')
                    if mv: match = '= "%s"' % mv
                if tag == 'menu' and key in menu_items:
                    match = 'DTMF %s' % menu_items[key]
                branches.append((key, match, dest))

        nodes[mid] = dict(id=mid, tag=tag, name=name, body=[sanitize(b) for b in body if b])
        # edges
        sd = m.findtext('singleDescendant')
        if sd: add_edge(mid, sd)
        exc = m.findtext('exceptionalDescendant')
        if exc: exceptions[mid] = exc
        return branches

    port_seq = [0]
    all_branches = {}
    for container in ('modules','modulesOnHangup'):
        cont = root.find(container)
        if cont is None: continue
        for m in cont:
            br = handle(m)
            if br: all_branches[m.findtext('moduleId')] = br

    # branch-port nodes
    for mid, brs in all_branches.items():
        for key, match, dest in brs:
            if not dest: continue
            port_seq[0] += 1
            pid = 'PORT%d' % port_seq[0]
            nodes[pid] = dict(id=pid, tag='PORT', name=sanitize(key),
                              body=[sanitize(match)] if match else [])
            edges.append((mid, pid, False))
            edges.append((pid, dest, False))

    # exception-handler ports: an explicit, labeled (red) second exit for every
    # module that defines an exceptionalDescendant, mirroring the branch ports.
    for mid, dest in exceptions.items():
        if not dest or dest not in nodes: continue
        port_seq[0] += 1
        pid = 'PORTX%d' % port_seq[0]
        nodes[pid] = dict(id=pid, tag='PORT_EXC', name='exception', body=[])
        edges.append((mid, pid, True))
        edges.append((pid, dest, True))

    # drop dangling edges and self-loops
    edges = [(s,d,x) for (s,d,x) in edges if s in nodes and d in nodes and s != d]
    return nodes, edges

def parse_ivr(xml_definition):
    """Parse an IVR ``xmlDefinition`` string -> (nodes, edges)."""
    return _build(ET.fromstring(xml_definition))

def parse(path):
    """Backward-compatible file wrapper (accepts a ``.five9ivr`` path)."""
    return _build(ET.parse(path).getroot())

# ---------------- layout (Sugiyama-lite) ----------------
def components(nodes, edges):
    from collections import defaultdict as dd
    adj = dd(set)
    for s,d,x in edges: adj[s].add(d); adj[d].add(s)
    seen, comps = set(), []
    for n in nodes:
        if n in seen: continue
        stack, comp = [n], set()
        while stack:
            u = stack.pop()
            if u in comp: continue
            comp.add(u); seen.add(u)
            stack.extend(sorted(adj[u]-comp))
        comps.append(comp)
    return comps

def layout_component(nodes, edges, keys):
    """Layered layout for the subgraph induced by keys. Returns x,y,dims,layer,gaps."""
    keyset = set(keys)
    keys = [n for n in nodes if n in keyset]   # document order, deterministic
    sub_edges = [(s,d,x) for (s,d,x) in edges if s in keyset and d in keyset]
    succ = defaultdict(list); pred = defaultdict(list)
    for s,d,x in sub_edges: succ[s].append(d); pred[d].append(s)
    roots = [n for n in keys if not pred[n]] or [keys[0]]

    back = set(); state = {}
    def dfs(u):
        state[u] = 1
        for v in succ[u]:
            if state.get(v) == 1: back.add((u,v))
            elif v not in state: dfs(v)
        state[u] = 2
    sys.setrecursionlimit(10000)
    for r in roots: dfs(r)
    for n in keys:
        if n not in state: dfs(n)

    fwd = [(s,d) for s,d,x in sub_edges if (s,d) not in back]
    layer = {n:0 for n in keys}
    changed, it = True, 0
    while changed and it < 3000:
        changed = False; it += 1
        for s,d in fwd:
            if layer[d] < layer[s]+1: layer[d] = layer[s]+1; changed = True

    L = defaultdict(list)
    for n in keys: L[layer[n]].append(n)
    maxl = max(L)

    order = {l: list(L[l]) for l in L}
    pos = {}
    def reindex(l):
        for i,n in enumerate(order[l]): pos[n] = i
    for l in order: reindex(l)
    fsucc = defaultdict(list); fpred = defaultdict(list)
    for s,d in fwd: fsucc[s].append(d); fpred[d].append(s)
    for sweep in range(6):
        rng = range(1, maxl+1) if sweep % 2 == 0 else range(maxl-1, -1, -1)
        ref = fpred if sweep % 2 == 0 else fsucc
        for l in rng:
            def bc(n):
                r = [pos[m] for m in ref[n] if m in pos]
                return sum(r)/len(r) if r else pos[n]
            order[l].sort(key=bc); reindex(l)

    W_MOD, W_PORT = 230, 140
    LINE_H, PAD = 15, 14
    dims = {}
    for n in keys:
        info = nodes[n]
        w = W_PORT if is_port(info['tag']) else W_MOD
        wrapped = []
        wrap_width = 48 if info['tag'] == 'foreignScript' else 34
        for b in info['body']:
            wrapped += wrap(b, 22 if is_port(info['tag']) else wrap_width)
        info['lines'] = wrapped
        h = PAD*2 + 18 + LINE_H*len(wrapped)
        kind = STYLE.get(info['tag'], DEFAULT_STYLE)[0]
        if kind == 'diamond': h = max(h+30, 90); w += 40
        if kind in ('circle','ellipse'): h = max(h, 60)
        dims[n] = (w, h)

    HGAP, VGAP = 60, 100
    x = {}
    for l in order:
        cx = 0
        for n in order[l]:
            x[n] = cx + dims[n][0]/2
            cx += dims[n][0] + HGAP

    def relax_layer(l):
        desired = {}
        for n in order[l]:
            nb = fpred[n] + fsucc[n]
            desired[n] = sum(x[m] for m in nb if m in x)/len(nb) if nb else x[n]
        row = sorted(order[l], key=lambda n: desired[n])
        newx = {}
        for i,n in enumerate(row):
            nx = desired[n]
            if i:
                a = row[i-1]
                minx = newx[a] + dims[a][0]/2 + HGAP + dims[n][0]/2
                nx = max(nx, minx)
            newx[n] = nx
        drift = sum(newx[n]-desired[n] for n in row)/len(row)
        for n in row: x[n] = newx[n] - drift
        order[l] = row

    for sweep in range(10):
        rng = range(maxl+1) if sweep % 2 == 0 else range(maxl, -1, -1)
        for l in rng: relax_layer(l)

    # ---- alignment snapping: make chains perfectly vertical ----
    def can_place(n, l, nx):
        row = order[l]
        i = row.index(n)
        if i > 0:
            a = row[i-1]
            if nx - dims[n][0]/2 < x[a] + dims[a][0]/2 + 20: return False
        if i < len(row)-1:
            b = row[i+1]
            if nx + dims[n][0]/2 > x[b] - dims[b][0]/2 - 20: return False
        return True
    for _ in range(6):
        moved = False
        for l in range(1, maxl+1):
            for n in order[l]:
                if len(fpred[n]) == 1:
                    p = fpred[n][0]
                    dx = abs(x[n]-x[p])
                    if 0.01 < dx and (len(fsucc[p]) == 1 or dx < 90):
                        if can_place(n, l, x[p]):
                            x[n] = x[p]; moved = True
        for l in range(maxl-1, -1, -1):   # pull single-child parents over their child
            for n in order[l]:
                if len(fsucc[n]) == 1 and len(fpred[n]) <= 1:
                    c = fsucc[n][0]
                    dx = abs(x[n]-x[c])
                    if 0.01 < dx < 90 and can_place(n, l, x[c]):
                        x[n] = x[c]; moved = True
        if not moved: break

    rowh = {l: max(dims[n][1] for n in order[l]) for l in order}
    y = {}; row_top = {}; row_bot = {}
    cy = 0
    for l in range(maxl+1):
        row_top[l] = cy
        for n in order[l]: y[n] = cy + rowh[l]/2
        cy += rowh[l]; row_bot[l] = cy; cy += VGAP
    gaps = {l: (row_bot[l] + row_top.get(l+1, row_bot[l]+VGAP))/2 for l in range(maxl+1)}

    minx = min(x[n]-dims[n][0]/2 for n in keys)
    for n in x: x[n] -= minx
    return x, y, dims, layer, gaps, maxl

def layout(nodes, edges):
    comps = components(nodes, edges)
    # Prefer the component that contains the incomingCall entry point; if an IVR
    # has none (e.g. a reusable subflow), fall back to the largest component.
    main = next((c for c in comps if any(nodes[n]['tag']=='incomingCall' for n in c)), None)
    if main is None:
        main = max(comps, key=len)
    side = [c for c in comps if c is not main]
    # on-hangup flow first, then unreferenced singles
    side.sort(key=lambda c: (0 if any(nodes[n]['tag']=='startOnHangup' for n in c) else 1, -len(c)))

    X, Y, DIMS, LAYER = {}, {}, {}, {}
    main = [n for n in nodes if n in main]
    side = [[n for n in nodes if n in c] for c in side]
    x,y,dims,layer,gaps,maxl = layout_component(nodes, edges, main)
    for n in main:
        X[n], Y[n], DIMS[n], LAYER[n] = x[n]+40, y[n]+80, dims[n], layer[n]
    main_gaps = {l: g+80 for l,g in gaps.items()}
    main_right = max(X[n]+DIMS[n][0]/2 for n in main)

    labels = []   # (text, x, y)
    side_x = main_right + 320
    side_y = 80
    for c in side:
        heading = ('ON-HANGUP FLOW' if any(nodes[n]['tag']=='startOnHangup' for n in c)
                   else 'UNREFERENCED MODULE (no inbound path)')
        sx,sy,sd,sl,sg,sml = layout_component(nodes, edges, c)
        w = max(sx[n]+sd[n][0]/2 for n in c)
        labels.append((heading, side_x + w/2, side_y))
        for n in c:
            X[n] = sx[n] + side_x
            Y[n] = sy[n] + side_y + 40
            DIMS[n] = sd[n]; LAYER[n] = -1   # side components use simple routing
        side_y += max(sy[n]+sd[n][1]/2 for n in c) + 40 + 120

    return X, Y, DIMS, LAYER, main_gaps, main, labels

# ---------------- SVG emission (collision-aware routing) ----------------
def shape_svg(kind, cx, cy, w, h, fill, stroke='#555555'):
    x0, y0 = cx-w/2, cy-h/2
    s = 'fill="%s" stroke="%s" stroke-width="1.5"' % (fill, stroke)
    if kind == 'rect':
        return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" %s/>' % (x0,y0,w,h,s)
    if kind in ('round','card','dblbar','manual','cylinder','document'):
        return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="10" %s/>' % (x0,y0,w,h,s)
    if kind in ('ellipse','circle'):
        return '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" %s/>' % (cx,cy,w/2,h/2,s)
    if kind == 'diamond':
        pts = '%f,%f %f,%f %f,%f %f,%f' % (cx,y0, x0+w,cy, cx,y0+h, x0,cy)
        return '<polygon points="%s" %s/>' % (pts,s)
    if kind == 'hexagon':
        i = min(24, w*0.15)
        pts = '%f,%f %f,%f %f,%f %f,%f %f,%f %f,%f' % (
            x0+i,y0, x0+w-i,y0, x0+w,cy, x0+w-i,y0+h, x0+i,y0+h, x0,cy)
        return '<polygon points="%s" %s/>' % (pts,s)
    if kind == 'parallelogram':
        o = 20
        pts = '%f,%f %f,%f %f,%f %f,%f' % (x0+o,y0, x0+w,y0, x0+w-o,y0+h, x0,y0+h)
        return '<polygon points="%s" %s/>' % (pts,s)
    if kind == 'trapezoid':
        o = 25
        pts = '%f,%f %f,%f %f,%f %f,%f' % (x0+o,y0, x0+w-o,y0, x0+w,y0+h, x0,y0+h)
        return '<polygon points="%s" %s/>' % (pts,s)
    if kind == 'pentagon':
        pts = '%f,%f %f,%f %f,%f %f,%f %f,%f' % (x0,y0, x0+w,y0, x0+w,y0+h-18, cx,y0+h, x0,y0+h-18)
        return '<polygon points="%s" %s/>' % (pts,s)
    if kind == 'chevron':
        a = 22
        pts = '%f,%f %f,%f %f,%f %f,%f %f,%f' % (x0,y0, x0+w-a,y0, x0+w,cy, x0+w-a,y0+h, x0,y0+h)
        return '<polygon points="%s" %s/>' % (pts,s)
    return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" %s/>' % (x0,y0,w,h,s)

TITLE_BAND = 48

def emit_svg(nodes, edges, X, Y, DIMS, LAYER, gaps, main, labels, title=None):
    # Reserve a band at the top for the title block by shifting all geometry
    # (nodes, routing gaps, side-column labels) down before anything is drawn.
    if title:
        X = dict(X)
        Y = {n: Y[n] + TITLE_BAND for n in Y}
        gaps = {k: v + TITLE_BAND for k, v in gaps.items()}
        labels = [(t, lx, ly + TITLE_BAND) for (t, lx, ly) in labels]
    PADB = 10
    boxes = {n:(X[n]-DIMS[n][0]/2-PADB, Y[n]-DIMS[n][1]/2-PADB,
                X[n]+DIMS[n][0]/2+PADB, Y[n]+DIMS[n][1]/2+PADB) for n in nodes}
    def v_clear(vx, ya, yb, skip=()):
        y0, y1 = min(ya,yb), max(ya,yb)
        for n,(bx0,by0,bx1,by1) in boxes.items():
            if n in skip: continue
            if bx0 < vx < bx1 and by0 < y1 and y0 < by1:
                return False
        return True
    def h_clear(hy, xa, xb, skip=()):
        x0, x1 = min(xa,xb), max(xa,xb)
        for n,(bx0,by0,bx1,by1) in boxes.items():
            if n in skip: continue
            if by0 < hy < by1 and bx0 < x1 and x0 < bx1:
                return False
        return True

    def route(s, d):
        x1, y1 = X[s], Y[s]+DIMS[s][1]/2
        x2, y2 = X[d], Y[d]-DIMS[d][1]/2
        ls, ld = LAYER[s], LAYER[d]
        sk = (s, d)
        if y2 > y1:  # forward/down
            if abs(x1-x2) < 2 and v_clear(x1, y1, y2, sk):
                return 'M %.1f %.1f L %.1f %.1f' % (x1,y1,x2,y2)
            gA = gaps.get(ls, y1+30) if ls >= 0 else y1+30
            gB = gaps.get(ld-1, y2-30) if ld >= 1 else y2-30
            gA = max(gA, y1+12); gB = min(gB, y2-12)
            # candidate A: exit jog near source, long straight lane at target x
            if v_clear(x2, gA, y2, sk) and h_clear(gA, x1, x2, sk):
                return 'M %.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f' % (
                    x1,y1, x1,gA, x2,gA, x2,y2)
            # candidate B: long lane at source x, entry jog near target
            if v_clear(x1, y1, gB, sk) and h_clear(gB, x1, x2, sk):
                return 'M %.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f' % (
                    x1,y1, x1,gB, x2,gB, x2,y2)
            # candidate C: find a free vertical corridor near target x
            for off in [j for k in range(1,30) for j in (k*35, -k*35)]:
                lane = x2 + off
                if v_clear(lane, gA, gB, sk) and h_clear(gA, x1, lane, sk) and h_clear(gB, lane, x2, sk):
                    return ('M %.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f '
                            'L %.1f %.1f L %.1f %.1f') % (
                        x1,y1, x1,gA, lane,gA, lane,gB, x2,gB, x2,y2)
            midy = (y1+y2)/2   # fallback
            return 'M %.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f' % (
                x1,y1, x1,midy, x2,midy, x2,y2)
        else:  # back edge (loop): drop into gap, ride a clear lane up, enter target top
            gA = gaps.get(ls, y1+30) if ls >= 0 else y1+30      # gap below source row
            gT = gaps.get(ld-1, y2-30) if ld >= 1 else y2-30    # gap above target row
            gA = max(gA, y1+12); gT = min(gT, y2-12)
            for off in [j for k in range(1,60) for j in (k*35, -k*35)]:
                lane = x2 + off
                if (v_clear(lane, gT, gA, sk) and h_clear(gA, x1, lane, sk)
                        and h_clear(gT, lane, x2, sk)):
                    return ('M %.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f '
                            'L %.1f %.1f L %.1f %.1f') % (
                        x1,y1, x1,gA, lane,gA, lane,gT, x2,gT, x2,y2)
            lane = max(X[n]+DIMS[n][0]/2 for n in nodes) + 60   # far-right fallback
            return ('M %.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f '
                    'L %.1f %.1f L %.1f %.1f') % (
                x1,y1, x1,gA, lane,gA, lane,gT, x2,gT, x2,y2)

    parts = []
    content_right = max(X[n]+DIMS[n][0]/2 for n in nodes)
    content_bottom = max(Y[n]+DIMS[n][1]/2 for n in nodes)

    # ---- legend geometry (only the module types actually used) ----
    present = [t for t in STYLE if any(info['tag'] == t for info in nodes.values())]
    legend_x0 = content_right + 40
    legend_w = 214
    legend_row_h = 28
    legend_top = 30
    legend_h = 34 + legend_row_h * len(present) + 10 if present else 0

    width = (legend_x0 + legend_w + 20) if present else content_right + 80
    height = max(content_bottom + 80, legend_top + legend_h + 20)
    parts.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
                 'viewBox="0 0 %d %d" font-family="Arial, sans-serif">' % (width,height,width,height))
    parts.append('<defs><marker id="arr" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">'
                 '<path d="M0,0 L10,4 L0,8 z" fill="#333333"/></marker>'
                 '<marker id="arrR" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">'
                 '<path d="M0,0 L10,4 L0,8 z" fill="#CC0000"/></marker></defs>')

    # ---- title block ----
    if title:
        module_count = sum(1 for info in nodes.values() if not is_port(info['tag']))
        # A "transition" is one exit from a real module (branch/exception ports
        # count once, not as the two internal edges that implement them).
        edge_count = sum(1 for s,_d,_x in edges if not is_port(nodes[s]['tag']))
        parts.append('<text x="40" y="30" font-size="18" font-weight="bold">%s</text>'
                     % html.escape(sanitize(title)))
        parts.append('<text x="40" y="48" font-size="12" fill="#666666">%d modules, '
                     '%d transitions</text>' % (module_count, edge_count))

    for s,d,exc in edges:
        color = '#CC0000' if exc else '#333333'
        mark = 'arrR' if exc else 'arr'
        parts.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.6" marker-end="url(#%s)"/>' % (
            route(s,d), color, mark))

    for text, lx, ly in labels:
        parts.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="16" '
                     'font-weight="bold">%s</text>' % (lx, ly, html.escape(text)))

    for n,info in nodes.items():
        kind, fill = STYLE.get(info['tag'], DEFAULT_STYLE)
        is_exc = info['tag'] == 'PORT_EXC'
        stroke = '#C0392B' if is_exc else '#555555'
        tcol = '#C0392B' if is_exc else '#000000'
        w,h = DIMS[n]; cx,cy = X[n], Y[n]
        parts.append('<g>')
        parts.append(shape_svg(kind, cx, cy, w, h, fill, stroke))
        lines = info['lines']
        total = 18 + 15*len(lines)
        ty = cy - total/2 + 13
        parts.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="12" fill="%s" '
                     'font-weight="bold" text-decoration="underline">%s</text>' % (cx,ty,tcol,html.escape(sanitize(info['name']))))
        ty += 17
        for ln in lines:
            segs = svg_text_segments(ln)
            if len(segs) == 1 and segs[0][1] is None:
                parts.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="11" fill="%s">%s</text>' % (cx,ty,tcol,html.escape(ln)))
            else:
                chunks = ['<text x="%.1f" y="%.1f" text-anchor="middle" font-size="11" fill="%s" xml:space="preserve">' % (cx,ty,tcol)]
                for text, style in segs:
                    attrs = ''
                    if style == 'bold':
                        attrs = ' font-weight="bold"'
                    elif style == 'italic':
                        attrs = ' font-style="italic"'
                    chunks.append('<tspan%s>%s</tspan>' % (attrs, html.escape(text)))
                chunks.append('</text>')
                parts.append(''.join(chunks))
            ty += 15
        parts.append('</g>')

    # ---- legend panel ----
    if present:
        parts.append('<rect x="%.1f" y="%.1f" width="%d" height="%.1f" rx="6" '
                     'fill="#FCFCFC" stroke="#CCCCCC" stroke-width="1"/>'
                     % (legend_x0, legend_top, legend_w, legend_h))
        parts.append('<text x="%.1f" y="%.1f" font-size="13" font-weight="bold">Legend</text>'
                     % (legend_x0 + 12, legend_top + 22))
        ry = legend_top + 34 + legend_row_h/2
        for t in present:
            kind, fill = STYLE[t]
            is_exc = t == 'PORT_EXC'
            stroke = '#C0392B' if is_exc else '#555555'
            tcol = '#C0392B' if is_exc else '#000000'
            parts.append(shape_svg(kind, legend_x0 + 24, ry, 30, 16, fill, stroke))
            parts.append('<text x="%.1f" y="%.1f" font-size="11" fill="%s">%s</text>'
                         % (legend_x0 + 50, ry + 4, tcol, html.escape(LEGEND_NAMES.get(t, t))))
            ry += legend_row_h

    parts.append('</svg>')
    return '\n'.join(parts)

# ---------------- high-level entry points ----------------
def ivr_to_svg(xml_definition, name=None):
    """IVR ``xmlDefinition`` string -> styled SVG call-flow (string).

    If ``name`` is given it is stamped onto the diagram as a title block.
    Raises ValueError if the script has no diagrammable modules.
    """
    nodes, edges = parse_ivr(xml_definition)
    if not nodes:
        raise ValueError("IVR script contains no modules to diagram")
    X, Y, DIMS, LAYER, gaps, main, labels = layout(nodes, edges)
    return emit_svg(nodes, edges, X, Y, DIMS, LAYER, gaps, main, labels, title=name)

def ivr_to_text(xml_definition, name=None):
    """IVR ``xmlDefinition`` string -> human-readable Markdown documentation.

    Produces a summary document focused on variables, JavaScript functions, and
    foreign scripts in use.
    """
    nodes, edges = parse_ivr(xml_definition)
    root = ET.fromstring(xml_definition)

    lines = ['# IVR: %s' % (sanitize(name) if name else '(unnamed)'), '']
    modules = [n for n in nodes.values() if not is_port(n['tag'])]
    transition_count = sum(1 for s, _d, _x in edges if not is_port(nodes[s]['tag']))
    lines.append('%d modules, %d transitions' % (len(modules), transition_count))
    lines.append('')

    user_vars = root.findall('userVariables/entry')
    lines.append('## Script Variables')
    lines.append('')
    if user_vars:
        lines.append('| Name | Default | Description |')
        lines.append('| --- | --- | --- |')
        for entry in user_vars:
            lines.append(script_variable_summary_lines(entry))
        lines.append('')
    else:
        lines.append('- No script variables defined.')
        lines.append('')

    function_entries = root.findall('functions/entry')
    function_usage = function_usage_map(root)
    lines.append('## JavaScript Functions')
    lines.append('')
    if function_entries:
        for entry in function_entries:
            name = entry.findtext('value/name') or '?'
            lines.extend(function_summary_lines(entry, function_usage.get(name, [])))
            lines.append('')
    else:
        lines.append('- No JavaScript functions defined.')
        lines.append('')

    foreign_groups = foreign_script_summary_lines(root)
    lines.append('## Foreign Scripts')
    lines.append('')
    if foreign_groups:
        for script_name in sorted(foreign_groups):
            lines.append('- **%s**' % sanitize(script_name))
            for module in foreign_groups[script_name]:
                lines.append('  - Module: %s' % sanitize(module['module_name']))
                if module['details']:
                    lines.append('    - Details:')
                    for detail in module['details']:
                        lines.append('      - %s' % detail)
                if module['params']:
                    lines.append('    - Parameters:')
                    for param in module['params']:
                        lines.append('      - %s' % param)
                if module['returns']:
                    lines.append('    - Return Values:')
                    for ret in module['returns']:
                        lines.append('      - %s' % ret)
            lines.append('')
    else:
        lines.append('- No foreign scripts defined.')
        lines.append('')
    return '\n'.join(lines)

# ---------------- CLI (backward compatible) ----------------
def _read_source(path):
    """Return an xmlDefinition string from a .five9ivr XML file or captured JSON."""
    with open(path, 'r') as f:
        raw = f.read()
    stripped = raw.lstrip()
    if stripped.startswith('{'):
        return json.loads(raw)['xmlDefinition']
    return raw

def main():
    src, out = sys.argv[1], sys.argv[2]
    xml = _read_source(src)
    title = os.path.splitext(os.path.basename(src))[0]
    nodes, edges = parse_ivr(xml)
    X, Y, DIMS, LAYER, gaps, main_comp, labels = layout(nodes, edges)
    svg = emit_svg(nodes, edges, X, Y, DIMS, LAYER, gaps, main_comp, labels, title=title)
    with open(out,'w') as f: f.write(svg)
    print('nodes=%d edges=%d size=%dKB' % (len(nodes), len(edges), len(svg)//1024))

    # ---- same-run verification ----
    # emit_svg shifts all geometry down by TITLE_BAND when a title is present;
    # mirror that here so boxes align with the coordinates in the emitted paths.
    if title:
        Y = {n: Y[n] + TITLE_BAND for n in Y}
    import re as _re
    paths = _re.findall(r'<path d="(M[^"]+)" fill="none"', svg)
    st = sum(1 for p in paths if p.count('L')==1)
    b2 = sum(1 for p in paths if p.count('L')==3)
    b4 = sum(1 for p in paths if p.count('L')>3)
    boxes = {n:(X[n]-DIMS[n][0]/2, Y[n]-DIMS[n][1]/2, X[n]+DIMS[n][0]/2, Y[n]+DIMS[n][1]/2) for n in nodes}
    ks = list(nodes); ov = 0
    for i in range(len(ks)):
        for j in range(i+1,len(ks)):
            a,b = boxes[ks[i]], boxes[ks[j]]
            if a[0]<b[2] and b[0]<a[2] and a[1]<b[3] and b[1]<a[3]: ov += 1
    cross = 0
    for (s,d,exc),p in zip(edges, paths):
        pts = [(float(a),float(b)) for a,b in _re.findall(r'([-\d.]+) ([-\d.]+)', p)]
        hit = False
        for (xa,ya),(xb,yb) in zip(pts, pts[1:]):
            for n,(bx0,by0,bx1,by1) in boxes.items():
                if n in (s,d): continue
                if abs(xa-xb)<0.01 and bx0<xa<bx1 and min(ya,yb)<by1 and by0<max(ya,yb): hit=True; break
                if abs(ya-yb)<0.01 and by0<ya<by1 and min(xa,xb)<bx1 and bx0<max(xa,xb): hit=True; break
            if hit: break
        if hit: cross += 1
    print('VERIFY: straight=%d 2-bend=%d 4+bend=%d | shape-overlaps=%d | edges-crossing-shapes=%d' % (
        st, b2, b4, ov, cross))
    # unmapped types flag
    unmapped = sorted({i['tag'] for i in nodes.values() if i['tag'] not in STYLE})
    if unmapped: print('UNMAPPED TYPES (gray default):', unmapped)

if __name__ == '__main__':
    main()
