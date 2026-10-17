import assert from 'node:assert/strict';
const base=process.env.WEB_URL;
if(!base)throw new Error('Set WEB_URL for a running local synthetic NextRM demo');
const cases=[['/v1/rm/home','usr-maya',200],['/v1/rm/pulse','usr-maya',200],['/v1/rm/prospects','usr-maya',200],['/v1/rm/destinations','usr-dina',200],['/v1/rm/follow-ups','usr-dina',403],['/v1/rm/quality','usr-maya',403],['/v1/rm/quality','usr-aiadmin',200],['/v1/rm/quality','usr-dina',403],['/v1/cases/CF-026','usr-maya',404],['/v1/admin/companies','usr-maya',404],['/v1/local-auth/login','usr-maya',404]];
for(const [path,user,expected] of cases){
 const response=await fetch(base+'/api'+path,{headers:{'X-User-Id':user,'X-Tenant-Id':'demo-bank'}});assert.equal(response.status,expected,path);console.log('PASS proxy',path,response.status);
}
const response=await fetch(base+'/api/v1/rm/home',{headers:{'Authorization':'Bearer usr-maya','X-Tenant-Id':'demo-bank'}});assert.equal(response.status,401);console.log('PASS proxy rejects fabricated Bearer identity');
