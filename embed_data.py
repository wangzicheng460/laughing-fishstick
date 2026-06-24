#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Embed exam_data.json into the HTML file directly."""
import json

# Read the JSON data
with open('exam_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Read the HTML template
with open('诊断学试题集_学习系统.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Convert data to JSON string for embedding
data_json = json.dumps(data, ensure_ascii=False)

# Replace the XHR loading code with inline data
old_loading = '''// Load data
var xhr = new XMLHttpRequest();
xhr.onload = function() {
  try {
    var data = JSON.parse(xhr.responseText);
    Q = data.questions || {}; A = data.answers || {}; EN = data.examNames || [];
    document.getElementById('app').innerHTML = '';
    r();
  } catch(e) {
    document.getElementById('app').innerHTML = '<div class="empty-state"><div class="icon">❌</div><p>加载失败</p></div>';
  }
};
xhr.onerror = function() {
  document.getElementById('app').innerHTML = '<div class="empty-state"><div class="icon">❌</div><p>加载失败，请确保 exam_data.json 文件存在</p></div>';
};
xhr.open('GET', 'exam_data.json?' + new Date().getTime(), true);
xhr.send();'''

new_loading = '''// Inline data
var rawData = ' + json.dumps(data_json, ensure_ascii=False) + ';
var data = JSON.parse(rawData);
Q = data.questions || {}; A = data.answers || {}; EN = data.examNames || [];
document.getElementById('app').innerHTML = '';
r();'''

# Actually, the simpler approach: just embed the JSON directly
# Replace the XHR code with inline assignment

old_marker = 'var xhr = new XMLHttpRequest();'
new_code = '''// Data loaded from inline JSON
var __data = ''' + data_json + ''';
Q = __data.questions || {};
A = __data.answers || {};
EN = __data.examNames || [];
document.getElementById('app').innerHTML = '';
r();'''

# Find the exact text to replace
old_block_start = html.find('// Load data')
old_block_end = html.find('</script>', old_block_start)

if old_block_start > 0:
    new_html = html[:old_block_start] + new_code + '\n' + html[old_block_end:]

    with open('诊断学试题集_学习系统.html', 'w', encoding='utf-8') as f:
        f.write(new_html)

    print(f'Done! HTML size: {len(new_html.encode("utf-8"))} bytes')
    print(f'Data embedded: {len(data_json)} bytes of JSON')
else:
    print(f'Could not find load code section (start={old_block_start})')
    # Try alternative approach - just concatenate at end
    print('Trying alternative approach...')

    # Remove the XHR call, keep everything else
    lines = html.split('\n')
    filtered = [l for l in lines if 'xhr.' not in l and 'XMLHttpRequest' not in l
                and 'Load data' not in l and 'xhr.onload' not in l
                and 'xhr.onerror' not in l and 'xhr.open' not in l
                and 'xhr.send' not in l and 'JSON.parse(xhr.responseText)' not in l]

    # Find the </script> tag and add inline data before it
    new_html = '\n'.join(filtered)

    inline_code = f'''\n// Inline embedded data
var __data = {data_json};
Q = __data.questions || {{}};
A = __data.answers || {{}};
EN = __data.examNames || [];
document.getElementById('app').innerHTML = '';
r();\n'''

    insert_pos = new_html.find('</script>')
    if insert_pos > 0:
        new_html = new_html[:insert_pos] + inline_code + new_html[insert_pos:]

    with open('诊断学试题集_学习系统.html', 'w', encoding='utf-8') as f:
        f.write(new_html)

    print(f'Done (alt method)! HTML size: {len(new_html.encode("utf-8"))} bytes')
