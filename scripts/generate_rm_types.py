"""Generate relationship API contracts from OpenAPI; no database mutations."""
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'services/api'))
from app.main import app
schemas=app.openapi()['components']['schemas']
def ts(s):
    if '$ref' in s:return s['$ref'].split('/')[-1]
    if 'enum' in s:return ' | '.join(__import__('json').dumps(x) for x in s['enum'])
    if 'const' in s:return __import__('json').dumps(s['const'])
    if 'anyOf' in s:return ' | '.join(ts(x) for x in s['anyOf'])
    if s.get('type')=='array':return 'Array<'+ts(s['items'])+'>'
    if s.get('type')=='object':return 'Record<string, '+(ts(s['additionalProperties']) if isinstance(s.get('additionalProperties'),dict) else 'unknown')+'>'
    return {'string':'string','integer':'number','number':'number','boolean':'boolean','null':'null'}.get(s.get('type'),'unknown')
lines=['// Generated from OpenAPI by scripts/generate_rm_types.py. Do not edit.']
for name,schema in schemas.items():
    if not name.startswith('RM'):continue
    lines.append('export interface '+name+' {')
    for key,value in schema.get('properties',{}).items():lines.append('  '+key+('' if key in schema.get('required',[]) else '?')+': '+ts(value)+';')
    lines.append('}')
output=root/'apps/web/src/lib/rm.generated.ts';content='\n'.join(lines)+'\n'
if not output.exists() or output.read_text()!=content:output.write_text(content)
print('Relationship contracts generated from OpenAPI.')
